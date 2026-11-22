"""Read publisher metadata from GDELT's public archive. Never visit source URLs."""
import concurrent.futures
import datetime as dt
import gzip
import html
import io
import re
import zipfile
import json
from urllib.error import HTTPError
from urllib.request import urlopen

BASE = 'https://data.gdeltproject.org/gdeltv3/gemg/'


def text(value, limit):
    if not isinstance(value, str):
        return ''
    cleaned = ' '.join(html.unescape(value).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(' ', 1)[0] + '…'


def read_minute(stamp, urls):
    url = BASE + stamp + '.gemg.json.gz'
    found = {}
    try:
        with urlopen(url, timeout=18) as response, gzip.GzipFile(fileobj=response) as stream:
            for line in stream:
                row = json.loads(line)
                if row.get('url') not in urls:
                    continue
                meta = {str(m.get('key', '')).lower(): m.get('value') for m in row.get('metatags') or [] if isinstance(m, dict)}
                title = text(meta.get('og:title') or row.get('title'), 200)
                for key in ('og:description', 'description', 'twitter:description'):
                    description = text(meta.get(key), 280)
                    if description and description.casefold() != title.casefold():
                        break
                else:
                    description, key = '', ''
                if title or description:
                    found[row['url']] = dict(title=title, description=description, field=key, archive=url, captured=row.get('date',stamp))
    except HTTPError as exc:
        if exc.code != 404:
            print('Metadata archive unavailable:', stamp, exc.code, flush=True)
    except (OSError, ValueError, EOFError) as exc:
        print('Metadata archive incomplete:', stamp, type(exc).__name__, flush=True)
    return found


def archived_headlines(batch):
    """Use the contemporaneous GKG page title when no richer entry exists."""
    urls = {entry['raw'][60] for entry in batch['sample']}
    if not urls:
        return {}
    stamp = batch['stamp']
    url = f'https://data.gdeltproject.org/gdeltv2/{stamp}.gkg.csv.zip'
    found = {}
    try:
        with urlopen(url, timeout=20) as response:
            archive = io.BytesIO(response.read())
        with zipfile.ZipFile(archive) as z, z.open(z.namelist()[0]) as stream:
            for line in stream:
                fields = line.decode('utf-8','replace').rstrip().split('\t')
                if len(fields) < 27 or fields[4] not in urls:
                    continue
                match = re.search(r'<PAGE_TITLE>(.*?)</PAGE_TITLE>', fields[26])
                if match and match[1].strip():
                    found[fields[4]] = dict(title=text(match[1],200),description='',field='PAGE_TITLE',
                                            archive=url,captured=stamp+' UTC')
    except (OSError, ValueError, EOFError, zipfile.BadZipFile) as exc:
        print('Headline archive unavailable:', stamp, type(exc).__name__, flush=True)
    return found


def enrich(batches, cancelled=lambda: False):
    jobs = []
    for b in batches:
        urls = {x['raw'][60] for x in b['sample'] if x['raw'][60]}
        if not urls:
            continue
        stamp = dt.datetime.strptime(b['stamp'], '%Y%m%d%H%M%S')
        for offset in (-15, -14, -13, -12, 0, 1, 2, 3):
            minute = stamp + dt.timedelta(minutes=offset)
            jobs.append((minute.strftime('%Y%m%d%H%M%S'), urls))
    previews = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for result in pool.map(lambda b: {} if cancelled() else archived_headlines(b), batches):
            previews.update(result)
        for result in pool.map(lambda pair: {} if cancelled() else read_minute(*pair), jobs):
            for url, preview in result.items():
                if url not in previews or (preview['description'] and not previews[url]['description']):
                    previews[url] = preview
    return previews

