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
