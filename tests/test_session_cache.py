import json
from pathlib import Path
import sys
import tempfile
import unittest


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
sys.path.insert(0, str(APP_DIR))

from main import TransitRequestHandler  # noqa: E402
from session_cache import SessionCache, validate_session_id  # noqa: E402


class SessionCacheTests(unittest.TestCase):
    def test_round_trip_uses_one_atomic_json_file_per_session(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = SessionCache(directory=directory, max_bytes=1024 * 1024)
            state = {
                "current_batch_index": 0,
                "current_view": "stack",
                "results": [{"file_name": "wasp43.csv", "result": {"transits": [1, 2]}}],
            }

            saved = cache.save("session_12345678", state)
            loaded = cache.load("session_12345678")

            cache_path = Path(saved["cache_file"])
            self.assertEqual(cache_path.parent, Path(directory).resolve())
            self.assertEqual(cache_path.name, "session-session_12345678.json")
            self.assertEqual(loaded["state"], state)
            self.assertEqual(loaded["schema_version"], 1)
            json.dumps(loaded)
            self.assertEqual(list(Path(directory).glob("*.tmp")), [])

    def test_missing_session_returns_none(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = SessionCache(directory=directory)
            self.assertIsNone(cache.load("missing_12345678"))

    def test_invalid_ids_cannot_escape_cache_directory(self):
        for value in ("../outside", "short", "abc/defgh", "contains space"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_session_id(value)

    def test_session_route_parser_accepts_only_safe_ids(self):
        self.assertEqual(
            TransitRequestHandler.analysis_session_id("/analysis-sessions/abc12345_def"),
            "abc12345_def",
        )
        self.assertIsNone(TransitRequestHandler.analysis_session_id("/analysis-sessions/../secret"))
        self.assertIsNone(TransitRequestHandler.analysis_session_id("/analysis-sessions/short"))

    def test_frontend_creates_restorable_url_sessions(self):
        index_html = (APP_DIR / "static" / "index.html").read_text()
        app_js = (APP_DIR / "static" / "app.js").read_text()

        self.assertIn('aria-label="Application version 59">v59</span>', index_html)
        self.assertIn('id="sessionIndicator"', index_html)
        self.assertIn("function ensureSessionId()", app_js)
        self.assertIn("function restoreSessionState(state)", app_js)
        self.assertIn("sessionReadyPromise = initializeSession();", app_js)
        self.assertIn("/analysis-sessions/", app_js)


if __name__ == "__main__":
    unittest.main()
