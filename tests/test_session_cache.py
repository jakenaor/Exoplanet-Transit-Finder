import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
sys.path.insert(0, str(APP_DIR))

from main import TransitRequestHandler  # noqa: E402
from session_cache import SessionCache, SessionCacheManager, validate_session_id  # noqa: E402


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
        self.assertEqual(
            TransitRequestHandler.analysis_session_location_id(
                "/analysis-sessions/abc12345_def/location"
            ),
            "abc12345_def",
        )

    def test_custom_location_moves_cache_and_survives_manager_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            default_directory = root / "default"
            custom_directory = root / "custom results"
            session_id = "moveme_12345678"
            state = {"current_view": "stack", "results": []}
            manager = SessionCacheManager(default_directory=default_directory)
            original = Path(manager.save(session_id, state)["cache_file"])

            relocated = manager.relocate(session_id, str(custom_directory))

            relocated_path = Path(relocated["cache_file"])
            self.assertTrue(relocated["moved"])
            self.assertFalse(original.exists())
            self.assertTrue(relocated_path.is_file())
            restarted_manager = SessionCacheManager(default_directory=default_directory)
            self.assertEqual(restarted_manager.directory_for(session_id), custom_directory.resolve())
            self.assertEqual(restarted_manager.load(session_id)["state"], state)

    def test_custom_location_rejects_relative_and_root_paths(self):
        with self.assertRaisesRegex(ValueError, "absolute path"):
            SessionCacheManager.validate_directory("relative/folder")
        with self.assertRaisesRegex(ValueError, "filesystem root"):
            SessionCacheManager.validate_directory("/")

    def test_manager_lists_default_and_custom_caches_newest_first(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = SessionCacheManager(default_directory=root / "default")
            older_id = "older_12345678"
            newer_id = "newer_12345678"
            older_path = Path(manager.save(older_id, {"results": []})["cache_file"])
            manager.save(newer_id, {"results": []})
            newer_path = Path(
                manager.relocate(newer_id, str(root / "custom"))["cache_file"]
            )
            os.utime(older_path, (1_000, 1_000))
            os.utime(newer_path, (2_000, 2_000))

            sessions = manager.list_sessions()

            self.assertEqual([item["session_id"] for item in sessions], [newer_id, older_id])
            self.assertEqual(Path(sessions[0]["cache_file"]), newer_path)
            self.assertEqual(Path(sessions[1]["cache_file"]), older_path)
            self.assertTrue(all(item["loadable"] for item in sessions))

    def test_frontend_creates_restorable_url_sessions(self):
        index_html = (APP_DIR / "static" / "index.html").read_text()
        app_js = (APP_DIR / "static" / "app.js").read_text()

        self.assertIn('aria-label="Application version 62">v62</span>', index_html)
        self.assertIn('id="sessionIndicator"', index_html)
        self.assertIn('id="saveLocationHeading">Save File Location</h2>', index_html)
        self.assertIn('id="saveLocationInput"', index_html)
        self.assertIn('id="saveLocationButton" type="submit">Apply</button>', index_html)
        self.assertIn('id="loadCacheHeading">Load Cache</h2>', index_html)
        self.assertIn('id="cacheSelect"', index_html)
        self.assertIn('id="loadCacheButton"', index_html)
        self.assertIn('id="refreshCachesButton"', index_html)
        self.assertIn("function ensureSessionId()", app_js)
        self.assertIn("function setSaveFileLocation(directory, cacheFile = '')", app_js)
        self.assertIn("/location`,", app_js)
        self.assertIn("function restoreSessionState(state)", app_js)
        self.assertIn("async function refreshSessionCacheList()", app_js)
        self.assertIn("window.location.assign", app_js)
        self.assertIn("sessionReadyPromise = initializeSession();", app_js)
        self.assertIn("/analysis-sessions/", app_js)


if __name__ == "__main__":
    unittest.main()
