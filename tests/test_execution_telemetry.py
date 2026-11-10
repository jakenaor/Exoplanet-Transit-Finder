import json as Json
from pathlib import Path
import sys as Sys
import time as Time
import unittest as Unittest

import numpy as Np

Sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"))
from analysis_jobs import AnalysisJobManager, ExecutionTelemetry, CleanedProgressDetails


#MARK: run progress
def Progress(Count, Elapsed, Estimate=None, Bounds=None, Complete=False, Total=100):
    return {"completed_trials": Count, "total_trials": Total,
            "search_elapsed_seconds": Elapsed, "estimated_remaining_seconds": Estimate,
            "eta_lower_seconds": Bounds[0] if Bounds else None,
            "eta_upper_seconds": Bounds[1] if Bounds else None,
            "eta_state": "available" if Estimate is not None else "estimating",
            "eta_scope": "search", "search_complete": Complete}


#MARK: run progress
def TelemetryRunner(TimeValues, FluxValues, Options, ProgressCallback=None):
    ProgressCallback("tls_search", "Searching", Progress(0, 0))
    ProgressCallback("tls_search", "Searching", Progress(50, .01, .02, (.01, .03)))
    ProgressCallback("tls_finalizing", "Finalizing", Progress(100, .02, Complete=True))
    return {"finished": True}


#MARK: run progress
class ExecutionTelemetryTests(Unittest.TestCase):
    def testCompletedWorkerPersistsTelemetryInTheSavedResult(self):
        Manager = AnalysisJobManager(Runner=TelemetryRunner)
        self.addCleanup(Manager.shutdown)
        Submitted = Manager.submit(Np.arange(20), Np.ones(20), {})
        Deadline = Time.monotonic() + 15
        while Time.monotonic() < Deadline:
            Job = Manager.get(Submitted["job_id"])
            if Job["status"] in {"completed", "failed"}:
                break
            Time.sleep(.02)
        self.assertEqual(Job["status"], "completed", Job.get("error"))
        Execution = Job["result"]["execution"]
        self.assertEqual(Execution, Job["execution"])
        self.assertEqual(Execution["eta_audit"]["retained_forecasts_audited"], 1)
        self.assertIsNone(Job["estimated_remaining_seconds"])
        self.assertEqual(Execution["searches"][0]["completed_trials"], 100)
        Json.dumps(Job, allow_nan=False)

    def testAuditUsesActualSearchEndWithoutIncludingFinalization(self):
        Telemetry = ExecutionTelemetry()
        Telemetry.update("starting", "Starting", {}, 0)
        Telemetry.update("tls_search", "Searching", Progress(0, 0), 1)
        Telemetry.update("tls_search", "Searching", Progress(25, 9, 20, (15, 25)), 10)
        Telemetry.update("tls_search", "Searching", Progress(50, 19, 20, (15, 25)), 20)
        Telemetry.update("tls_finalizing", "Finalizing", Progress(100, 39, Complete=True), 40)
        Execution = Telemetry.finish("completed", "Complete", 45, QueueWait=2)
        self.assertEqual(Execution["elapsed_seconds"], 45)
        self.assertEqual(Execution["queue_wait_seconds"], 2)
        self.assertEqual(sum(Stage["duration_seconds"] for Stage in Execution["stage_durations"]), 45)
        Forecasts = [Row for Row in Execution["progress_history"] if "eta_error_seconds" in Row]
        self.assertEqual([Row["actual_remaining_seconds"] for Row in Forecasts], [30, 20])
        self.assertEqual([Row["eta_error_seconds"] for Row in Forecasts], [-10, 0])
        self.assertEqual(Execution["eta_audit"]["mean_absolute_error_seconds"], 5)
        self.assertEqual(Execution["eta_audit"]["observed_range_coverage_fraction"], .5)
        Json.dumps(Execution, allow_nan=False)

    def testSeparateSearchesGetSeparateActualEndpoints(self):
        Telemetry = ExecutionTelemetry()
        Telemetry.update("tls_search", "First search", Progress(0, 0), 0)
        Telemetry.update("tls_search", "First search", Progress(50, 10, 10), 10)
        Telemetry.update("tls_finalizing", "Finalizing", Progress(100, 20, Complete=True), 20)
        Telemetry.update("tls_search", "Second search", Progress(0, 0), 30)
        Telemetry.update("tls_search", "Second search", Progress(50, 10, 20), 40)
        Telemetry.update("tls_finalizing", "Finalizing", Progress(100, 30, Complete=True), 60)
        Execution = Telemetry.finish("completed", "Complete", 65)
        Forecasts = [Row for Row in Execution["progress_history"] if "eta_error_seconds" in Row]
        self.assertEqual([Row["actual_remaining_seconds"] for Row in Forecasts], [10, 20])
        self.assertEqual([Row["search_id"] for Row in Forecasts], [1, 2])
        self.assertEqual(Execution["eta_audit"]["mean_absolute_error_seconds"], 0)

    def testCancelledSearchDoesNotInventActualCompletion(self):
        Telemetry = ExecutionTelemetry()
        Telemetry.update("tls_search", "Searching", Progress(0, 0), 0)
        Telemetry.update("tls_search", "Searching", Progress(50, 10, 20), 10)
        Execution = Telemetry.finish("cancelled", "Cancelled", 15)
        self.assertEqual(Execution["eta_audit"]["retained_forecasts_audited"], 0)
        self.assertIsNone(Execution["eta_audit"]["mean_absolute_error_seconds"])

    def testLongJobKeepsBoundedHistoryAndExplicitSampling(self):
        Telemetry = ExecutionTelemetry(HistoryLimit=32)
        for I in range(500):
            Telemetry.update("tls_search", "Searching", Progress(I, I * 5, 500 - I, Total=500), I * 5)
        Telemetry.update("tls_finalizing", "Finalizing", Progress(500, 2500, Complete=True, Total=500), 2500)
        Execution = Telemetry.finish("completed", "Complete", 2502)
        History = Execution["progress_history"]
        self.assertLessEqual(len(History), 32)
        self.assertTrue(Execution["progress_history_sampled"])
        self.assertEqual(History[0]["elapsed_seconds"], 0)
        self.assertEqual(History[-1]["elapsed_seconds"], 2502)

    def testEtaMetadataCrossesTheBoundaryWithoutNonfiniteValues(self):
        Details = CleanedProgressDetails({"eta_method": "observed_trial_throughput",
            "eta_sample_seconds": 20, "eta_variation": float("inf")})
        self.assertEqual(Details["eta_method"], "observed_trial_throughput")
        self.assertEqual(Details["eta_sample_seconds"], 20)
        self.assertNotIn("eta_variation", Details)


if __name__ == "__main__":
    Unittest.RunApp()
