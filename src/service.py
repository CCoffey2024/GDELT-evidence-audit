"""Public, single-process date-range collector with bounded background work."""
import datetime as dt
import json
import os
import secrets
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
        if job.get("cancelled"):
            return
        job.update(values)


def mark_stopped(job):
    with lock:
        job.update(state="stopped", finished=time.monotonic())


def run_collection(job, operation, *args):
    try:
        operation(job, *args)
    finally:
        with lock:
            if job.get("cancelled") and not job.get("preview_assigned"):
                mark_stopped(job)



def add_previews(job, batches):
    try:
        previews = enrich(batches, lambda: job.get("cancelled", False))
        update(job, previews=previews, metadata="complete")
    except Exception:
        app.logger.exception("Metadata collection failed")
        update(job, metadata="unavailable")
    finally:
        with lock:
            if job.get("cancelled"):
                mark_stopped(job)
            else:
                update(job, finished=time.monotonic())


def collect_range(job, first, last):
    try:
        update(job, state="collecting")
        days = [first + i*DAY for i in range(job["total"])]
        batches = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            for batch in pool.map(lambda day: None if job.get("cancelled") else daily(day), days):
                if job.get("cancelled"):
                    return
                batches.append(batch)
                update(job, done=len(batches))
        if all("error" in b["events"] for b in batches):
            update(job, state="failed", error="All selected event archives were unavailable.",
                   finished=time.monotonic())
            return
        result = dict(start=str(first), end=str(last+DAY), seed=SEED, batches=batches,
                      collected=dt.datetime.now(dt.timezone.utc).isoformat())
        with lock:
            if job.get("cancelled"):
                return
            update(job, result=result, state="ready", metadata="collecting")
            job["preview_assigned"] = True
            job["future"] = preview_worker.submit(add_previews, job, batches)
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
        if key not in jobs or jobs[key]["state"] == "stopped":
            if sum("finished" not in j for j in jobs.values()) >= 4:
                return jsonify(error="Queue is full. Retry after a current job finishes."), 429
            if len(jobs)>=12:
                oldest=min((k for k in jobs if "finished" in jobs[k]),key=lambda k:jobs[k]["finished"])
                del jobs[oldest]
            j = dict(state="queued", done=0,total=(last-first).days+1,metadata="pending")
            jobs[key]=j
            j["token"] = secrets.token_urlsafe(24)
            j["future"] = worker.submit(run_collection, j, collect_range, first, last)
            return jsonify(id=key, stopToken=j["token"]), 202
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


# Full ranges use a separate disk-backed format from the historical sampler.
from flask import Response
from full_range import collect_all, export_rows, read_batch

FULL_CACHE = CACHE.parent / "full-ranges-v1"
FULL_CACHE.mkdir(parents=True, exist_ok=True)
full_jobs = {}


@app.post("/api/ranges")
def submit_full():
    data = request.get_json(silent=True)
    try:
        if not isinstance(data, dict):
            raise ValueError("Send a JSON date range.")
        first, last = parse_dates(data.get("start"), data.get("end"))
    except (TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400
    key = f"{first}_{last}"
    with lock:
        current = full_jobs.get(key)
        if current and (current["state"] not in ("failed","ready","stopped") or
                        (current["state"] == "ready" and not current.get("gaps"))):
            return jsonify(id=key), 202
        if sum(j["state"] in ("queued","collecting","screening","stopping") for j in full_jobs.values()) >= 2:
            return jsonify(error="Two full ranges are already in progress. Retry shortly."), 429
        # Retain recent ranges; never evict an active collection.
        files = sorted(FULL_CACHE.glob("*.sqlite"), key=lambda p:p.stat().st_mtime, reverse=True)
        for old in files[2:]:
            if old.stem != key and full_jobs.get(old.stem,{}).get("state") not in ("queued","collecting","screening","stopping"):
                old.unlink(missing_ok=True)
                full_jobs.pop(old.stem,None)
        job = dict(state="queued", done=0, total=((last-first).days+1)*96, rows=0)
        full_jobs[key] = job
        job["token"] = secrets.token_urlsafe(24)
        job["future"] = worker.submit(run_collection, job, collect_all, first, last, FULL_CACHE / (key+".sqlite"), update)
        return jsonify(id=key, stopToken=job["token"]), 202
    return jsonify(id=key), 202


@app.get("/api/ranges/<key>")
@app.get("/api/ranges/<key>/<part>")
def full_result(key, part=None):
    with lock:
        job = full_jobs.get(key)
        if job is None:
            return jsonify(error="Submit this range again to resume collection."), 404
        if part is None:
            return jsonify({k:v for k,v in job.items() if k in ("state","done","total","rows","error","counts","gaps")})
        if job["state"] != "ready":
            return jsonify(error="Collection is in progress."), 409
        if part == "manifest":
            return jsonify(job["slots"])
    path = FULL_CACHE / (key+".sqlite")
    if part == "events.tsv":
        return Response(export_rows(path), mimetype="text/tab-separated-values",
                        headers={"Content-Disposition":f'attachment; filename="gdelt-events-{key}.tsv"'})
    batch = read_batch(path, part)
    if batch is None:
        abort(404)
    return jsonify(batch)

# Enrich only the archive an analyst opens. Large ranges can contain thousands.
archive_previews = {}


@app.get("/api/ranges/<key>/previews/<stamp>")
def full_previews(key, stamp):
    with lock:
        if full_jobs.get(key, {}).get("state") != "ready":
            return jsonify(error="Range is unavailable."), 404
        future = archive_previews.get(stamp)
        if future is None:
            if sum(not f.done() for f in archive_previews.values()) >= 2:
                return jsonify(state="busy")
            batch = read_batch(FULL_CACHE / (key+".sqlite"), stamp)
            if batch is None:
                abort(404)
            for old in list(archive_previews):
                if len(archive_previews) < 6:
                    break
                if archive_previews[old].done():
                    del archive_previews[old]
            future = archive_previews[stamp] = preview_worker.submit(enrich, [batch])
        if not future.done():
            return jsonify(state="collecting")
        if future.exception():
            del archive_previews[stamp]
            return jsonify(state="unavailable")
        return jsonify(state="complete", previews=future.result())


@app.post("/api/<kind>/<key>/stop")
def stop_collection(kind, key):
    registry = {"jobs": jobs, "ranges": full_jobs}.get(kind)
    data = request.get_json(silent=True) or {}
    with lock:
        job = registry.get(key) if registry is not None else None
        if job is None:
            abort(404)
        token = data.get("token") if isinstance(data, dict) else None
        if not isinstance(token, str) or not secrets.compare_digest(job["token"], token):
            return jsonify(error="Only the browser that started this job can stop it."), 403
        if "finished" not in job and (job["state"] != "ready" or job.get("metadata") == "collecting"):
            job.update(cancelled=True,state="stopping")
            if job["future"].cancel():
                mark_stopped(job)
        return jsonify(state=job["state"])


@app.get("/api/estimate")
def estimate_range():
    try:
        first, last = parse_dates(request.args.get("start"), request.args.get("end"))
    except (TypeError, ValueError) as exc:
        return jsonify(error=str(exc)), 400
    with lock:
        job = full_jobs.get(f"{first}_{last}", {})
        if job.get("state") == "ready":
            missing = sum(bool(gap & 1) for _, _, gap in job["slots"])
            if not missing:
                return jsonify(exact=job["rows"])
        return jsonify(processed=job.get("done",0), rows=job.get("rows",0))
