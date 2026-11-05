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
            for _ in range(10):
                clock[0] += 1.0
                progress.update(10)
            estimate = reports[-1]
            self.assertGreater(estimate["estimated_remaining_seconds"], 70.0)
            self.assertLess(estimate["estimated_remaining_seconds"], 110.0)
            self.assertEqual(estimate["throughput_elapsed_seconds"], 10.0)
            self.assertEqual(estimate["search_elapsed_seconds"], 130.0)
            progress.close()
            self.assertTrue(reports[-1]["search_complete"])
            self.assertIsNone(reports[-1]["estimated_remaining_seconds"])

    def test_eta_waits_for_samples_and_clears_at_end(self):
        reports = []
        clock = [0.0]
        with mock.patch.object(tls_search.monotonic_time, "monotonic", side_effect=lambda: clock[0]):
            progress = tls_search.SearchProgress(reports.append, total=100)
            self.assertIsNone(reports[-1]["estimated_remaining_seconds"])
            for count in range(20):
                clock[0] += .5
                progress.update()
            estimate = reports[-1]
            self.assertGreater(estimate["estimated_remaining_seconds"], 0)
            self.assertLess(estimate["eta_lower_seconds"], estimate["eta_upper_seconds"])
            self.assertEqual(estimate["eta_scope"], "search")
            progress.close()
            self.assertIsNone(reports[-1]["estimated_remaining_seconds"])

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
