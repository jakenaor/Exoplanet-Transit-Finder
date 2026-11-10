"""Keep older scripts working while the app uses camelCase."""
from pathlib import Path
import inspect as Inspect
import sys as Sys
import tempfile as Tempfile
import time as Time
import unittest as Unittest

import numpy as Np

APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
Sys.path.insert(0, str(APP_DIR))

import analysis as Analysis
import parsers as Parsers
import tls_search as TlsSearch
from analysis_jobs import AnalysisJobManager
from session_cache import SessionCache, SessionCacheManager


#MARK: fake external caller
def LegacyRunner(TimeValues, FluxValues, Options, progress_callback=None):
    # this old spelling is deliberate: the worker has to accept outside callers.
    progress_callback("tls_search", "Old runner checking in", {
        "completed_trials": 1, "total_trials": 3,
    })
    return {"total_points": len(TimeValues), "transits": [], "caller": "legacy"}


#MARK: old calls
class LegacyPythonApiTests(Unittest.TestCase):
    def testOldSearchCallbackKeywordsStillBind(self):
        # binding catches a broken keyword without starting another search.
        for Search in (Analysis.estimate_period_with_tls, TlsSearch.run_tls_search):
            Inspect.signature(Search).bind([], [], {}, progress_callback=None)

    def testOldParserKeywordsMatchCamelCaseParser(self):
        Raw = ("Time,Flux\n" + "\n".join(f"{2459000 + I * .01},1" for I in range(30))).encode()
        Old = Parsers.parse_csv_bytes(Raw, return_metadata=True, time_format="jd",
                                     time_scale="tdb", time_unit="days")
        New = Parsers.ParseCsvBytes(Raw, ReturnMetadata=True, TimeFormat="jd",
                                   TimeScale="tdb", TimeUnit="days")
        Np.testing.assert_array_equal(Old["time"], New["time"])
        Np.testing.assert_array_equal(Old["flux"], New["flux"])
        self.assertEqual(Old["input_metadata"], New["input_metadata"])
        self.assertEqual(Old["cleaning"], New["cleaning"])

    def testOldCacheConstructorKeywordsStillWork(self):
        with Tempfile.TemporaryDirectory() as Folder:
            Old = SessionCache(Folder, max_bytes=2048)
            New = SessionCache(Folder, MaxBytes=2048)
            self.assertEqual(Old.Directory, New.Directory)
            self.assertEqual(Old.MaxBytes, New.MaxBytes)
            Manager = SessionCacheManager(default_directory=Folder, max_bytes=2048)
            self.assertEqual(Manager.DefaultDirectory, Path(Folder).resolve())
            self.assertEqual(Manager.MaxBytes, 2048)

    def testOldRunnerGetsProgressThroughSpawn(self):
        Manager = AnalysisJobManager(max_running=1, retention_seconds=60,
                                     start_method="spawn", Runner=LegacyRunner)
        try:
            JobId = Manager.submit(Np.arange(30, dtype=float), Np.ones(30), {})["job_id"]
            Deadline = Time.monotonic() + 15
            while Time.monotonic() < Deadline:
                Job = Manager.get(JobId)
                if Job["status"] in ("completed", "failed"):
                    break
                Time.sleep(.02)
            self.assertEqual(Job["status"], "completed", Job.get("error"))
            self.assertEqual(Job["result"]["caller"], "legacy")
            Stages = Job["result"]["execution"]["stage_durations"]
            self.assertTrue(any(Stage["stage"] == "tls_search" for Stage in Stages))
        finally:
            Manager.shutdown()

    def testOldAnalysisProgressKeywordStillReportsStages(self):
        from test_tls_search import SyntheticLightCurve, TlsOptions
        TimeValues, FluxValues, _ = SyntheticLightCurve()
        Stages = []
        Result = Analysis.analyze(TimeValues, FluxValues, TlsOptions(),
                                  progress_callback=lambda Stage, Label, Details=None: Stages.append(Stage))
        self.assertIn("tls_search", Stages)
        self.assertIn("finalizing", Stages)
        self.assertEqual(Result["period_method"], "TLS")


if __name__ == "__main__":
    Unittest.RunApp()
