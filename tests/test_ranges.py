import datetime as dt
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import service


class RangeTests(unittest.TestCase):
    def test_validation(self):
        for pair in [('2026-11-01','2026-10-31'),('2014-01-01','2014-01-01'),
                     ('2020-01-01','2020-03-31'),('2099-01-01','2099-01-01')]:
            with self.assertRaises(ValueError):
                service.parse_dates(*pair)
        self.assertEqual(service.parse_dates('2020-01-01','2020-03-30')[1],dt.date(2020,3,30))

    def test_overlap_failure_and_retry(self):
        c=service.app.test_client()
        calls=[]
        def fake(d):
            calls.append(d.day)
            manifest={'error':'unavailable'} if d.day==3 else {'rows':1}
            return dict(day=str(d),stamp=d.strftime('%Y%m%d')+'000000',sample=[],
                        events=manifest,mentions={'rows':0})
        def result(first,last):
            response=c.post('/api/jobs',json=dict(start=first,end=last))
            self.assertEqual(response.status_code,202)
            path='/api/jobs/'+response.json['id']
            for _ in range(200):
                state=c.get(path).json
                if state['metadata']=='complete' or state['state']=='failed':
                    return path,state
                time.sleep(.01)
            self.fail('Job did not finish')
        with tempfile.TemporaryDirectory() as temp, patch.object(service,'CACHE',Path(temp)), patch.object(service,'day_sample',fake), patch.object(service,'enrich',return_value={}):
            with service.lock:service.jobs.clear()
            a,state=result('2020-02-01','2020-02-02')
            b,state=result('2020-02-02','2020-02-03')
            self.assertEqual(c.get(b+'/result').json['end'],'2020-02-04')
            self.assertEqual(c.get(b+'/result').json['batches'][1]['events']['error'],'unavailable')
            self.assertCountEqual(calls,[1,2,3])
            self.assertEqual(result('2020-02-02','2020-02-03')[0],b)
            self.assertEqual(len(calls),3)
            self.assertEqual(result('2020-02-03','2020-02-03')[1]['state'],'failed')
            self.assertEqual(calls.count(3),2)
