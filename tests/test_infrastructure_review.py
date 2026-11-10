"""Input provenance, session compatibility, and background job contracts."""
import io as Io
import json as Json
from pathlib import Path
import sys as Sys
import tempfile as Tempfile
import time as Time
import unittest as Unittest
from unittest import mock as Mock

import numpy as Np

APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
Sys.path.insert(0, str(APP_DIR))

from analysis_jobs import AnalysisJobManager, AnnotateAnalysisResult
from parsers import CleanLightCurveArrays, ParseCsvBytes, ParseFitsBytes, FitsTimeReference
from session_cache import SessionCache
from main import TransitRequestHandler


#MARK: run progress
def ProgressRunner(TimeValues, FluxValues, Options, ProgressCallback=None):
    ProgressCallback("tls_search", "Searching periods with TLS", {
        "completed_trials": 10, "total_trials": 100,
        "estimated_remaining_seconds": 12, "eta_lower_seconds": 8,
        "eta_upper_seconds": 20, "eta_scope": "search",
    })
    Time.sleep(0.6)
    ProgressCallback("finalizing", "Preparing result")
    Time.sleep(0.1)
    return {"finished": True}


#MARK: minimal result
def MinimalResult():
    return {"period": 2.0, "plot": {"time": [0, 1, 2],
        "raw_flux": [1, .99, 1], "smooth_flux": [1, .99, 1]}, "transits": []}


#MARK: extra signals
def MultipleSignalRunner(TimeValues, FluxValues, Options):
    Result = MinimalResult()
    Result["effective_settings"] = {"tls_max_signals": 2}
    First = MinimalResult()
    First["effective_settings"] = {"tls_max_signals": 2, "signal_index": 0}
    Second = MinimalResult()
    Second["period"] = 3.0
    Second["effective_settings"] = {"tls_max_signals": 1, "signal_index": 1}
    Result["signals"] = [First, Second]
    return Result


