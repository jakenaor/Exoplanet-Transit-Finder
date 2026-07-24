import json
from pathlib import Path
import sys
from types import SimpleNamespace
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
    def test_zero_centered_ppm_flux_is_converted_before_segment_normalization(self):
        time_values = np.linspace(0.0, 20.0, 2001)
        residual_ppm = np.random.default_rng(14).normal(3.0, 110.0, len(time_values))
        residual_ppm[995:1006] -= 450.0

        normalized, segments = analysis.normalize_flux_by_segments(
            time_values,
            residual_ppm,
        )
        plan = analysis.flux_normalization_plan(residual_ppm)
        tls_flux, _ = analysis.normalized_flux_for_tls(time_values, residual_ppm)

        self.assertEqual(segments, [(0, len(time_values))])
        self.assertEqual(plan["input_representation"], "zero-centered residual flux (ppm)")
        self.assertEqual(plan["residual_scale"], 1000000.0)
        self.assertAlmostEqual(float(np.median(normalized)), 1.0, delta=1e-12)
        self.assertGreater(float(np.min(normalized)), 0.999)
        self.assertLess(float(np.max(normalized)), 1.001)
        self.assertAlmostEqual(float(np.median(tls_flux)), 1.0, delta=1e-12)
        self.assertGreater(float(np.min(tls_flux)), 0.999)
        self.assertLess(float(np.max(tls_flux)), 1.001)

    def test_absolute_relative_flux_keeps_fractional_transit_depth(self):
        time_values = np.linspace(0.0, 10.0, 1001)
        relative_flux = np.ones_like(time_values)
        relative_flux[495:506] = 0.99

        normalized, _ = analysis.normalize_flux_by_segments(
            time_values,
            relative_flux,
        )
        plan = analysis.flux_normalization_plan(relative_flux)

        self.assertEqual(plan["input_representation"], "absolute or relative flux")
        self.assertIsNone(plan["residual_scale"])
        self.assertAlmostEqual(float(np.median(normalized)), 1.0)
        self.assertAlmostEqual(float(np.min(normalized)), 0.99)

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

    def test_unfolded_tls_model_restores_gap_compressed_duration(self):
        period = 1.0
        centers = np.arange(0.5, 4.0, period)
        model_time = np.concatenate([
            np.linspace(center - period / 2.0, center + period / 2.0, 1001)
            for center in centers
        ])
        model_flux = np.concatenate([
            np.where(
                np.abs(np.linspace(-period / 2.0, period / 2.0, 1001)) <= 0.05,
                0.98,
                1.0,
            )
            for _ in centers
        ])
        folded_phase = np.linspace(0.0, 1.0, 1001)
        compressed_folded_flux = np.where(np.abs(folded_phase - 0.5) <= 0.025, 0.98, 1.0)
        fake_result = SimpleNamespace(
            period=period,
            duration=0.05,
            T0=centers[0],
            periods=np.asarray([0.9, period, 1.1]),
            power=np.asarray([1.0, 9.0, 1.0]),
            power_raw=np.asarray([1.0, 9.0, 1.0]),
            model_lightcurve_time=model_time,
            model_lightcurve_model=model_flux,
            model_folded_phase=folded_phase,
            model_folded_model=compressed_folded_flux,
            transit_times=centers,
            transit_depths=np.full(len(centers), 0.98),
            per_transit_count=np.full(len(centers), 100),
            transit_count=len(centers),
            distinct_transit_count=len(centers),
            empty_transit_count=0,
            depth=0.98,
            SDE=9.0,
            SDE_raw=9.0,
            FAP=0.001,
            snr=20.0,
        )
        fake_model = mock.Mock()
        fake_model.power.return_value = fake_result
        observed_time = np.r_[
            np.linspace(0.0, 1.0, 1001),
            np.linspace(3.0, 4.0, 1001),
        ]

        with mock.patch.object(tls_search, "transitleastsquares", return_value=fake_model):
            result = tls_search.run_tls_search(
                observed_time,
                np.ones_like(observed_time),
                {
                    "period_min": 0.8,
                    "period_max": 1.2,
                    "tls_threads": 1,
                },
            )

        self.assertAlmostEqual(result["folded_engine_duration"], 0.05, delta=0.002)
        self.assertAlmostEqual(result["duration"], 0.10, delta=0.002)
        self.assertAlmostEqual(result["unfolded_model_duration"], 0.10, delta=0.002)
        self.assertAlmostEqual(result["sampling_fill_factor"], 0.5, delta=0.002)
        self.assertAlmostEqual(result["uncompressed_duration"], 0.10, delta=0.002)
        self.assertEqual(
            result["duration_source"],
            "TLS duration with sampling-gap compression removed",
        )
        folded_phase = np.asarray(result["model"]["folded_phase_days"])
        folded_flux = np.asarray(result["model"]["folded_flux"])
        contact_indices = np.flatnonzero(
            np.isclose(np.abs(folded_phase), result["duration"] / 2.0)
        )
        self.assertEqual(contact_indices.size, 2)
        self.assertTrue(np.allclose(folded_flux[contact_indices], 1.0))

    def test_observed_duration_refinement_covers_ingress_and_egress(self):
        time_values = np.linspace(0.0, 8.0, 8001)
        period = 1.0
        epoch = 0.5
        phase = ((time_values - epoch + period / 2.0) % period) - period / 2.0
        flux_values = np.ones_like(time_values)
        flux_values[np.abs(phase) <= 0.05] = 0.98
        flux_values += np.random.default_rng(91).normal(0.0, 0.0001, len(flux_values))

        refinement = tls_search.observed_phase_folded_duration(
            time_values,
            flux_values,
            period,
            epoch,
            seed_duration=0.06,
        )

        self.assertIsNotNone(refinement)
        self.assertLessEqual(refinement["measured_start"], -0.049)
        self.assertGreaterEqual(refinement["measured_end"], 0.049)
        self.assertGreaterEqual(refinement["duration"], 0.10)
        self.assertLess(refinement["duration"], 0.13)

    def test_rescaled_folded_model_is_centered_inside_duration_box(self):
        phase = np.linspace(-0.5, 0.5, 1001)
        shifted_model = np.where(
            (phase >= -0.07) & (phase <= 0.03),
            0.98,
            1.0,
        )

        scaled_phase, scaled_flux = tls_search.rescale_folded_model_duration(
            phase,
            shifted_model,
            target_duration=0.06,
            period=1.0,
        )
        support = scaled_phase[scaled_flux < 0.999]
        left_contact = int(np.argmin(np.abs(scaled_phase + 0.03)))
        right_contact = int(np.argmin(np.abs(scaled_phase - 0.03)))

        self.assertAlmostEqual(float(scaled_phase[left_contact]), -0.03, delta=1e-9)
        self.assertAlmostEqual(float(scaled_phase[right_contact]), 0.03, delta=1e-9)
        self.assertAlmostEqual(float(scaled_flux[left_contact]), 1.0)
        self.assertAlmostEqual(float(scaled_flux[right_contact]), 1.0)
        self.assertGreater(float(np.min(support)), -0.03)
        self.assertLess(float(np.max(support)), 0.03)

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

    def test_smoothed_tls_box_bounds_cover_filter_radius(self):
        display_start, display_end = analysis.smoothed_transit_display_bounds(
            start=1.0,
            end=1.1,
            cadence=0.01,
            smooth_width=5,
            domain_min=0.0,
            domain_max=2.0,
        )

        self.assertAlmostEqual(display_start, 0.98)
        self.assertAlmostEqual(display_end, 1.12)

    def test_phase_folded_bins_preserve_individual_transit_shape(self):
        cadence = 10.0 / (24.0 * 60.0)
        time_values = np.arange(0.0, 60.0, cadence)
        period = 3.5
        epoch = 1.2
        duration = 0.15
        phase = ((time_values - epoch + period / 2.0) % period) - period / 2.0
        absolute_phase = np.abs(phase)
        transit_profile = np.zeros_like(phase)
        transit_profile[absolute_phase <= 0.045] = 1.0
        ingress = (absolute_phase > 0.045) & (absolute_phase < duration / 2.0)
        transit_profile[ingress] = (
            duration / 2.0 - absolute_phase[ingress]
        ) / (duration / 2.0 - 0.045)
        flux_values = 1.0 - 0.016 * transit_profile

        folded = analysis.build_phase_folded_plot(
            time_values,
            flux_values,
            flux_values,
            period,
            epoch,
            duration,
        )
        binned_phase = np.asarray(folded["binned_phase"])
        binned_flux = np.asarray(folded["binned_flux"])
        in_transit_bins = np.abs(binned_phase) <= duration / 2.0
        outside_transit = (np.abs(binned_phase) >= 0.11) & (np.abs(binned_phase) <= 0.18)

        self.assertGreaterEqual(np.count_nonzero(in_transit_bins), 16)
        self.assertLess(float(np.min(binned_flux[in_transit_bins])), 0.985)
        self.assertGreater(float(np.min(binned_flux[outside_transit])), 0.999)

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
