from pathlib import Path
import sys as Sys
import unittest as Unittest
from unittest import mock as Mock

Sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"))
import tls_search as TlsSearch


#MARK: run progress
class SearchProgressTests(Unittest.TestCase):
    def testStartupIdleIsExcludedFromThroughputEta(self):
        Reports = []
        Clock = [0.0]
        with Mock.patch.object(TlsSearch.MonotonicTime, "monotonic", side_effect=lambda: Clock[0]):
            Progress = TlsSearch.SearchProgress(Reports.append, total=1000)
            Clock[0] = 120.0  # cold interpreter/jit/worker startup
            Progress.update()
            self.assertIsNone(Reports[-1]["estimated_remaining_seconds"])
            for _ in range(25):
                Clock[0] += 1.0
                Progress.update(10)
            Estimate = Reports[-1]
            self.assertGreater(Estimate["estimated_remaining_seconds"], 70.0)
            self.assertLess(Estimate["estimated_remaining_seconds"], 110.0)
            self.assertEqual(Estimate["throughput_elapsed_seconds"], 25.0)
            self.assertEqual(Estimate["search_elapsed_seconds"], 145.0)
            Progress.close()
            self.assertTrue(Reports[-1]["search_complete"])
            self.assertIsNone(Reports[-1]["estimated_remaining_seconds"])

    def testEtaWaitsForSamplesAndClearsAtEnd(self):
        Reports = []
        Clock = [0.0]
        with Mock.patch.object(TlsSearch.MonotonicTime, "monotonic", side_effect=lambda: Clock[0]):
            Progress = TlsSearch.SearchProgress(Reports.append, total=100)
            self.assertIsNone(Reports[-1]["estimated_remaining_seconds"])
            for Count in range(60):
                Clock[0] += .5
                Progress.update()
            Estimate = Reports[-1]
            self.assertGreater(Estimate["estimated_remaining_seconds"], 0)
            self.assertLessEqual(Estimate["eta_lower_seconds"], Estimate["eta_upper_seconds"])
            self.assertEqual(Estimate["eta_scope"], "search")
            Progress.close()
            self.assertIsNone(Reports[-1]["estimated_remaining_seconds"])

    def testChangingTrialCostWithdrawsTheEstimate(self):
        Reports, Clock = [], [0.0]
        with Mock.patch.object(TlsSearch.MonotonicTime, "monotonic", side_effect=lambda: Clock[0]):
            Progress = TlsSearch.SearchProgress(Reports.append, total=10000)
            Progress.update()
            for _ in range(25):
                Clock[0] += 1.0
                Progress.update(30)
            self.assertEqual(Reports[-1]["eta_state"], "available")
            for _ in range(6):
                Clock[0] += 1.0
                Progress.update(1)
            self.assertEqual(Reports[-1]["eta_state"], "estimating")
            self.assertIsNone(Reports[-1]["estimated_remaining_seconds"])
            self.assertIsNone(Reports[-1]["remaining_seconds_range"])

    def testStableForecastCoversAKnownContinuingWorkload(self):
        Reports, Clock = [], [0.0]
        with Mock.patch.object(TlsSearch.MonotonicTime, "monotonic", side_effect=lambda: Clock[0]):
            Progress = TlsSearch.SearchProgress(Reports.append, total=1000)
            Progress.update()
            for Count in (50, 55, 45, 50):
                Clock[0] += 5.0
                Progress.update(Count)
            Estimate = Reports[-1]
            # continuing at ten trials/second takes 79.9 seconds for 799 trials.
            self.assertAlmostEqual(Estimate["estimated_remaining_seconds"], 79.9)
            self.assertLessEqual(Estimate["eta_lower_seconds"], 79.9)
            self.assertGreaterEqual(Estimate["eta_upper_seconds"], 79.9)
            self.assertLess(Estimate["eta_upper_seconds"] / Estimate["eta_lower_seconds"], 1.5)
            self.assertEqual(Estimate["eta_method"], "observed_trial_throughput")
            self.assertIsNone(Reports[3]["estimated_remaining_seconds"])

    def testModuleProgressAdapterRestoresOnError(self):
        import importlib as Importlib
        Module = Importlib.import_module("transitleastsquares.main")
        Stats = Importlib.import_module("transitleastsquares.stats")
        Original = Module.tqdm
        OriginalStats = Stats.tqdm
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with TlsSearch.MeasuredTlsProgress(lambda Details: None):
                self.assertIsNot(Module.tqdm, Original)
                self.assertIsNot(Stats.tqdm, OriginalStats)
                raise RuntimeError("failure")
        self.assertIs(Module.tqdm, Original)
        self.assertIs(Stats.tqdm, OriginalStats)


if __name__ == "__main__":
    Unittest.RunApp()
