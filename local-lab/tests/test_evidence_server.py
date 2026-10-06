"""Exercise real HTTP behavior against isolated test-only directories."""
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from explore_evidence import EvidenceStore, create_server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "evidence"
        self.root.mkdir()
        self.server = create_server(self.root, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_missing_evidence_is_explicit_and_assets_load(self):
        with urllib.request.urlopen(self.url + "/api/status") as response:
            self.assertEqual(json.load(response)["state"], "missing")
        with urllib.request.urlopen(self.url + "/") as response:
            self.assertEqual(response.status, 200)
            self.assertIn("Table state explorer", response.read().decode())

    def test_no_arbitrary_files_or_write_endpoint(self):
        for path in ["/../../etc/passwd", "/%2e%2e/%2e%2e/etc/passwd", "/api/runs/../../manifest.json"]:
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)
        request = urllib.request.Request(self.url + "/api/status", data=b"{}", method="POST")
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(request)
        self.assertEqual(error.exception.code, 405)

    def test_symlink_cannot_escape_evidence_root(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "manifest.json").write_text('{"private":"test-only"}')
        runs = self.root / "runs"
        runs.mkdir()
        run_id = "olist_20261006T000000Z_abcdef12"
        (runs / run_id).symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "escapes"):
            EvidenceStore(self.root).read(run_id, "manifest.json")

    def test_invalid_current_pointer_reports_unavailable(self):
        (self.root / "current.json").write_text('{"run_id":"../../private"}')
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.url + "/api/status")
        self.assertEqual(error.exception.code, 503)

    def test_metadata_integers_keep_exact_digits_for_browser(self):
        run_id = "olist_20261006T000000Z_abcdef12"
        run = self.root / "runs" / run_id
        run.mkdir(parents=True)
        capture = {"formats": [], "metadata": {"snapshot_id": 4455204442159578763,
                   "negative_long": -9223372036854775808, "count": 107, "valid": True}}
        path = run / "create.json"
        path.write_text(json.dumps(capture))
        with urllib.request.urlopen(self.url + f"/api/runs/{run_id}/stages/create") as response:
            served = json.load(response)
        self.assertEqual(served["metadata"]["snapshot_id"], "4455204442159578763")
        self.assertEqual(served["metadata"]["negative_long"], "-9223372036854775808")
        self.assertEqual(served["metadata"]["count"], 107)
        self.assertIs(served["metadata"]["valid"], True)
        self.assertEqual(json.loads(path.read_text()), capture)


if __name__ == "__main__":
    unittest.main()
