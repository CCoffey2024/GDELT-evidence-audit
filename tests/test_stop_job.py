"""Cancellation and preflight checks without downloading public archives."""
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import service


class JobControlTest(unittest.TestCase):
    def test_stop_running_range_and_queued_sample(self):
        started, release = threading.Event(), threading.Event()
        def block(stamp):
            started.set()
            release.wait(5)
            return {"stamp":stamp,"day":"2026-01-03","events":{},"mentions":{},"sample":[]}
        dates = {"start":"2026-01-03","end":"2026-01-03"}
        c = service.app.test_client()
        with tempfile.TemporaryDirectory() as folder, patch.object(service, "FULL_CACHE", Path(folder)), patch("full_range.full_batch",side_effect=block) as fetch:
            path = "/api/estimate?start=2026-01-03&end=2026-01-03"
            self.assertEqual(c.get(path).json, {"processed":0,"rows":0})
            fetch.assert_not_called()
            full = c.post("/api/ranges",json=dates).json
            try:
                self.assertTrue(started.wait(2))
                for kind in ("jobs","ranges"):
                    job = c.post("/api/jobs",json=dates).json if kind=="jobs" else full
                    endpoint = f'/api/{kind}/{job["id"]}'
                    self.assertEqual(c.post(endpoint+"/stop",json={"token":"wrong"}).status_code,403)
                    response = c.post(endpoint+"/stop",json={"token":job["stopToken"]})
                    self.assertEqual(response.json["state"],"stopped" if kind=="jobs" else "stopping")
                    self.assertNotIn("token",c.get(endpoint).json)
            finally:
                release.set()
                service.full_jobs[full["id"]]["future"].result(timeout=5)
            self.assertEqual(c.get(endpoint).json["state"],"stopped")
            self.assertLessEqual(fetch.call_count,3)


if __name__=="__main__":
    unittest.main()
