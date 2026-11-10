import io as Io
from pathlib import Path
import sys as Sys
import time as Time
import unittest as Unittest
from unittest import mock as Mock

import numpy as Np


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
Sys.path.insert(0, str(APP_DIR))

from analysis_jobs import AnalysisJobManager  # noqa: E402
from main import TransitRequestHandler, FormatAnalysisJobPoll  # noqa: E402


#MARK: quick runner
def QuickRunner(TimeValues, FluxValues, Options):
    return {
        "point_count": len(TimeValues),
        "option_marker": Options.get("marker"),
        "flux_mean": float(Np.mean(FluxValues)),
    }


#MARK: slow runner
def SlowRunner(TimeValues, FluxValues, Options):
    Time.sleep(30)
    return {"finished": True}


#MARK: staged runner
def StagedRunner(TimeValues, FluxValues, Options, ProgressCallback=None):
    ProgressCallback("tls_search", "Searching periods with TLS")
    Time.sleep(0.3)
    return {"finished": True}


#MARK: wait for terminal
def WaitForTerminal(Manager, JobId, Timeout=10):
    Deadline = Time.monotonic() + Timeout
    while Time.monotonic() < Deadline:
        Job = Manager.get(JobId)
        if Job and Job["status"] in {"completed", "failed", "cancelled"}:
            return Job
        Time.sleep(0.05)
    raise AssertionError(f"Job {JobId} did not finish within {Timeout} seconds")


#MARK: worker stuffs
class AnalysisJobManagerTests(Unittest.TestCase):
    def testSpawnedJobCompletesAndReturnsResult(self):
        Manager = AnalysisJobManager(StartMethod="spawn", Runner=QuickRunner)
        self.addCleanup(Manager.shutdown)
        Submitted = Manager.submit(
            Np.arange(12, dtype=float),
            Np.full(12, 1.25),
            {"marker": "kept"},
            SourceFile="curve.csv",
        )

        self.assertIn(Submitted["status"], {"queued", "running"})
        Job = WaitForTerminal(Manager, Submitted["job_id"])

        self.assertEqual(Job["status"], "completed")
        self.assertEqual(Job["source_file"], "curve.csv")
        self.assertEqual(Job["result"]["point_count"], 12)
        self.assertEqual(Job["result"]["option_marker"], "kept")

    def testRunningJobCanBeCancelled(self):
        Manager = AnalysisJobManager(StartMethod="spawn", Runner=SlowRunner)
        self.addCleanup(Manager.shutdown)
        Submitted = Manager.submit(Np.arange(20), Np.ones(20), {})

        Job = Manager.cancel(Submitted["job_id"])

        self.assertEqual(Job["status"], "cancelled")
        self.assertLess(Job["elapsed_seconds"], 10)
        self.assertEqual(Manager.get(Submitted["job_id"])["status"], "cancelled")

    def testRunningJobReportsWorkerStage(self):
        Manager = AnalysisJobManager(StartMethod="spawn", Runner=StagedRunner)
        self.addCleanup(Manager.shutdown)
        Submitted = Manager.submit(Np.arange(20), Np.ones(20), {})
        Deadline = Time.monotonic() + 5
        Observed = None
        while Time.monotonic() < Deadline:
            Job = Manager.get(Submitted["job_id"])
            if Job.get("stage") == "tls_search":
                Observed = Job
                break
            Time.sleep(0.02)

        self.assertIsNotNone(Observed)
        self.assertEqual(Observed["status"], "running")
        self.assertEqual(Observed["stage_label"], "Searching periods with TLS")
        self.assertEqual(
            WaitForTerminal(Manager, Submitted["job_id"])["status"],
            "completed",
        )


#MARK: run checks
class DisconnectHandlingTests(Unittest.TestCase):
    def testPeriodicJobPollLogShowsProgressWithoutResultPayload(self):
        with Mock.patch("main.Time.strftime", return_value="2026-07-24 09:30:00"):
            Message = FormatAnalysisJobPoll(
                "abcdef123456",
                {
                    "status": "running",
                    "source_file": "kepler curve.csv",
                    "elapsed_seconds": 3723.456,
                    "queue_position": None,
                    "stage_label": "Searching periods with TLS",
                    "result": {"large": "payload"},
                },
            )

        self.assertEqual(
            Message,
            '[2026-07-24 09:30:00] [analysis poll] job=abcdef12 '
            'file="kepler curve.csv" status=running elapsed=3723.5s '
            'stage="Searching periods with TLS"',
        )
        self.assertNotIn("payload", Message)

    def testFailedJobPollLogIncludesError(self):
        with Mock.patch("main.Time.strftime", return_value="2026-07-24 09:31:00"):
            Message = FormatAnalysisJobPoll(
                "9876543210",
                {
                    "status": "failed",
                    "source_file": "curve.csv",
                    "elapsed_seconds": 12,
                    "queue_position": None,
                    "error": "TLS did not fit a valid transit.",
                },
            )

        self.assertIn("job=98765432", Message)
        self.assertIn("status=failed", Message)
        self.assertIn('error=\"TLS did not fit a valid transit.\"', Message)

    def testJsonWriteTreatsBrokenPipeAsClientDisconnect(self):
        Handler = object.__new__(TransitRequestHandler)
        Handler.client_address = ("127.0.0.1", 51000)
        Handler.send_response = Mock.Mock()
        Handler.send_header = Mock.Mock()
        Handler.end_headers = Mock.Mock()
        Handler.wfile = Mock.Mock()
        Handler.wfile.write.side_effect = BrokenPipeError(32, "Broken pipe")

        with Mock.patch("sys.stdout", new_callable=Io.StringIO) as Output:
            Delivered = Handler.WriteJson({"ok": True})

        self.assertFalse(Delivered)
        self.assertIn("connection closed", Output.getvalue())
        Handler.send_response.assert_called_once_with(200)
        Handler.wfile.write.assert_called_once()

    def testJobPathParserRejectsNestedOrEmptyPaths(self):
        self.assertEqual(
            TransitRequestHandler.AnalysisJobId("/analysis-jobs/abc123"),
            "abc123",
        )
        self.assertIsNone(TransitRequestHandler.AnalysisJobId("/analysis-jobs/"))
        self.assertIsNone(TransitRequestHandler.AnalysisJobId("/analysis-jobs/a/b"))


if __name__ == "__main__":
    Unittest.RunApp()
