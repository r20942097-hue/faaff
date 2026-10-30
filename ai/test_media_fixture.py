import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai.media_fixture import inspect, probe, sha256

class SyntheticMediaTests(unittest.TestCase):
    def test_hash_matches_exact_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data"
            path.write_bytes(b"abc")
            self.assertEqual(sha256(path), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    @patch("ai.media_fixture.shutil.which", return_value=None)
    def test_missing_tool_fails_closed(self, unused):
        result = inspect()
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["release_readiness"], "NO_GO")

    @patch("ai.media_fixture.command")
    def test_audio_absence_is_failure(self, command):
        from subprocess import CompletedProcess
        command.return_value = CompletedProcess([], 0, stdout=json.dumps({
            "streams": [{"codec_type": "video", "codec_name": "mpeg2video", "nb_read_packets": "5"}]
        }))
        with self.assertRaisesRegex(ValueError, "MISSING_AUDIO"):
            probe("dummy.ts")

    def test_synthetic_fixture_is_not_product_acceptance(self):
        from ai.media_fixture import inspect
        result = inspect()
        if result["status"] != "PASS":
            self.skipTest("ffmpeg/ffprobe encoders unavailable on this runner")
        self.assertEqual(result["full_decode"], "PASS")
        self.assertEqual(result["product_recording_e2e"], "NOT_RUN")
        self.assertEqual(result["release_readiness"], "NO_GO")

if __name__ == "__main__":
    unittest.main()
