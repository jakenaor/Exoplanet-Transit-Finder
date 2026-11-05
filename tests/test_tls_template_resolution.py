"""Gaps must not replace a dense physical template with a few model knots."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

import numpy as np

APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
sys.path.insert(0, str(APP_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tls_search
import validate_updates


def shape(phase, duration):
    return np.clip(1 - (2 * np.asarray(phase) / duration) ** 2, 0, 1)


class DenseTemplateTests(unittest.TestCase):
    def mocked_result(self, gap):
        observed = np.r_[np.linspace(0, 1, 1001), np.linspace(gap - 1, gap, 1001)]
        fill = tls_search.sampling_fill_factor(observed)
        period, duration = 1.0, .1
        centers = np.arange(.5, gap, period)
        coarse_phase = np.linspace(-.5, .5, 41)
        model_time = np.concatenate([center + coarse_phase for center in centers])
        model_flux = np.tile(1 - .01 * shape(coarse_phase, duration), len(centers))
        phase = np.linspace(0, 1, 120001)
        folded = 1 - .01 * shape(phase - .5, duration * (1 + fill) / 2)
        return observed, SimpleNamespace(period=period, duration=duration * fill,
            T0=.5, periods=np.asarray([.9, 1, 1.1]), power=np.asarray([1, 9, 1]),
            power_raw=np.asarray([1, 9, 1]), model_lightcurve_time=model_time,
            model_lightcurve_model=model_flux, model_folded_phase=phase,
            model_folded_model=folded, transit_times=centers, SDE=9.0, depth=.99)

    def test_coarse_unfolded_cycle_does_not_replace_dense_folded_shape(self):
        observed, engine_result = self.mocked_result(100)
        engine = mock.Mock()
        engine.power.return_value = engine_result
        with mock.patch.object(tls_search, "transitleastsquares", return_value=engine), \
             mock.patch.object(tls_search, "fit_observed_model_duration", return_value=None) as fit:
            result = tls_search.run_tls_search(observed, np.ones(len(observed)), {"period_min": .8, "period_max": 1.2})
        self.assertEqual(result["template_source"], "engine folded template")
        self.assertLess(result["template_resolution"]["engine_unfolded_contact_samples"], 10)
        self.assertGreater(result["template_resolution"]["retained_contact_samples"], 1000)
        self.assertAlmostEqual(result["duration"], .1, places=8)
        self.assertGreater(tls_search.model_contact_sample_count(fit.call_args[0][6]), 1000)
        phase = np.asarray(result["model"]["folded_phase_days"])
        flux = np.asarray(result["model"]["folded_flux"])
        np.testing.assert_allclose(flux[np.isclose(np.abs(phase), .05)], 1.0, atol=1e-12)
        held_out = np.linspace(-.2, .2, 1001)
        np.testing.assert_allclose(np.interp(held_out, phase, flux), 1 - .01 * shape(held_out, .1), atol=1e-5)

    def test_empty_epochs_do_not_change_retained_observed_shape(self):
        curves = []
        for gap in (10, 100):
            observed, engine_result = self.mocked_result(gap)
            engine = mock.Mock()
            engine.power.return_value = engine_result
            with mock.patch.object(tls_search, "transitleastsquares", return_value=engine), \
                 mock.patch.object(tls_search, "fit_observed_model_duration", return_value=None):
                result = tls_search.run_tls_search(observed, np.ones(len(observed)), {"period_min": .8, "period_max": 1.2})
            curves.append(np.interp(np.linspace(-.15, .15, 1001),
                result["model"]["folded_phase_days"], result["model"]["folded_flux"]))
        np.testing.assert_allclose(curves[0], curves[1], atol=1e-5)

    def test_reference_fallback_cannot_silently_drop_requested_bounds(self):
        for best_period, grid in ((1.3, [.9, 1.0, 1.1]), (1.0, [.6, 1.0, 1.3])):
            observed, engine_result = self.mocked_result(10)
            engine_result.period = best_period
            engine_result.periods = np.asarray(grid)
            engine = mock.Mock()
            engine.power.return_value = engine_result
            with mock.patch.object(tls_search, "transitleastsquares", return_value=engine):
                with self.assertRaisesRegex(ValueError, "outside requested bounds.*oversampling"):
                    tls_search.run_tls_search(observed, np.ones(len(observed)), {"period_min": .8, "period_max": 1.2})

    def test_small_real_gapped_tls_fixture_keeps_independent_dense_shape(self):
        time = np.r_[np.linspace(0, 6, 700), np.linspace(100, 106, 700)]
        flux, truth = validate_updates.injected(time, period=2.4, epoch=.7)
        flux += np.random.default_rng(20261105).normal(0, .0004, len(time))
        result = tls_search.run_tls_search(time, flux, {"period_min": 1.4, "period_max": 3.5,
            "tls_oversampling": 1, "tls_threads": 1, "exposure_seconds": 0})
        self.assertAlmostEqual(result["period"], truth["period_days"], delta=.02)
        self.assertEqual(result["template_source"], "engine folded template")
        resolution = result["template_resolution"]
        self.assertGreater(resolution["engine_folded_contact_samples"], resolution["engine_unfolded_contact_samples"])
        self.assertGreater(resolution["retained_contact_samples"], 20)
        self.assertAlmostEqual(result["duration"], truth["duration_days"], delta=truth["duration_days"] * .2)


if __name__ == "__main__":
    unittest.main()
