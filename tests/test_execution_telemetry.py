import json
from pathlib import Path
import sys
import time
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"))
from analysis_jobs import AnalysisJobManager, ExecutionTelemetry, cleaned_progress_details


def progress(count, elapsed, estimate=None, bounds=None, complete=False, total=100):
    return {"completed_trials": count, "total_trials": total,
            "search_elapsed_seconds": elapsed, "estimated_remaining_seconds": estimate,
            "eta_lower_seconds": bounds[0] if bounds else None,
            "eta_upper_seconds": bounds[1] if bounds else None,
            "eta_state": "available" if estimate is not None else "estimating",
            "eta_scope": "search", "search_complete": complete}


def telemetry_runner(time_values, flux_values, options, progress_callback=None):
    progress_callback("tls_search", "Searching", progress(0, 0))
    progress_callback("tls_search", "Searching", progress(50, .01, .02, (.01, .03)))
    progress_callback("tls_finalizing", "Finalizing", progress(100, .02, complete=True))
    return {"finished": True}


class ExecutionTelemetryTests(unittest.TestCase):
    def test_completed_worker_persists_telemetry_in_the_saved_result(self):
        manager = AnalysisJobManager(runner=telemetry_runner)
        self.addCleanup(manager.shutdown)
        submitted = manager.submit(np.arange(20), np.ones(20), {})
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            job = manager.get(submitted["job_id"])
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(.02)
        self.assertEqual(job["status"], "completed", job.get("error"))
        execution = job["result"]["execution"]
        self.assertEqual(execution, job["execution"])
        self.assertEqual(execution["eta_audit"]["retained_forecasts_audited"], 1)
        self.assertIsNone(job["estimated_remaining_seconds"])
        self.assertEqual(execution["searches"][0]["completed_trials"], 100)
        json.dumps(job, allow_nan=False)

    def test_audit_uses_actual_search_end_without_including_finalization(self):
        telemetry = ExecutionTelemetry()
        telemetry.update("starting", "Starting", {}, 0)
        telemetry.update("tls_search", "Searching", progress(0, 0), 1)
        telemetry.update("tls_search", "Searching", progress(25, 9, 20, (15, 25)), 10)
        telemetry.update("tls_search", "Searching", progress(50, 19, 20, (15, 25)), 20)
        telemetry.update("tls_finalizing", "Finalizing", progress(100, 39, complete=True), 40)
        execution = telemetry.finish("completed", "Complete", 45, queue_wait=2)
        self.assertEqual(execution["elapsed_seconds"], 45)
        self.assertEqual(execution["queue_wait_seconds"], 2)
        self.assertEqual(sum(stage["duration_seconds"] for stage in execution["stage_durations"]), 45)
        forecasts = [row for row in execution["progress_history"] if "eta_error_seconds" in row]
        self.assertEqual([row["actual_remaining_seconds"] for row in forecasts], [30, 20])
        self.assertEqual([row["eta_error_seconds"] for row in forecasts], [-10, 0])
        self.assertEqual(execution["eta_audit"]["mean_absolute_error_seconds"], 5)
        self.assertEqual(execution["eta_audit"]["observed_range_coverage_fraction"], .5)
        json.dumps(execution, allow_nan=False)

    def test_separate_searches_get_separate_actual_endpoints(self):
        telemetry = ExecutionTelemetry()
        telemetry.update("tls_search", "First search", progress(0, 0), 0)
        telemetry.update("tls_search", "First search", progress(50, 10, 10), 10)
        telemetry.update("tls_finalizing", "Finalizing", progress(100, 20, complete=True), 20)
        telemetry.update("tls_search", "Second search", progress(0, 0), 30)
        telemetry.update("tls_search", "Second search", progress(50, 10, 20), 40)
        telemetry.update("tls_finalizing", "Finalizing", progress(100, 30, complete=True), 60)
        execution = telemetry.finish("completed", "Complete", 65)
        forecasts = [row for row in execution["progress_history"] if "eta_error_seconds" in row]
        self.assertEqual([row["actual_remaining_seconds"] for row in forecasts], [10, 20])
        self.assertEqual([row["search_id"] for row in forecasts], [1, 2])
        self.assertEqual(execution["eta_audit"]["mean_absolute_error_seconds"], 0)

    def test_cancelled_search_does_not_invent_actual_completion(self):
        telemetry = ExecutionTelemetry()
        telemetry.update("tls_search", "Searching", progress(0, 0), 0)
        telemetry.update("tls_search", "Searching", progress(50, 10, 20), 10)
        execution = telemetry.finish("cancelled", "Cancelled", 15)
        self.assertEqual(execution["eta_audit"]["retained_forecasts_audited"], 0)
        self.assertIsNone(execution["eta_audit"]["mean_absolute_error_seconds"])

    def test_long_job_keeps_bounded_history_and_explicit_sampling(self):
        telemetry = ExecutionTelemetry(history_limit=32)
        for i in range(500):
            telemetry.update("tls_search", "Searching", progress(i, i * 5, 500 - i, total=500), i * 5)
        telemetry.update("tls_finalizing", "Finalizing", progress(500, 2500, complete=True, total=500), 2500)
        execution = telemetry.finish("completed", "Complete", 2502)
        history = execution["progress_history"]
        self.assertLessEqual(len(history), 32)
        self.assertTrue(execution["progress_history_sampled"])
        self.assertEqual(history[0]["elapsed_seconds"], 0)
        self.assertEqual(history[-1]["elapsed_seconds"], 2502)

    def test_eta_metadata_crosses_the_boundary_without_nonfinite_values(self):
        details = cleaned_progress_details({"eta_method": "observed_trial_throughput",
            "eta_sample_seconds": 20, "eta_variation": float("inf")})
        self.assertEqual(details["eta_method"], "observed_trial_throughput")
        self.assertEqual(details["eta_sample_seconds"], 20)
        self.assertNotIn("eta_variation", details)


if __name__ == "__main__":
    unittest.main()
