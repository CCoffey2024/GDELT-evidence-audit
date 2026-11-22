"""Disk-backed collection of complete GDELT 2 event exports."""
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import sqlite3
import zlib
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from urllib.parse import parse_qsl, urlencode, urlsplit

from collect import archive

DAY = dt.timedelta(days=1)


def stamps(first, last):
    for offset in range((last - first).days + 1):
        prefix = (first + offset * DAY).strftime("%Y%m%d")
        for slot in range(96):
            yield f"{prefix}{slot // 4:02}{slot % 4 * 15:02}00"


def full_batch(stamp):
    rows, events = archive(stamp, "export", 61)
    mentions, manifest = archive(stamp, "mentions", 16)
    linked = defaultdict(list)
    for mention in mentions:
        linked[mention[0]].append(mention)
    return dict(day=dt.datetime.strptime(stamp[:8], "%Y%m%d").date().isoformat(),
                stamp=stamp, events=events, mentions=manifest,
                sample=[dict(raw=row, mentions=linked.get(row[0], [])) for row in rows])


def number(value):
    try:
        return float(value)
    except ValueError:
        return math.nan


def digest(value):
    return hashlib.sha256(value.encode()).digest()[:16] if value else None


def group_keys(source):
    try:
        u = urlsplit(source)
        if u.scheme not in ("http", "https") or not u.hostname:
            return "", "", ""
        host = u.hostname.lower().removeprefix("www.")
        if u.port and (u.scheme, u.port) not in (("http", 80), ("https", 443)):
            host += f":{u.port}"
        params = sorted(((k, v) for k, v in parse_qsl(u.query, keep_blank_values=True)
                         if not re.match(r"^(utm_|fbclid$|gclid$)", k, re.I)), key=lambda p: p[0])
        key = host + u.path.removesuffix("/") + ("?" + urlencode(params) if params else "")
        slug = re.sub(r"\.html?$", "", key.split("?")[0].split("/")[-1].lower())
        if len(slug) < 45 or len(re.findall(r"[^_-]+", slug)) < 8:
            slug = ""
        return key, slug, host
    except ValueError:
        return "", "", ""


def screening_row(item, day):
    r = item["raw"]
    key, slug, host = group_keys(r[60])
    lat, lon = number(r[56]), number(r[57])
    spatial = (r[51] in ("0", "1", "2", "5") or not (abs(lat) <= 90 and abs(lon) <= 180)
               or (lat == 0 and lon == 0))
    confidence = [number(m[11]) for m in item["mentions"] if m[11].strip()]
    confidence = [v for v in confidence if math.isfinite(v)]
    genre = re.search(r"(?:^|[/-])(horoscopes?|recipes?|shopping-guide|buying-guide|best-mba-colleges)(?=[/-]|$)", key[key.find("/"):], re.I)
    extraction = (not r[6] and not r[16]) or bool(confidence and max(confidence) < 50) or bool(genre)
    try:
        age = (day - dt.datetime.strptime(r[1], "%Y%m%d").date()).days
        timing = age < 0 or age >= 30
    except ValueError:
        timing = False
    other = timing or not key or not item["mentions"]
    return digest(key), digest(slug), digest(host) if slug else None, int(spatial), int(extraction), int(other)


def collect_all(job, first, last, path, update):
    """Checkpoint each successful slot. Retry gaps when the range is submitted again."""
    import time
    try:
        with closing(sqlite3.connect(path)) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS slots(stamp TEXT PRIMARY KEY, rows INTEGER, gap INTEGER, payload BLOB);
                CREATE TABLE IF NOT EXISTS checks(stamp TEXT, article BLOB, slug BLOB, host BLOB,
                                                  spatial INTEGER, extraction INTEGER, other INTEGER);
                CREATE INDEX IF NOT EXISTS by_slot ON checks(stamp);
            """)
            complete = {r[0] for r in db.execute("SELECT stamp FROM slots WHERE gap=0")}
            pending = (s for s in stamps(first,last) if s not in complete)
            done = len(complete)
            rows = db.execute("SELECT coalesce(sum(rows),0) FROM slots WHERE gap=0").fetchone()[0]
            update(job, state="collecting", done=done, rows=rows)
            # Keep only a small group of uncommitted archive payloads in memory.
            with ThreadPoolExecutor(max_workers=3) as pool:
                from itertools import islice
                while group := list(islice(pending, 3)):
                    for b in pool.map(full_batch, group):
                        stamp = b["stamp"]
                        items = b["sample"]
                        gap = int("error" in b["events"]) + 2 * int("error" in b["mentions"])
                        day = dt.date.fromisoformat(b["day"])
                        with db:
                            db.execute("DELETE FROM checks WHERE stamp=?", (stamp,))
                            db.executemany("INSERT INTO checks VALUES(?,?,?,?,?,?,?)",
                                           ((stamp, *screening_row(i, day)) for i in items))
                            db.execute("INSERT OR REPLACE INTO slots VALUES(?,?,?,?)",
                                       (stamp, len(items), gap, zlib.compress(json.dumps(b,separators=(",",":")).encode(), 3)))
                        done += 1
                        rows += len(items)
                        update(job, done=done, rows=rows)
            update(job, state="screening")
            if not db.execute("SELECT 1 FROM slots WHERE gap IN (0,2) LIMIT 1").fetchone():
                raise ValueError("No event export could be retrieved. Retry this range.")
            # A repeated coded claim is also a shared article, so it adds no new
            # records to the redundancy category.
            counts = db.execute("""
                WITH articles AS (SELECT article FROM checks WHERE article IS NOT NULL GROUP BY article HAVING count(*)>1),
                slugs AS (SELECT slug FROM checks WHERE slug IS NOT NULL GROUP BY slug HAVING min(host)<>max(host)),
                flags AS (SELECT spatial, extraction, other,
                    (a.article IS NOT NULL OR s.slug IS NOT NULL) AS redundant
                    FROM checks c LEFT JOIN articles a USING(article) LEFT JOIN slugs s USING(slug))
                SELECT count(*),coalesce(sum(spatial OR extraction OR other OR redundant),0),
                       coalesce(sum(redundant),0),coalesce(sum(spatial),0),coalesce(sum(extraction),0) FROM flags
            """).fetchone()
            manifest = list(db.execute("SELECT stamp,rows,gap FROM slots ORDER BY stamp"))
            update(job, state="ready", counts=counts, slots=manifest,
                   gaps=sum(bool(slot[2]) for slot in manifest), finished=time.monotonic())
    except Exception as exc:
        update(job, state="failed", error=f"Full collection interrupted: {exc}. Submit the same dates to retry.", finished=time.monotonic())


def read_batch(path, stamp):
    with closing(sqlite3.connect(path)) as db:
        row = db.execute("SELECT payload FROM slots WHERE stamp=?", (stamp,)).fetchone()
        return json.loads(zlib.decompress(row[0])) if row else None


def export_rows(path):
    with closing(sqlite3.connect(path)) as db:
        for stamp, payload in db.execute("SELECT stamp,payload FROM slots ORDER BY stamp"):
            buffer = io.StringIO()
            writer = csv.writer(buffer, delimiter="\t", lineterminator="\n")
            for item in json.loads(zlib.decompress(payload))["sample"]:
                writer.writerow([stamp, *item["raw"]])
            yield buffer.getvalue()
