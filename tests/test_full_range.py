import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import full_range as full


class RangeTest(unittest.TestCase):
    def test_all_slots_rows_cross_archive_screening_and_resume(self):
        day = dt.date(2026, 1, 1)
        slots = list(full.stamps(day, day))
        self.assertEqual(len(slots), 96)
        self.assertTrue(slots[-1].endswith("234500"))
        missed = slots[35]

        def fixture(stamp):
            items = []
            for i in range(13):
                row = [""]*61
                row[0] = stamp+str(i)
                row[1], row[6], row[51], row[56], row[57] = "20260101","actor","3","1","2"
                row[60] = "https://news.example/"+("shared" if i == 0 else row[0])
                items.append(dict(raw=row, mentions=[[""]*16]))
            return dict(stamp=stamp, day=str(day), events={}, mentions={}, sample=items)

        def fetch(stamp):
            b = fixture(stamp)
            if stamp == missed:
                b.update(events={"error":"missing"},sample=[])
            return b

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"range.sqlite"
            job = {}
            with patch.object(full,"full_batch",side_effect=fetch):
                full.collect_all(job, day, day, path, dict.update)
            self.assertEqual(job["counts"], (1235,95,95,0,0))
            self.assertEqual(job["gaps"], 1)
            with patch.object(full,"full_batch",side_effect=fixture) as retry:
                full.collect_all(job, day, day, path, dict.update)
                retry.assert_called_once_with(missed)
            self.assertEqual(job["counts"], (1248,96,96,0,0))
            self.assertEqual(len(full.read_batch(path,missed)["sample"]),13)
            self.assertEqual(sum(len(lines.splitlines()) for lines in full.export_rows(path)),1248)


if __name__ == "__main__":
    unittest.main()
