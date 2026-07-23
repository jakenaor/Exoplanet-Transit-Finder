import json
from pathlib import Path
import sys
import unittest
from unittest import mock

import numpy as np


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
sys.path.insert(0, str(APP_DIR))

import analysis  # noqa: E402


class FormItem:
    def __init__(self, value):
        self.value = value


def tls_options(**overrides):
    options = dict(analysis.DEFAULT_DETECTION_OPTIONS)
    options.update({
        "search_mode": "tls",
        "min_period": 1.5,
        "max_period": 3.5,
        "tls_oversampling": 2,
        "tls_threads": 1,
    })
    options.update(overrides)
    return options


def synthetic_light_curve(seed=4, depth=0.006):
    time = np.linspace(2459000.0, 2459012.0, 1200)
    period = 2.4
    epoch = 2459000.7
    duration = 0.14
    phase = ((time - epoch + period / 2.0) % period) - period / 2.0
    triangular_core = np.clip(1.0 - np.abs(phase) / (duration / 2.0), 0.0, 1.0)
    transit_shape = (0.25 + 0.75 * triangular_core) * (np.abs(phase) < duration / 2.0)
    flux = 1.0 - depth * transit_shape
    flux += np.random.default_rng(seed).normal(0.0, 0.0008, len(time))
    return time, flux, period


class TLSOptionTests(unittest.TestCase):
    def test_parses_physical_tls_options(self):
        options = analysis.parse_detection_options({
            "searchMode": FormItem("tls"),
            "tlsTemplate": FormItem("grazing"),
            "stellarRadius": FormItem("0.82"),
            "stellarMass": FormItem("0.77"),
            "limbDarkeningU1": FormItem("0.42"),
            "limbDarkeningU2": FormItem("0.18"),
            "tlsOversampling": FormItem("4"),
            "tlsMinTransits": FormItem("2"),
            "tlsThreads": FormItem("2"),
            "tlsMinDepthPpm": FormItem("25"),
            "tlsDurationGridStep": FormItem("1.08"),
        })
        self.assertEqual(options["search_mode"], "tls")
        self.assertEqual(options["tls_template"], "grazing")
        self.assertEqual(options["tls_oversampling"], 4)
        self.assertEqual(options["tls_min_transits"], 2)
        self.assertAlmostEqual(options["stellar_radius"], 0.82)
        self.assertAlmostEqual(options["limb_darkening_u2"], 0.18)

    def test_requires_both_limb_darkening_coefficients(self):
        with self.assertRaisesRegex(ValueError, "Both limbDarkening"):
            analysis.parse_detection_options({
                "searchMode": FormItem("tls"),
                "limbDarkeningU1": FormItem("0.4"),
            })


class TLSSearchTests(unittest.TestCase):
    def test_recovers_transit_with_reference_tls(self):
        time, flux, injected_period = synthetic_light_curve()
        result = analysis.analyze(time, flux, tls_options())

        self.assertEqual(result["period_method"], "TLS")
        self.assertAlmostEqual(result["period"], injected_period, delta=0.02)
        self.assertGreaterEqual(result["period_sde"], 7.0)
        self.assertLessEqual(result["tls_fap"], 0.01)
        self.assertGreaterEqual(len(result["transits"]), 4)
        self.assertTrue(all(item.get("source") == "TLS model" for item in result["transits"]))
        self.assertGreater(len(result["transit_model"]["folded_phase_days"]), 100)
        self.assertEqual(result["planet_assessment"]["status"], "strong_candidate")
        json.dumps(result)

    def test_noise_does_not_become_candidate(self):
        time = np.linspace(2459000.0, 2459012.0, 1200)
        flux = 1.0 + np.random.default_rng(41).normal(0.0, 0.0008, len(time))
        result = analysis.analyze(time, flux, tls_options())

        self.assertLess(result["period_sde"], 5.0)
        self.assertEqual(result["planet_assessment"]["status"], "no_planet_like_signal")
        self.assertLessEqual(result["planet_assessment"]["candidate_score"], 44)

    def test_bls_runtime_failure_uses_binned_fallback(self):
        class BrokenBLS:
            def __init__(self, *args, **kwargs):
                pass

            def power(self, *args, **kwargs):
                raise RuntimeError("forced BLS failure")

        sentinel = {"method": "binned BLS fallback", "period": 2.0}
        time = np.linspace(0.0, 10.0, 100)
        flux = np.ones_like(time)
        with mock.patch.object(analysis, "BoxLeastSquares", BrokenBLS), mock.patch.object(
            analysis,
            "estimate_period_with_binned_bls",
            return_value=sentinel,
        ) as fallback:
            result = analysis.estimate_period_with_bls(time, flux)

        self.assertIs(result, sentinel)
        fallback.assert_called_once()


if __name__ == "__main__":
    unittest.main()