#MARK: run checks
class ParserReviewTests(Unittest.TestCase):
    def testCsvCountsReconcileWithoutDiscardingMissingErrors(self):
        Rows = ["Time,Flux,Flux_err,Quality"]
        Rows += [f"{I},1,0.01,0" for I in range(30)]
        Rows += ["1,0.5,0.02,0", "bad,1,0.01,0", "nan,1,0.01,0",
                 "31,1,0.01,1", "32,1,,0"]
        Parsed = ParseCsvBytes("\n".join(Rows).encode(), ReturnMetadata=True)
        C = Parsed["cleaning"]
        self.assertEqual(C["input_rows"], 35)
        self.assertEqual(C["retained_rows"], 31)
        for Field in ("invalid_numeric_rows", "nonfinite_rows", "quality_excluded_rows", "duplicate_rows"):
            self.assertEqual(C[Field], 1)
        self.assertTrue(C["counts_reconcile"])
        self.assertEqual(C["invalid_uncertainty_rows"], 1)
        self.assertTrue(Np.isnan(Parsed["flux_uncertainty"][-1]))
        self.assertEqual(Parsed["flux"][1], 1)
        self.assertTrue(Parsed["input_metadata"]["time_convention_ambiguous"])

    def testSortingDuplicatePolicyAndErrorsStayAligned(self):
        TimeValues = list(range(29, -1, -1)) + [10]
        Parsed = CleanLightCurveArrays(TimeValues,
            [1 + T / 100 for T in TimeValues[:-1]] + [9],
            [0.1 + T / 1000 for T in TimeValues[:-1]] + [9], ReturnMetadata=True)
        Np.testing.assert_equal(Parsed["time"], Np.arange(30))
        self.assertAlmostEqual(Parsed["flux"][10], 1.1)
        self.assertAlmostEqual(Parsed["flux_uncertainty"][10], .11)
        self.assertTrue(Parsed["cleaning"]["sorting_applied"])
        self.assertEqual(Parsed["cleaning"]["duplicate_rows"], 1)

    def testDeclaredCsvTimeConversionIsExplicit(self):
        CsvData = ("Time,Flux\n" + "\n".join(f"{I * 60},1" for I in range(30))).encode()
        Parsed = ParseCsvBytes(CsvData, ReturnMetadata=True,
                                 TimeFormat="btjd", TimeUnit="seconds", TimeScale="tdb")
        self.assertAlmostEqual(Parsed["time"][0], 2457000)
        self.assertAlmostEqual(Parsed["time"][1] - Parsed["time"][0], 60 / 86400, places=8)
        self.assertEqual(Parsed["input_metadata"]["time_format"], "BJD")
        self.assertEqual(Parsed["input_metadata"]["time_scale"], "TDB")
        self.assertFalse(Parsed["input_metadata"]["time_convention_ambiguous"])
        Kepler = ParseCsvBytes(CsvData.replace(b"Time", b"BKJD"), ReturnMetadata=True, TimeUnit="seconds")
        self.assertEqual(Kepler["time"][0], 2454833)
        self.assertEqual(Kepler["input_metadata"]["time_format"], "BJD")

    def testCsvMjdHeaderConvertsToJdWithoutGuessingGenericTime(self):
        CsvData = ("MJD,Flux\n" + "\n".join(f"{60000 + I / 10},1" for I in range(30))).encode()
        Parsed = ParseCsvBytes(CsvData, ReturnMetadata=True)
        self.assertEqual(Parsed["time"][0], 2460000.5)
        self.assertEqual(Parsed["input_metadata"]["original_time_format"], "MJD")
        # the ui's default "unknown" means no override, not discard the header.
        DefaultUi = ParseCsvBytes(CsvData, ReturnMetadata=True, TimeFormat="unknown")
        Np.testing.assert_equal(DefaultUi["time"], Parsed["time"])

    def testZeroSpanFailsBeforeCadenceCanBeInfinite(self):
        with self.assertRaisesRegex(ValueError, "zero time span"):
            CleanLightCurveArrays(Np.ones(30), Np.ones(30))

    def testSplitFitsReferenceUsesExtensionAndPrimaryParts(self):
        self.assertEqual(FitsTimeReference({"BJDREFF": .25}, {"BJDREFI": 2457000}), 2457000.25)

    def testFitsSecondsReferenceQualityErrorsAndScale(self):
        from astropy.io import fits as Fits
        Cols = [Fits.Column(name="TIME", format="D", unit="s", array=Np.arange(30) * 60),
                Fits.Column(name="PDCSAP_FLUX", format="D", array=Np.ones(30)),
                Fits.Column(name="PDCSAP_FLUX_ERR", format="D", array=Np.full(30, .01)),
                Fits.Column(name="QUALITY", format="J", array=[1] + [0] * 29)]
        Table = Fits.BinTableHDU.from_columns(Cols)
        Table.header["MJDREFI"] = 60000
        Table.header["MJDREFF"] = .25
        Table.header["TIMEZERO"] = 30
        Table.header["TIMESYS"] = "TDB"
        Output = Io.BytesIO()
        Fits.HDUList([Fits.PrimaryHDU(), Table]).writeto(Output)
        Parsed = ParseFitsBytes(Output.getvalue(), ReturnMetadata=True)
        self.assertAlmostEqual(Parsed["time"][0], 2460000.75 + 90 / 86400)
        self.assertEqual(Parsed["cleaning"]["quality_excluded_rows"], 1)
        self.assertEqual(Parsed["cleaning"]["retained_rows"], 29)
        self.assertEqual(Parsed["input_metadata"]["time_scale"], "TDB")
        Np.testing.assert_equal(Parsed["flux_uncertainty"], Np.full(29, .01))


