import io
from pathlib import Path
import sys
import time
import unittest
from unittest import mock

import numpy as np


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
sys.path.insert(0, str(APP_DIR))

from analysis_jobs import AnalysisJobManager  # noqa: E402
from main import TransitRequestHandler, format_analysis_job_poll  # noqa: E402


def quick_runner(time_values, flux_values, options):
    return {
        "point_count": len(time_values),
        "option_marker": options.get("marker"),
        "flux_mean": float(np.mean(flux_values)),
    }


def slow_runner(time_values, flux_values, options):
    time.sleep(30)
    return {"finished": True}


def wait_for_terminal(manager, job_id, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = manager.get(job_id)
        if job and job["status"] in {"completed", "failed", "cancelled"}:
            return job
        time.sleep(0.05)
    raise AssertionError(f"Job {job_id} did not finish within {timeout} seconds")


class AnalysisJobManagerTests(unittest.TestCase):
    def test_spawned_job_completes_and_returns_result(self):
        manager = AnalysisJobManager(start_method="spawn", runner=quick_runner)
        self.addCleanup(manager.shutdown)
        submitted = manager.submit(
            np.arange(12, dtype=float),
            np.full(12, 1.25),
            {"marker": "kept"},
            source_file="curve.csv",
        )

        self.assertIn(submitted["status"], {"queued", "running"})
        job = wait_for_terminal(manager, submitted["job_id"])

        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["source_file"], "curve.csv")
        self.assertEqual(job["result"]["point_count"], 12)
        self.assertEqual(job["result"]["option_marker"], "kept")

    def test_running_job_can_be_cancelled(self):
        manager = AnalysisJobManager(start_method="spawn", runner=slow_runner)
        self.addCleanup(manager.shutdown)
        submitted = manager.submit(np.arange(20), np.ones(20), {})

        job = manager.cancel(submitted["job_id"])

        self.assertEqual(job["status"], "cancelled")
        self.assertLess(job["elapsed_seconds"], 10)
        self.assertEqual(manager.get(submitted["job_id"])["status"], "cancelled")


class DisconnectHandlingTests(unittest.TestCase):
    def test_periodic_job_poll_log_shows_progress_without_result_payload(self):
        with mock.patch("main.time.strftime", return_value="2026-07-24 09:30:00"):
            message = format_analysis_job_poll(
                "abcdef123456",
                {
                    "status": "running",
                    "source_file": "kepler curve.csv",
                    "elapsed_seconds": 3723.456,
                    "queue_position": None,
                    "result": {"large": "payload"},
                },
            )

        self.assertEqual(
            message,
            '[2026-07-24 09:30:00] [analysis poll] job=abcdef12 '
            'file="kepler curve.csv" status=running elapsed=3723.5s',
        )
        self.assertNotIn("payload", message)

    def test_failed_job_poll_log_includes_error(self):
        with mock.patch("main.time.strftime", return_value="2026-07-24 09:31:00"):
            message = format_analysis_job_poll(
                "9876543210",
                {
                    "status": "failed",
                    "source_file": "curve.csv",
                    "elapsed_seconds": 12,
                    "queue_position": None,
                    "error": "TLS did not fit a valid transit.",
                },
            )

        self.assertIn("job=98765432", message)
        self.assertIn("status=failed", message)
        self.assertIn('error=\"TLS did not fit a valid transit.\"', message)

    def test_json_write_treats_broken_pipe_as_client_disconnect(self):
        handler = object.__new__(TransitRequestHandler)
        handler.client_address = ("127.0.0.1", 51000)
        handler.send_response = mock.Mock()
        handler.send_header = mock.Mock()
        handler.end_headers = mock.Mock()
        handler.wfile = mock.Mock()
        handler.wfile.write.side_effect = BrokenPipeError(32, "Broken pipe")

        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            delivered = handler.write_json({"ok": True})

        self.assertFalse(delivered)
        self.assertIn("connection closed", output.getvalue())
        handler.send_response.assert_called_once_with(200)
        handler.wfile.write.assert_called_once()

    def test_job_path_parser_rejects_nested_or_empty_paths(self):
        self.assertEqual(
            TransitRequestHandler.analysis_job_id("/analysis-jobs/abc123"),
            "abc123",
        )
        self.assertIsNone(TransitRequestHandler.analysis_job_id("/analysis-jobs/"))
        self.assertIsNone(TransitRequestHandler.analysis_job_id("/analysis-jobs/a/b"))


if __name__ == "__main__":
    unittest.main()
