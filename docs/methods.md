# Sampling and screening

## Sampling frame

The exclusive UTC end date defines a three-calendar-month ingest window. For each day, a seeded SHA-256 hash selects one of 96 quarter-hour batches. Within the batch, event IDs are ranked by their timestamp-and-ID hashes and up to 12 records are retained. The seed and hashing inputs are in the collector. The ledger preserves archive URLs, compressed-file hashes, and acquisition failures. Failed slots receive no replacement.

Mentions are joined by GlobalEventID within the same quarter-hour. Later reporting can add mentions outside the sample. A coded event date can precede the ingest window. Similar sample sizes per day give low-volume and high-volume days similar weight.

## Reading the flags

| Check family | Example trigger | Interpretation |
|---|---|---|
| Redundancy | Same article, coded date, action, ordered named actors, and action location | Compare both records and the source passage before counting distinct incidents. |
| Geography | Country or administrative-area coding | A plotted coordinate represents an area. Site-level inference needs more precise evidence. |
| Timing | Coded date at least 30 days before ingest | Look for historical references or date attribution problems. |
| Extraction | All available numeric same-batch mention confidence values below 50 | The threshold is an audit choice. It has no calibrated probability interpretation. |
| Provenance | Missing source URL or matching same-batch mention | Record the evidence gap and its scope. |

The dashboard displays every rule and its triggering evidence. A record can trigger several rules, so category counts overlap. A clear screen means only that no configured check fired.

## Reporting accuracy

Field agreement is supported divided by supported plus contradicted for that field. Include the numerator, denominator, and counts of unclear, inapplicable, and unassessed fields. Self-selected reviews can overrepresent unusual cases. Measuring missed incidents requires an independently assembled incident list and a separate matching exercise.