#MARK: cache files
class CacheReviewTests(Unittest.TestCase):
    def testLegacyRestoreIsExplicitAndLeavesOriginalFileUntouched(self):
        with Tempfile.TemporaryDirectory() as Folder:
            Cache = SessionCache(Folder)
            Document = {"schema_version": 1, "session_id": "legacy_12345678",
                        "saved_at": "2020-01-01", "state": {"results": [{"file_name": "old.csv", "result": MinimalResult()}]}}
            FilePath = Cache.PathFor(Document["session_id"])
            FilePath.write_text(Json.dumps(Document))
            Before = FilePath.read_bytes()
            Restored = Cache.load(Document["session_id"])
            Result = Restored["state"]["results"][0]["result"]
            self.assertEqual(Result["provenance"]["analysis_version"], "unknown")
            self.assertIsNone(Result["analyzed_at"])
            self.assertEqual(FilePath.read_bytes(), Before)

    def testResavingKeepsAnalysisDateAndEffectiveSettings(self):
        with Tempfile.TemporaryDirectory() as Folder:
            Cache = SessionCache(Folder)
            R = AnnotateAnalysisResult(MinimalResult(), {"stellar_mass": .1})
            State = {"results": [{"file_name": "new.csv", "result": R}],
                     "active_job_id": "abcdef123", "active_file_index": 0,
                     "pending_files": [{"file_name": "next.csv"}]}
            OriginalDate = R["analyzed_at"]
            Cache.save("current_12345678", State)
            Loaded = Cache.load("current_12345678")["state"]
            Loaded["current_view"] = "stack"
            Cache.save("current_12345678", Loaded)
            Final = Cache.load("current_12345678")["state"]["results"][0]["result"]
            self.assertEqual(Final["analyzed_at"], OriginalDate)
            self.assertEqual(Final["provenance"]["effective_settings"], {"stellar_mass": .1})

    def testMalformedCacheReportsErrorAndIsPreserved(self):
        with Tempfile.TemporaryDirectory() as Folder:
            Cache = SessionCache(Folder)
            Bad = MinimalResult()
            Bad["plot"]["raw_flux"] = [1]
            Doc = {"schema_version": 1, "session_id": "broken_12345678", "state": {"results": [{"result": Bad}]}}
            FilePath = Cache.PathFor(Doc["session_id"])
            FilePath.write_text(Json.dumps(Doc))
            Before = FilePath.read_bytes()
            with self.assertRaisesRegex(ValueError, "mismatched plot arrays"):
                Cache.load(Doc["session_id"])
            self.assertEqual(FilePath.read_bytes(), Before)

    def testFutureSchemaIsNotSilentlyLoaded(self):
        with Tempfile.TemporaryDirectory() as Folder:
            Cache = SessionCache(Folder)
            Doc = {"schema_version": 999, "session_id": "future_12345678", "state": {"results": []}}
            Cache.PathFor(Doc["session_id"]).write_text(Json.dumps(Doc))
            with self.assertRaisesRegex(ValueError, "unsupported cache schema"):
                Cache.load(Doc["session_id"])

    def testFutureProvenanceSchemaAndMismatchedFoldedArraysAreRejected(self):
        with Tempfile.TemporaryDirectory() as Folder:
            Cache = SessionCache(Folder)
            R = AnnotateAnalysisResult(MinimalResult())
            R["provenance"]["result_schema_version"] = 999
            with self.assertRaisesRegex(ValueError, "inconsistent provenance/result schemas"):
                Cache.save("metadata_12345678", {"results": [{"result": R}]})
            R = MinimalResult()
            R["transit_model"] = {"time": [], "flux": [], "folded_phase_days": [0, 1], "folded_flux": [1]}
            with self.assertRaisesRegex(ValueError, "mismatched folded model"):
                Cache.save("metadata_12345678", {"results": [{"result": R}]})

    def testActiveJobWithoutAMatchingFileIsRecoverablyRejected(self):
        with Tempfile.TemporaryDirectory() as Folder:
            Cache = SessionCache(Folder)
            with self.assertRaisesRegex(ValueError, "no matching file entry"):
                Cache.save("active_12345678", {"results": [], "active_job_id": "abc123"})


