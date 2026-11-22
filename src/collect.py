"""Rebuild the published sample using Python 3.9+ and the GDELT public archive."""
import argparse
import calendar
import concurrent.futures
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
from article_previews import enrich
import time
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parent
SEED = 'bluelens-gdelt-v1'
BASE = 'https://data.gdeltproject.org/gdeltv2/'
def rank(value):
    return hashlib.sha256((SEED + '|' + value).encode()).hexdigest()

def archive(stamp, kind, width):
    url = BASE + stamp + '.' + kind + '.CSV.zip'
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent':'GDELT academic audit/1.0'}), timeout=25) as response:
                data = response.read()
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                member = stamp + '.' + kind + '.CSV'
                lines = z.read(member).decode('utf-8').splitlines()
            rows = [l.split('\t') for l in lines]
            if any(len(r) != width for r in rows):
                raise ValueError('Unexpected column count')
            return rows, dict(url=url, sha256=hashlib.sha256(data).hexdigest(), rows=len(rows), member=member)
        except Exception as exc:
            if attempt == 2:
                return [], dict(url=url,error=str(exc))
            time.sleep(1 + attempt)

def day_sample(day):
    slot = int(rank('slot|' + str(day)),16) % 96
    stamp = day.strftime('%Y%m%d') + f'{slot//4:02}{slot%4*15:02}00'
    rows, events = archive(stamp,'export',61)
    selected = sorted(rows, key=lambda r: rank(stamp+'|'+r[0]))[:12]
    matches = {r[0]:[] for r in selected}
    mentions, manifest = archive(stamp,'mentions',16)
    for m in mentions:
        if m[0] in matches:
            matches[m[0]].append(m)
    return dict(day=str(day),stamp=stamp,events=events,mentions=manifest,
                sample=[dict(raw=r,mentions=matches[r[0]]) for r in selected])

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--end',default='2026-11-21',help='Exclusive UTC end, YYYY-MM-DD')
    end = dt.date.fromisoformat(p.parse_args().end)
    month = end.month - 3
    year = end.year - (month <= 0)
    month = (month-1)%12+1
    start = end.replace(year=year,month=month,day=min(end.day,calendar.monthrange(year,month)[1]))
    days = [start+dt.timedelta(i) for i in range((end-start).days)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        batches = list(pool.map(day_sample,days))
    data = dict(start=str(start),end=str(end),seed=SEED,collected=dt.datetime.now(dt.timezone.utc).isoformat(),batches=batches)
    if not any(b['sample'] for b in batches):
        raise SystemExit('No event data retrieved. Existing dashboard preserved.')
    data['previews'] = enrich(batches)
    template = (ROOT/'template.html').read_text(encoding='utf-8')
    result = template.replace('/*DATASET*/null',json.dumps(data,separators=(',',':')).replace('<','\\u003c'))
    tmp = ROOT.parent/'public'/'index.tmp'
    tmp.write_text(result,encoding='utf-8')
    os.replace(tmp,ROOT.parent/'public'/'index.html')
    print('Rows',sum(len(b['sample']) for b in batches),'missing archives',[(b['stamp'],k) for b in batches for k in ('events','mentions') if 'error' in b[k]])
if __name__=='__main__':
    main()
