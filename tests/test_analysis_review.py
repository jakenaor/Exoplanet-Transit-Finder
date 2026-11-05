import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"))
import analysis
import tls_search


class EventEvidenceTests(unittest.TestCase):
    def test_search_edge_warning_uses_local_period_scale(self):
        for period, lower, upper, sigma, expected in [
            (.81347, .5, 245, .000026, False),
            (1.3382, .5, 253, .000074, False),
            (.50001, .5, 245, .000001, True),
            (244.99, .5, 245, .000001, True),
            (2.18, 1, 2.2, .01, True),
        ]:
            with self.subTest(period=period, bounds=(lower, upper)):
                _, warnings = analysis.build_candidate_diagnostics([], {
                    "period": period, "period_method": "TLS", "period_uncertainty": sigma,
                    "period_search": {"min_period": lower, "max_period": upper},
                })
                self.assertEqual(any(w["title"] == "Period peak near search edge" for w in warnings), expected)

    def windows(self, time, flux, centers=(1.0, 3.0, 5.0), duration=0.2):
        return analysis.transits_from_tls_result(time, flux, {
            "period": 2.0, "duration": duration, "transit_time": 1.0,
            "tls_result": {"transit_times": centers, "per_transit_count": [0, 0, 0],
                           "transit_depth_fractions": [0.02, 0.02, 0.02]},
        })

    def test_flat_ephemeris_windows_do_not_become_observed_events(self):
        time = np.linspace(0, 6, 3001)
        windows = self.windows(time, np.ones(len(time)))
        self.assertEqual(len(windows), 3)
        self.assertTrue(all(w["state"] == "unsupported_window" for w in windows))
        self.assertTrue(all(w["depth"] == 0 and w["measured_center"] is None for w in windows))
        detection = {"period": 2, "period_epoch": 1, "period_method": "TLS", "period_duration": .2,
                     "period_sde": 9, "tls_snr": 20, "tls_fap": None, "tls": {}}
        diagnostics, warnings = analysis.build_candidate_diagnostics(windows, detection)
        assessment = analysis.build_planet_assessment(windows, detection, diagnostics, warnings)
        self.assertEqual(diagnostics["supported_event_count"], 0)
        self.assertIsNone(diagnostics["ephemeris_match_fraction"])
        self.assertNotEqual(assessment["status"], "strong_candidate")
        self.assertFalse(any("ephemeris" in item["title"].lower() for item in assessment["supporting_evidence"]))
        self.assertFalse(any("false-alarm" in item["title"].lower() for item in assessment["supporting_evidence"]))

    def test_final_window_counts_and_negative_depth_are_measured(self):
        time = np.linspace(0, 6, 3001)
        flux = np.ones(len(time))
        flux[np.abs(time - 1) <= .1] += .01
        windows = self.windows(time, flux)
        first = windows[0]
        self.assertGreaterEqual(first["points"], 99)
        self.assertLess(first["signed_depth"], 0)
        self.assertEqual(first["state"], "unsupported_window")

    def test_local_centroid_is_not_copied_from_ephemeris(self):
        time = np.linspace(0, 6, 6001)
        flux = 1 + np.random.default_rng(201).normal(0, .0002, len(time))
        for center in (1.025, 3.025, 5.025):
            flux -= .01 * np.clip(1 - np.abs(time - center) / .055, 0, 1)
        windows = self.windows(time, flux)
        self.assertTrue(all(w["state"] == "supported_dip" for w in windows))
        for window in windows:
            self.assertAlmostEqual(window["measured_center"] - window["center"], .025, delta=.008)
            self.assertGreater(window["timing_uncertainty"], 0)

    def test_cycle_parity_survives_a_missing_cycle(self):
        windows = [{"center": c, "cycle_number": n, "depth": d, "points": 30,
                    "duration": .1, "state": "supported_dip"}
                   for c, n, d in [(1, 0, .01), (3, 1, .02), (7, 3, .02), (9, 4, .01)]]
        diagnostics, _ = analysis.build_candidate_diagnostics(windows, {"period": 2, "period_epoch": 1})
        self.assertEqual(diagnostics["odd_depth"], .02)
        self.assertEqual(diagnostics["even_depth"], .01)

    def test_gap_separates_trends_and_local_baselines(self):
        time = np.r_[np.linspace(0, 2, 300), np.linspace(10, 12, 300)]
        flux = np.r_[np.ones(300), np.ones(300) * 1.05]
        flattened = analysis.flattened_flux_for_period_search(time, flux)
        self.assertLess(np.max(np.abs(flattened)), 1e-12)
        windows = self.windows(time, flux, centers=(1.95, 6.0, 10.05))
        self.assertEqual(windows[1]["state"], "outside_observations")
        self.assertAlmostEqual(windows[0]["local_baseline"], 1.0)
        self.assertAlmostEqual(windows[2]["local_baseline"], 1.05)

    def test_phase_bins_include_counts_and_uncertainties(self):
        time = np.linspace(0, 6, 1201)
        flux = 1 + np.random.default_rng(8).normal(0, .001, len(time))
        plot = analysis.build_phase_folded_plot(time, flux, flux, 2.0, 1.0, .1)
        self.assertEqual(sum(plot["binned_count"]), len(time))
        self.assertEqual(len(plot["binned_uncertainty"]), len(plot["binned_flux"]))
        json.dumps(plot, allow_nan=False)

    def test_two_transit_option_changes_automatic_search_bounds(self):
        _, maximum = analysis.period_search_bounds(.001, 24, {"tls_min_transits": 2})
        self.assertEqual(maximum, 12)

    def test_exploratory_local_features_keep_unassigned_dips_without_scoring_them(self):
        time = np.r_[np.linspace(0, 2, 1001), np.linspace(10, 12, 1001)]
        flux = 1 + np.random.default_rng(18).normal(0, .0001, len(time))
        for center in (.8, 10.8):
            flux -= .02 * np.clip(1 - np.abs(time - center) / .05, 0, 1)
        dips, metadata = analysis.exploratory_local_dips(time, flux, analysis.DEFAULT_DETECTION_OPTIONS, 0.0)
        self.assertGreaterEqual(len(dips), 2)
        result = {"time_reference": 0.0, "exploratory_dips": dips,
                  "planet_assessment": {"candidate_score": 12},
                  "predicted_windows": [{"start": .7, "end": .9}]}
        analysis.tag_exploratory_assignments(result, [result])
        self.assertTrue(any(dip["assignment"] == "unassigned" for dip in dips))
        self.assertTrue(any(dip["assignment"] == "overlaps_predicted_window" for dip in dips))
        self.assertTrue(all(dip["validated"] is False for dip in dips))
        self.assertEqual(result["planet_assessment"]["candidate_score"], 12)
        self.assertIn("never", metadata["interpretation"])


