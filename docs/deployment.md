# Deploy and refresh

## Render Static Site

Connect the GitHub repository from **New → Static Site** in Render. Use the following settings for this repository layout.

| Setting | Value |
|---|---|
| Branch | `main` |
| Root Directory | Leave blank |
| Build Command | `test -s public/index.html` |
| Publish Directory | `public` |

Create the static site. Once live, open its assigned HTTPS URL and verify that Overview shows the total records and Map displays the sample. Render serves only the public folder. The default site URL is publicly accessible, including when the Git repository is private. Analyst reviews remain in browser storage. [Render Static Sites](https://render.com/docs/static-sites)

## Local development and data refresh

Edit `src/template.html` for durable interface changes. From the repository root, generate a new snapshot with Python 3.9+ and internet access:

```powershell
python src/collect.py --end 2026-11-21
```

The end is exclusive. This example reproduces the bundled window using the current archive bytes. Inspect the collector output for missing batches, open the generated public/index.html, and check the archive ledger before committing. Commit the template or collector changes along with the regenerated public/index.html. A push to the connected branch updates the hosted dashboard when Render auto-deploy is enabled.

To publish a prebuilt update supplied as a single index.html, replace public/index.html and commit. Keep the corresponding source template in sync before the next data refresh.

## Date ranges and on-demand archives

The static dashboard can filter the embedded 92-day snapshot without a backend. To enable fresh archive requests, deploy the included render.yaml using New → Blueprint and select this repository and branch. It defines one free Python web service. Its root URL serves the same dashboard and its /api/health endpoint returns a JSON service identifier. The dashboard at this new URL uses the collector on the same origin immediately.

To retain the existing static-site URL, set STATIC_ORIGIN on the collector to the exact HTTPS origin of your existing static site (no trailing slash). Add public/collector.json to the repository with the actual new web service origin, for example:

```json
{"origin":"https://YOUR-COLLECTOR.onrender.com"}
```

Commit the configuration and allow the static site to redeploy. The file contains only the public service address. Analyst reviews stay on the existing browser origin. If you switch to the new service URL, export and import reviews to move them.

For local development, from the repository root on Windows:

```powershell
python -m pip install Flask
python -m flask --app src/service.py run --port 8765
```

Open http://127.0.0.1:8765. For Linux deployment use the gunicorn command in render.yaml. Use one worker process because job state is in memory. An instance restart clears jobs. Resubmit the same range to recover. Complete daily batches are written atomically to CACHE_DIR (default /tmp/gdelt-day-cache). Render free disk is ephemeral. A mounted disk on a suitable plan can preserve completed days across restarts. The cache retains up to 1,500 daily batches. Preview metadata is best effort and may take longer than event collection. Polling an active job keeps the interface informed; closing the tab requires submitting the same dates to reattach. Empty, missing and partial days remain visible in the archive ledger.


Full-range jobs use SQLite under CACHE_DIR/full-ranges-v1. Each available quarter-hour export is committed separately with its matched mentions, provenance and screening inputs. Completed slots can be reused when the same dates are resubmitted while the files remain available. The service keeps recent ranges and limits concurrent collection. Capacity depends on disk space and upstream availability. A disk or collection failure is reported as an interruption. For long ranges, use a collector with sufficient disk space. The original sampler and snapshot rebuild continue to use their existing format.
