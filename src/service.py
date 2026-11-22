"""Public, single-process date-range collector with bounded background work."""
import datetime as dt
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from flask import Flask, abort, jsonify, request, send_from_directory
from article_previews import enrich
from collect import ROOT, SEED, day_sample

PUBLIC = ROOT.parent / "public"
CACHE = Path(os.environ.get("CACHE_DIR", "/tmp/gdelt-day-cache")) / SEED
CACHE.mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1024
worker = ThreadPoolExecutor(max_workers=1)
preview_worker = ThreadPoolExecutor(max_workers=1)
lock = threading.RLock()
jobs = {}
DAY = dt.timedelta(days=1)


def parse_dates(start, end):
    first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    if (first.isoformat(), last.isoformat()) != (start, end):
        raise ValueError("Use YYYY-MM-DD.")
    if not 0 <= (last-first).days < 90:
        raise ValueError("Select 1 to 90 days, inclusive.")
    if first < dt.date(2015, 2, 19) or last >= dt.datetime.now(dt.timezone.utc).date():
        raise ValueError("Use completed UTC days from 2015-02-19 onward.")
    return first, last


def daily(day):
    path = CACHE / (str(day) + ".json")
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf8"))
        except (OSError, ValueError):
            pass
    batch = day_sample(day)
    if all("error" not in batch[k] for k in ("events", "mentions")):
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(batch, separators=(",", ":")), encoding="utf8")
        temp.replace(path)
    return batch


def update(job, **values):
    with lock:
        job.update(values)


def add_previews(job, batches):
    try:
        previews = enrich(batches)
        update(job, previews=previews, metadata="complete")
    except Exception:
        app.logger.exception("Metadata collection failed")
        update(job, metadata="unavailable")
    finally:
        update(job, finished=time.monotonic())


def collect_range(job, first, last):
    try:
        update(job, state="collecting")
        days = [first + i*DAY for i in range(job["total"])]
        batches = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            for batch in pool.map(daily, days):
                batches.append(batch)
                update(job, done=len(batches))
        if all("error" in b["events"] for b in batches):
            update(job, state="failed", error="All selected event archives were unavailable.",
                   finished=time.monotonic())
            return
        result = dict(start=str(first), end=str(last+DAY), seed=SEED, batches=batches,
                      collected=dt.datetime.now(dt.timezone.utc).isoformat())
        update(job, result=result, state="ready", metadata="collecting")
        preview_worker.submit(add_previews, job, batches)
        # Bound cache growth on ephemeral and mounted storage alike.
        files = sorted(CACHE.glob("*.json"), key=lambda p: p.stat().st_mtime)
        for path in files[:-1500]:
            path.unlink(missing_ok=True)
    except Exception:
        app.logger.exception("Range collection failed")
        if "result" not in job:
            update(job, state="failed", error="Collection interrupted. Please retry.", finished=time.monotonic())


@app.after_request
def cors(response):
    origin = request.headers.get("Origin")
    if origin and origin == os.environ.get("STATIC_ORIGIN"):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Vary"] = "Origin"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/")
def dashboard():
    return send_from_directory(PUBLIC, "index.html")


@app.get("/api/health")
def health():
    return jsonify(service="gdelt-range-v1")


@app.post("/api/jobs")
def submit():
    data = request.get_json(silent=True)
    try:
        if not isinstance(data, dict):
            raise ValueError("Send a JSON date range.")
        first, last = parse_dates(data.get("start"), data.get("end"))
    except (TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400
    key = f"{first}_{last}"
    with lock:
        for k,j in list(jobs.items()):
            ttl = 60 if j["state"]=="failed" or any("error" in b[s] for b in j.get("result",{}).get("batches",[]) for s in ("events","mentions")) else 3600
            if j.get("finished", float("inf")) + ttl < time.monotonic():
                del jobs[k]
        if key not in jobs:
            if sum("finished" not in j for j in jobs.values()) >= 4:
                return jsonify(error="Queue is full. Retry after a current job finishes."), 429
            if len(jobs)>=12:
                oldest=min((k for k in jobs if "finished" in jobs[k]),key=lambda k:jobs[k]["finished"])
                del jobs[oldest]
            j = dict(state="queued", done=0,total=(last-first).days+1,metadata="pending")
            jobs[key]=j
            worker.submit(collect_range, j, first, last)
    return jsonify(id=key), 202


@app.get("/api/jobs/<key>")
@app.get("/api/jobs/<key>/<part>")
def get_job(key, part=None):
    with lock:
        job = jobs.get(key)
        if job is None:
            return jsonify(error="Job expired or service restarted. Submit the range again."), 404
        if part is None:
            return jsonify({k:job[k] for k in ("state","done","total","metadata","error") if k in job})
        if part not in ("result","previews"):
            abort(404)
        if part not in job:
            return jsonify(error="Result pending."), 409
        return jsonify(job[part])
