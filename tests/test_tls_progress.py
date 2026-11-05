from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"))
import tls_search


class SearchProgressTests(unittest.TestCase):
    def test_startup_idle_is_excluded_from_throughput_eta(self):
        reports = []
        clock = [0.0]
        with mock.patch.object(tls_search.monotonic_time, "monotonic", side_effect=lambda: clock[0]):
            progress = tls_search.SearchProgress(reports.append, total=1000)
            clock[0] = 120.0  # cold interpreter/JIT/worker startup
            progress.update()
            self.assertIsNone(reports[-1]["estimated_remaining_seconds"])
            for _ in range(25):
                clock[0] += 1.0
                progress.update(10)
            estimate = reports[-1]
            self.assertGreater(estimate["estimated_remaining_seconds"], 70.0)
            self.assertLess(estimate["estimated_remaining_seconds"], 110.0)
            self.assertEqual(estimate["throughput_elapsed_seconds"], 25.0)
            self.assertEqual(estimate["search_elapsed_seconds"], 145.0)
            progress.close()
            self.assertTrue(reports[-1]["search_complete"])
            self.assertIsNone(reports[-1]["estimated_remaining_seconds"])

    def test_eta_waits_for_samples_and_clears_at_end(self):
        reports = []
        clock = [0.0]
        with mock.patch.object(tls_search.monotonic_time, "monotonic", side_effect=lambda: clock[0]):
            progress = tls_search.SearchProgress(reports.append, total=100)
            self.assertIsNone(reports[-1]["estimated_remaining_seconds"])
            for count in range(60):
                clock[0] += .5
                progress.update()
            estimate = reports[-1]
            self.assertGreater(estimate["estimated_remaining_seconds"], 0)
            self.assertLessEqual(estimate["eta_lower_seconds"], estimate["eta_upper_seconds"])
            self.assertEqual(estimate["eta_scope"], "search")
            progress.close()
            self.assertIsNone(reports[-1]["estimated_remaining_seconds"])

    def test_changing_trial_cost_withdraws_the_estimate(self):
        reports, clock = [], [0.0]
        with mock.patch.object(tls_search.monotonic_time, "monotonic", side_effect=lambda: clock[0]):
            progress = tls_search.SearchProgress(reports.append, total=10000)
            progress.update()
            for _ in range(25):
                clock[0] += 1.0
                progress.update(30)
            self.assertEqual(reports[-1]["eta_state"], "available")
            for _ in range(6):
                clock[0] += 1.0
                progress.update(1)
            self.assertEqual(reports[-1]["eta_state"], "estimating")
            self.assertIsNone(reports[-1]["estimated_remaining_seconds"])
            self.assertIsNone(reports[-1]["remaining_seconds_range"])

    def test_stable_forecast_covers_a_known_continuing_workload(self):
        reports, clock = [], [0.0]
        with mock.patch.object(tls_search.monotonic_time, "monotonic", side_effect=lambda: clock[0]):
            progress = tls_search.SearchProgress(reports.append, total=1000)
            progress.update()
            for count in (50, 55, 45, 50):
                clock[0] += 5.0
                progress.update(count)
            estimate = reports[-1]
            # Continuing at ten trials/second takes 79.9 seconds for 799 trials.
            self.assertAlmostEqual(estimate["estimated_remaining_seconds"], 79.9)
            self.assertLessEqual(estimate["eta_lower_seconds"], 79.9)
            self.assertGreaterEqual(estimate["eta_upper_seconds"], 79.9)
            self.assertLess(estimate["eta_upper_seconds"] / estimate["eta_lower_seconds"], 1.5)
            self.assertEqual(estimate["eta_method"], "observed_trial_throughput")
            self.assertIsNone(reports[3]["estimated_remaining_seconds"])

    def test_module_progress_adapter_restores_on_error(self):
        import importlib
        module = importlib.import_module("transitleastsquares.main")
        stats = importlib.import_module("transitleastsquares.stats")
        original = module.tqdm
        original_stats = stats.tqdm
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with tls_search.measured_tls_progress(lambda details: None):
                self.assertIsNot(module.tqdm, original)
                self.assertIsNot(stats.tqdm, original_stats)
                raise RuntimeError("failure")
        self.assertIs(module.tqdm, original)
        self.assertIs(stats.tqdm, original_stats)


if __name__ == "__main__":
    unittest.main()
