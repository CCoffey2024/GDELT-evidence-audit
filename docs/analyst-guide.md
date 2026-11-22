# Analyst guide

## Triage a batch

Open Overview. Select a metric or a rule count to open its matching records. Records are ordered by the combined weights of their flags. Export batch CSV for a spreadsheet with one row per event, including unflagged events. The provenance tab exports the archive ledger.

## Investigate a place

On Map, use the geographic precision colors to identify country, administrative-area, and locality coding. Marker size reflects records sharing identical coordinates. Switch to redundancy colors to see where repeated claims or shared sources occur. Select a marker and an event ID to inspect its evidence. The map displays the count of ungeocoded or otherwise unplottable records separately.

## Review a claim

Read the cached Article preview first. Selecting an event renders plain text bundled in the dashboard. The timestamp and metadata field identify where the headline or description came from. Some publishers supply only a headline or a generic description. Use the original link when you need article-level evidence. Record its availability, and identify the passage describing the action. Compare the action, each actor, the date, and the action location separately. Use **Unclear** when the available text cannot resolve a field. Cite separately sourced evidence for an independent judgment about whether the occurrence itself is supported. Several outlets may carry one wire report.

## Share work

Save the review with your name and evidence notes. Browser storage is specific to the device, browser profile, and site. Export review JSON before moving from a local file to a hosted URL. Import into the same sample on the destination. When imported decisions conflict, the dashboard retains existing decisions and reports the conflict count. Keep the original exports for adjudication.

Print the batch brief to describe screening outcomes, or print the analyst review overview to present human judgments and their denominators.

## Compare dates

Open **Date ranges** above any tab. Archive dates refer to UTC acquisition dates. Both bounds are inclusive. **Apply date filters** applies the selected archive dates and optional coded-event dates across the dashboard. Batch flags are recalculated for the selected rows. A record can also list related IDs elsewhere in the loaded sample. The map, CSV, archive ledger and review totals follow the active range. Review decisions persist by event ID; the review export includes only decisions in the current view.

To collect another period, select 1–90 completed UTC days and choose **Download records**. **All available event records** checks every quarter-hour export. The progress bar counts archive slots and the live count shows event rows. When collection finishes, the full-range cards include cross-archive article and syndication matches. Missing event or mention files appear in the archive selector. Submit the same dates again to retry gaps.

Use **Download all event rows (TSV)** to save the whole range. The headerless file contains an archive timestamp followed by the 61 GDELT event columns in their original order. Select a quarter-hour and choose **Open archive** to use the map, detailed checks, linked mentions, archived article previews and review tools for that archive. Archive-level duplicate indicators compare records within the open archive. **Quick sample** retains the original reproducible sampling workflow. **Return to original dataset** restores the bundled demonstration.
