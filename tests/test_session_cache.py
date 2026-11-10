import json as Json
import os as Os
from pathlib import Path
import sys as Sys
import tempfile as Tempfile
import unittest as Unittest


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
Sys.path.insert(0, str(APP_DIR))

from main import TransitRequestHandler  # noqa: E402
from session_cache import SessionCache, SessionCacheManager, ValidateSessionId  # noqa: E402


#MARK: cache files
class SessionCacheTests(Unittest.TestCase):
    def testRoundTripUsesOneAtomicJsonFilePerSession(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Cache = SessionCache(Directory=Directory, MaxBytes=1024 * 1024)
            State = {
                "current_batch_index": 0,
                "current_view": "stack",
                "results": [{"file_name": "wasp43.csv", "result": {
                    "period": 0.81347,
                    "transits": [{"start": 1.0, "center": 1.05, "end": 1.1}],
                    "plot": {"time": [0, 1, 2], "raw_flux": [1, .99, 1], "smooth_flux": [1, .99, 1]},
                }}],
            }

            Saved = Cache.save("session_12345678", State)
            Loaded = Cache.load("session_12345678")

            CachePath = Path(Saved["cache_file"])
            self.assertEqual(CachePath.parent, Path(Directory).resolve())
            self.assertEqual(CachePath.name, "session-session_12345678.json")
            Restored = Loaded["state"]
            self.assertEqual(Restored["current_view"], State["current_view"])
            Result = Restored["results"][0]["result"]
            self.assertEqual(Result["plot"], State["results"][0]["result"]["plot"])
            self.assertEqual(Result["transits"], State["results"][0]["result"]["transits"])
            self.assertIsNone(Result["provenance"]["analyzed_at"])
            self.assertEqual(Result["provenance"]["analysis_version"], "unknown")
            self.assertNotIn("provenance", State["results"][0]["result"])
            self.assertEqual(Loaded["schema_version"], 1)
            Json.dumps(Loaded)
            self.assertEqual(list(Path(Directory).glob("*.tmp")), [])

    def testMissingSessionReturnsNone(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Cache = SessionCache(Directory=Directory)
            self.assertIsNone(Cache.load("missing_12345678"))

    def testInvalidIdsCannotEscapeCacheDirectory(self):
        for Value in ("../outside", "short", "abc/defgh", "contains space"):
            with self.subTest(value=Value):
                with self.assertRaises(ValueError):
                    ValidateSessionId(Value)

    def testSessionRouteParserAcceptsOnlySafeIds(self):
        self.assertEqual(
            TransitRequestHandler.AnalysisSessionId("/analysis-sessions/abc12345_def"),
            "abc12345_def",
        )
        self.assertIsNone(TransitRequestHandler.AnalysisSessionId("/analysis-sessions/../secret"))
        self.assertIsNone(TransitRequestHandler.AnalysisSessionId("/analysis-sessions/short"))
        self.assertEqual(
            TransitRequestHandler.AnalysisSessionLocationId(
                "/analysis-sessions/abc12345_def/location"
            ),
            "abc12345_def",
        )

    def testCustomLocationMovesCacheAndSurvivesManagerRestart(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Root = Path(Directory)
            DefaultDirectory = Root / "default"
            CustomDirectory = Root / "custom results"
            SessionId = "moveme_12345678"
            State = {"current_view": "stack", "results": []}
            Manager = SessionCacheManager(DefaultDirectory=DefaultDirectory)
            Original = Path(Manager.save(SessionId, State)["cache_file"])

            Relocated = Manager.relocate(SessionId, str(CustomDirectory))

            RelocatedPath = Path(Relocated["cache_file"])
            self.assertTrue(Relocated["moved"])
            self.assertFalse(Original.exists())
            self.assertTrue(RelocatedPath.is_file())
            RestartedManager = SessionCacheManager(DefaultDirectory=DefaultDirectory)
            self.assertEqual(RestartedManager.DirectoryFor(SessionId), CustomDirectory.resolve())
            self.assertEqual(RestartedManager.load(SessionId)["state"], State)

    def testCustomLocationRejectsRelativeAndRootPaths(self):
        with self.assertRaisesRegex(ValueError, "absolute path"):
            SessionCacheManager.ValidateDirectory("relative/folder")
        with self.assertRaisesRegex(ValueError, "filesystem root"):
            SessionCacheManager.ValidateDirectory("/")

    def testManagerListsDefaultAndCustomCachesNewestFirst(self):
        with Tempfile.TemporaryDirectory() as Directory:
            Root = Path(Directory)
            Manager = SessionCacheManager(DefaultDirectory=Root / "default")
            OlderId = "older_12345678"
            NewerId = "newer_12345678"
            OlderPath = Path(Manager.save(OlderId, {"results": []})["cache_file"])
            Manager.save(NewerId, {"results": []})
            NewerPath = Path(
                Manager.relocate(NewerId, str(Root / "custom"))["cache_file"]
            )
            Os.utime(OlderPath, (1_000, 1_000))
            Os.utime(NewerPath, (2_000, 2_000))

            Sessions = Manager.ListSessions()

            self.assertEqual([Item["session_id"] for Item in Sessions], [NewerId, OlderId])
            self.assertEqual(Path(Sessions[0]["cache_file"]), NewerPath)
            self.assertEqual(Path(Sessions[1]["cache_file"]), OlderPath)
            self.assertTrue(all(Item["loadable"] for Item in Sessions))

    def testFrontendCreatesRestorableUrlSessions(self):
        IndexHtml = (APP_DIR / "static" / "index.html").read_text()
        AppJs = (APP_DIR / "static" / "app.js").read_text()

        self.assertIn('aria-label="Application version 66">v66</span>', IndexHtml)
        self.assertIn('id="SessionIndicator"', IndexHtml)
        self.assertIn('id="SaveLocationHeading">Save File Location</h2>', IndexHtml)
        self.assertIn('id="CacheFolderThing"', IndexHtml)
        self.assertIn('id="SaveLocationButton" type="submit">Apply</button>', IndexHtml)
        self.assertIn('id="LoadCacheHeading">Load Cache</h2>', IndexHtml)
        self.assertIn('id="CachePickThing"', IndexHtml)
        self.assertIn('id="LoadCacheButton"', IndexHtml)
        self.assertIn('id="RefreshCachesButton"', IndexHtml)
        self.assertIn("function EnsureSessionId()", AppJs)
        self.assertIn("function SetSaveFileLocation(Directory, CacheFile = '')", AppJs)
        self.assertIn("/location`,", AppJs)
        self.assertIn("function RestoreSessionState(State)", AppJs)
        self.assertIn("async function RefreshSessionCacheList()", AppJs)
        self.assertIn("window.location.assign", AppJs)
        self.assertIn("SessionReadyPromise = OpenRun();", AppJs)
        self.assertIn("/analysis-sessions/", AppJs)


if __name__ == "__main__":
    Unittest.RunApp()
