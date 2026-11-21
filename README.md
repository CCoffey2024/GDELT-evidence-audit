# GDELT Evidence Audit

**BlueLens Analytics** · Media provenance and geospatial data quality

How much can an analyst infer from a machine-coded news event? This dashboard lets you follow a GDELT event back to the reporting, inspect the geographic precision, and document which parts of the claim the evidence supports.

**[Analyst guide](docs/analyst-guide.md) · [Sampling and screening](docs/methods.md) · [Deploy and refresh](docs/deployment.md)**

## Open the dashboard

Download or clone the repository and double-click `public/index.html`. The event sample, Leaflet map, basemap, and screening rules load locally. Article and archive links require internet access.

## A five-minute walkthrough

1. Open **Overview** and select **Repeated coded claim**. Each candidate links to the other sampled IDs that matched the rule.
2. Open **Map** and choose **Repeated coded claims**. The bundled sample resolves to six records at three coordinates. Select a marker, then an event ID to compare the reporting.
3. In **Record explorer**, inspect the action, actors, event date, place, and linked mentions. Save your field judgments and cite any independent evidence.
4. Open **Analyst reviews** for field-specific agreement and access counts, or export review decisions for a colleague.

## Inside the bundled sample

| Archive window (UTC) | Sampled events | Same-batch mentions | Mapped records | Distinct coordinates |
|---|---:|---:|---:|---:|
| August 21 through November 20, 2026 | 1,104 | 1,151 | 1,074 | 568 |

The sample uses one quarter-hour archive per day. A flag tells you why a record merits inspection. Estimating an error rate requires a defined review protocol and documented judgments.

## Repository layout

| Path | Purpose |
|---|---|
| `public/index.html` | Ready-to-serve dashboard and current snapshot |
| `src/template.html` | Editable interface, embedded map assets, and screening rules |
| `src/collect.py` | Reproducible sampler and dashboard generator |
| `docs/` | Analyst workflow, methodology, and hosting instructions |

## Data and map credits

Event and Mention archives and CAMEO labels come from the GDELT Project. The map uses Leaflet and Natural Earth 1:110m country boundaries. Each underlying publisher is identified by the source URL in the event record. [GDELT documentation](https://www.gdeltproject.org/data.html) · [Leaflet](https://leafletjs.com/) · [Natural Earth](https://www.naturalearthdata.com/)