#MARK: worker stuffs
class JobReviewTests(Unittest.TestCase):
    def testMultisignalWorkerResultRoundTripsCacheWithOwnSettings(self):
        Manager = AnalysisJobManager(Runner=MultipleSignalRunner)
        self.addCleanup(Manager.shutdown)
        Submitted = Manager.submit(Np.arange(30), Np.ones(30), {}, SourceFile="two.csv")
        Deadline = Time.monotonic() + 15
        while Time.monotonic() < Deadline:
            Job = Manager.get(Submitted["job_id"])
            if Job["status"] in {"completed", "failed"}:
                break
            Time.sleep(.03)
        self.assertEqual(Job["status"], "completed", Job.get("error"))
        with Tempfile.TemporaryDirectory() as Folder:
            Cache = SessionCache(Folder)
            Cache.save("multiple_12345678", {"results": [{"file_name": "two.csv", "result": Job["result"]}]})
            Restored = Cache.load("multiple_12345678")["state"]["results"][0]["result"]
        for Index, SignalResult in enumerate(Restored["signals"]):
            self.assertEqual(SignalResult["result_schema_version"], 2)
            self.assertEqual(SignalResult["provenance"]["result_schema_version"], 2)
            self.assertEqual(SignalResult["provenance"]["effective_settings"]["signal_index"], Index)
            self.assertEqual(SignalResult["provenance"]["analyzed_at"], SignalResult["analyzed_at"])
            self.assertEqual(SignalResult["provenance"]["source_file"], "two.csv")

    def testSubmissionLookupHttpRouteDecodesTokenAndReturnsExistingJob(self):
        Handler = object.__new__(TransitRequestHandler)
        Handler.path = "/analysis-jobs?request_id=batch-example%3A0"
        Handler.server = Mock.Mock()
        Handler.server.AnalysisJobs.FindByRequestId.return_value = {"job_id": "abc123", "status": "running"}
        Handler.WriteJson = Mock.Mock()
        Handler.do_GET()
        Handler.server.AnalysisJobs.FindByRequestId.assert_called_once_with("batch-example:0")
        Handler.WriteJson.assert_called_once_with({"job_id": "abc123", "status": "running"}, Status=200)

    def testProgressIsMeasuredAndTerminalEtaClears(self):
        Manager = AnalysisJobManager(Runner=ProgressRunner)
        self.addCleanup(Manager.shutdown)
        First = Manager.submit(Np.arange(30), Np.ones(30), {})
        SawProgress = None
        Deadline = Time.monotonic() + 15
        while Time.monotonic() < Deadline:
            Snapshot = Manager.get(First["job_id"])
            if Snapshot.get("completed_trials") == 10:
                SawProgress = Snapshot
            if Snapshot["status"] in {"completed", "failed"}:
                break
            Time.sleep(.03)
        self.assertIsNotNone(SawProgress)
        self.assertEqual(SawProgress["total_trials"], 100)
        self.assertEqual(SawProgress["eta_scope"], "search")
        self.assertEqual(Snapshot["status"], "completed", Snapshot.get("error"))
        self.assertIsNone(Snapshot["estimated_remaining_seconds"])
        self.assertEqual(Snapshot["result"]["result_schema_version"], 2)

    def testRepeatedSubmissionTokenDoesNotLaunchASecondJob(self):
        Manager = AnalysisJobManager(Runner=ProgressRunner)
        self.addCleanup(Manager.shutdown)
        Options = {"_request_id": "batch-example:0", "_batch_id": "batch-example"}
        First = Manager.submit(Np.arange(30), Np.ones(30), Options, "same.csv")
        Repeated = Manager.submit(Np.arange(30), Np.ones(30), Options, "same.csv")
        self.assertEqual(First["job_id"], Repeated["job_id"])
        self.assertEqual(len(Manager.Jobs), 1)
        Found = Manager.FindByRequestId(Options["_request_id"])
        self.assertEqual(Found["job_id"], First["job_id"])
        self.assertIsNone(Manager.FindByRequestId("unknown-submission"))
        with self.assertRaisesRegex(ValueError, "different analysis inputs"):
            Manager.submit(Np.arange(30), Np.zeros(30), Options, "same.csv")

    def testNonfiniteResultIsRejectedBeforeTransport(self):
        with self.assertRaisesRegex(ValueError, "nonfinite or unsupported"):
            AnnotateAnalysisResult({"diagnostics": {"invalid": float("nan")}})


if __name__ == "__main__":
    Unittest.RunApp()
