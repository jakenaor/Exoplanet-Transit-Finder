import json
from pathlib import Path
import sys
import unittest
from unittest import mock

import numpy as np


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
sys.path.insert(0, str(APP_DIR))

import analysis  # noqa: E402
import tls_search  # noqa: E402


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
    def test_tls_and_four_workers_are_defaults(self):
        options = analysis.parse_detection_options({})

        self.assertEqual(options["search_mode"], "tls")
        self.assertEqual(options["tls_threads"], 4)

        index_html = (APP_DIR / "static" / "index.html").read_text()
        app_js = (APP_DIR / "static" / "app.js").read_text()
        self.assertIn('<option value="tls" selected>Physical TLS</option>', index_html)
        self.assertIn('id="tlsThreadsInput" type="number" min="1" max="8" step="1" value="4"', index_html)
        self.assertIn("searchModeInput.value = 'tls';", app_js)
        self.assertIn("tlsThreadsInput.value = '4';", app_js)

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

    def test_model_compaction_preserves_narrow_transit_bottoms(self):
        time_values = np.arange(200000, dtype=float)
        flux_values = np.ones_like(time_values)
        transit_indices = np.arange(1000, 199000, 5000)
        flux_values[transit_indices] = 0.975

        compact_time, compact_flux = tls_search.compact_model(
            time_values,
            flux_values,
            max_points=2000,
        )

        kept_times = set(np.asarray(compact_time, dtype=int).tolist())
        self.assertTrue(set(transit_indices.tolist()).issubset(kept_times))
        self.assertEqual(min(compact_flux), 0.975)
        self.assertLessEqual(len(compact_time), 2000)

    def test_duration_is_measured_from_folded_physical_model(self):
        phase = np.linspace(-0.5, 0.5, 10001)
        flux = np.ones_like(phase)
        flux[np.abs(phase) <= 0.02] = 0.98

        duration = tls_search.duration_from_folded_model(phase, flux, period=1.0)

        self.assertAlmostEqual(duration, 0.04, delta=0.0003)

    def test_observation_aligned_model_keeps_every_visible_transit(self):
        time_values = np.linspace(0.0, 10.0, 10001)
        period = 1.0
        epoch = 0.2
        folded_phase = np.linspace(-0.5, 0.5, 2001)
        transit_shape = np.clip(1.0 - np.abs(folded_phase) / 0.025, 0.0, 1.0)
        folded_flux = 1.0 - 0.02 * transit_shape
        model = {
            "folded_phase_days": folded_phase.tolist(),
            "folded_flux": folded_flux.tolist(),
        }

        aligned = analysis.model_flux_at_observations(
            time_values,
            period,
            epoch,
            model,
        )
        smoothed = analysis.moving_average_by_segments(
            aligned,
            21,
            [(0, len(time_values))],
        )
        keep = analysis.downsample_indices_for_series(
            [np.ones_like(smoothed), smoothed],
            max_points=400,
        )
        compact_time = time_values[keep]
        compact_flux = smoothed[keep]

        for center in np.arange(epoch, time_values[-1], period):
            nearby = np.abs(compact_time - center) <= 0.03
            self.assertTrue(np.any(nearby), f"missing model samples near {center}")
            self.assertLess(float(np.min(compact_flux[nearby])), 0.99)

    def test_plot_smoothing_cannot_average_over_whole_transit(self):
        cadence = 2.0 / (24.0 * 60.0)
        duration = 0.0232

        width = analysis.transit_preserving_smoothing_width(
            requested_width=95,
            cadence=cadence,
            duration=duration,
        )

        self.assertEqual(width, 5)
        self.assertLess(width * cadence, duration / 2.0)

    def test_segment_smoothing_does_not_bridge_observation_gaps(self):
        values = np.r_[np.zeros(20), np.ones(20)]
        smoothed = analysis.moving_average_by_segments(
            values,
            9,
            [(0, 20), (20, 40)],
        )

        self.assertTrue(np.allclose(smoothed[:20], 0.0))
        self.assertTrue(np.allclose(smoothed[20:], 1.0))


if __name__ == "__main__":
    unittest.main()