class ConditionalDurationTests(unittest.TestCase):
    def test_joint_amplitudes_recover_overlapping_seeded_templates(self):
        time = np.linspace(0, 12, 6001)
        phase = np.linspace(-1.5, 1.5, 3001)
        shape = np.clip(1 - np.abs(phase) / .08, 0, 1)
        signals = []
        evaluated_shapes = []
        for index, (period, prior_depth) in enumerate([(2.0, .015), (3.0, .010)]):
            signal = {"signal_id": f"signal-{index + 1}", "label": f"Signal {index + 1}",
                      "period": period, "period_epoch": 1.0,
                      "transit_model": {"folded_phase_days": phase.tolist(), "folded_flux": (1 - prior_depth * shape).tolist()}}
            aligned = analysis.model_flux_at_observations(time, period, 1.0, signal["transit_model"])
            evaluated_shapes.append((1 - aligned) / prior_depth)
            signals.append(signal)
        flux = 1.001 - .006 * evaluated_shapes[0] - .003 * evaluated_shapes[1]
        flux += np.random.default_rng(20261105).normal(0, .0002, len(time))
        joint = analysis.joint_template_amplitudes(time, flux, signals)
        self.assertIsNotNone(joint)
        self.assertGreater(joint["metadata"]["overlapping_sample_count"], 0)
        self.assertAlmostEqual(joint["baseline"], 1.001, delta=.00005)
        self.assertAlmostEqual(joint["depths"][0], .006, delta=.00010)
        self.assertAlmostEqual(joint["depths"][1], .003, delta=.00010)
        self.assertLess(float(np.std(joint["residual_flux"])), .00022)
        analysis.update_signal_joint_depth(signals[0], joint["depths"][0], joint["depth_uncertainties"][0])
        self.assertAlmostEqual(1 - min(signals[0]["transit_model"]["folded_flux"]), joint["depths"][0])
        self.assertEqual(signals[0]["period"], 2.0)

    def test_collective_shallow_tls_signal_does_not_require_three_individual_detections(self):
        import validate_updates
        _, time, flux, _, _ = next(case for case in validate_updates.fixtures() if case[0] == "shallow_600ppm")
        options = {**analysis.DEFAULT_DETECTION_OPTIONS, "min_period": 1.4, "max_period": 3.5,
                   "tls_oversampling": 2, "tls_threads": 1}
        options["_flux_uncertainty"] = [.0008] * len(time)
        options["_flux_uncertainty"][0] = None
        result = analysis.analyze(time + 2459000, flux, options)
        self.assertIn(result["planet_assessment"]["status"], ("possible_candidate", "strong_candidate"))
        self.assertLess(len(result["observed_events"]), 3)
        self.assertTrue(result["diagnostics"]["combined_signal_supported"])
        self.assertAlmostEqual(result["period"], 2.4, delta=.025)
        self.assertTrue(any("combined" in evidence["title"].lower() for evidence in result["planet_assessment"]["supporting_evidence"]))
        self.assertIsNone(result["plot"]["flux_uncertainty"][0])
        self.assertIn("unweighted fallback", result["uncertainty_usage"])
        self.assertNotIn("_flux_uncertainty", result["detection_options"])
        json.dumps(result, allow_nan=False)

    def test_template_duration_can_shorten_and_estimates_uncertainty(self):
        time = np.linspace(0, 8, 8001)
        period, epoch, truth = 1.0, .5, .1
        phase = ((time - epoch + period/2) % period) - period/2
        flux = 1 - .01 * np.clip(1 - np.abs(phase) / (truth / 2), 0, 1)
        flux += np.random.default_rng(9).normal(0, .0002, len(time))
        model_phase = np.linspace(-.5, .5, 3001)
        model = 1 - .01 * np.clip(1 - np.abs(model_phase) / .065, 0, 1)
        result = tls_search.fit_observed_model_duration(time, flux, period, epoch, .13, model_phase, model)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result["duration"], truth, delta=.012)
        self.assertLess(result["duration"], .13)
        self.assertGreater(result["duration_uncertainty"], 0)


if __name__ == "__main__":
    unittest.main()
