"""Physical exposure durations stay distinct from sampling cadence."""
import io
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

import numpy as np

APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
sys.path.insert(0, str(APP_DIR))

import analysis
import parsers
import tls_search


def triangle_average(phase, half_width, exposure_days):
    """Independent analytic integral of a unit-depth triangular transit."""
    phase = np.asarray(phase)
    durations = np.broadcast_to(exposure_days, phase.shape)

    def primitive(x):
        return np.where(x <= -half_width, 0.0,
            np.where(x <= 0, (x + half_width) ** 2 / (2 * half_width),
                np.where(x < half_width, half_width / 2 + x - x ** 2 / (2 * half_width), half_width)))

    result = np.clip(1 - np.abs(phase) / half_width, 0, 1)
    finite = durations > 0
    result[finite] = (primitive(phase[finite] + durations[finite] / 2)
        - primitive(phase[finite] - durations[finite] / 2)) / durations[finite]
    return result


class ExposureParserTests(unittest.TestCase):
    def test_explicit_zero_override_is_preserved_and_negative_rejected(self):
        self.assertEqual(analysis.parse_detection_options({"exposureSeconds": SimpleNamespace(value="0")})["exposure_seconds"], 0)
        self.assertIsNone(analysis.parse_detection_options({})["exposure_seconds"])
        with self.assertRaises(ValueError):
            analysis.parse_detection_options({"exposureSeconds": SimpleNamespace(value="-1")})

    def test_csv_exposure_tracks_sort_quality_and_duplicate_cleaning(self):
        rows = ["Time,Flux,exposure_seconds,Quality"]
        rows += [f"{i},1,{i * 10},0" for i in range(29, -1, -1)]
        rows += ["10,.8,999,0", "31,1,100,1", "32,1,,0", "33,1,-10,0"]
        parsed = parsers.parse_csv_bytes("\n".join(rows).encode(), return_metadata=True)
        self.assertEqual(parsed["exposure_seconds"][10], 100)
        self.assertEqual(parsed["flux"][10], 1)
        self.assertTrue(np.isnan(parsed["exposure_seconds"][-2:]).all())
        self.assertEqual(parsed["input_metadata"]["exposure"]["known_rows"], 30)
        self.assertEqual(parsed["input_metadata"]["exposure"]["unknown_rows"], 2)
        self.assertEqual(parsed["cleaning"]["invalid_exposure_rows"], 2)
        self.assertTrue(parsed["cleaning"]["counts_reconcile"])

    def test_csv_explicit_exposure_days_are_independent_of_time_unit(self):
        raw = ("Time,Flux,exposure_days\n" + "\n".join(f"{i * 60},1,.001" for i in range(30))).encode()
        parsed = parsers.parse_csv_bytes(raw, return_metadata=True, time_unit="seconds")
        np.testing.assert_allclose(parsed["exposure_seconds"], 86.4)
        self.assertAlmostEqual(parsed["time"][1], 60 / 86400)

    def test_unlabelled_csv_exposure_and_cadence_are_not_assumed(self):
        raw = ("Time,Flux,exptime\n" + "\n".join(f"{i},1,10" for i in range(30))).encode()
        parsed = parsers.parse_csv_bytes(raw, return_metadata=True)
        self.assertIsNone(parsed["exposure_seconds"])
        self.assertEqual(parsed["input_metadata"]["exposure"]["unknown_rows"], 30)
        self.assertFalse(parsed["input_metadata"]["exposure"]["cadence_is_exposure"])

    @unittest.skipIf(parsers.fits is None, "astropy unavailable")
    def test_fits_per_row_exposure_uses_its_declared_units(self):
        fits = parsers.fits
        columns = [fits.Column(name="TIME", array=np.arange(30), format="D", unit="d"),
                   fits.Column(name="FLUX", array=np.ones(30), format="D"),
                   fits.Column(name="EXPTIME", array=np.full(30, 2.0), format="D", unit="min")]
        table = fits.BinTableHDU.from_columns(columns)
        table.header["TIMEDEL"] = .5
        table.header["TIMEUNIT"] = "d"
        table.header["EXPTIME"] = 3600.0
        output = io.BytesIO()
        fits.HDUList([fits.PrimaryHDU(), table]).writeto(output)
        parsed = parsers.parse_fits_bytes(output.getvalue(), return_metadata=True)
        np.testing.assert_allclose(parsed["exposure_seconds"], 120)
        metadata = parsed["input_metadata"]["exposure"]
        self.assertEqual(metadata["source"], "FITS per-row column")
        self.assertFalse(metadata["header_candidates"]["TIMEDEL"]["used_as_sample_exposure"])

    @unittest.skipIf(parsers.fits is None, "astropy unavailable")
    def test_fits_header_durations_do_not_become_per_sample_exposures(self):
        fits = parsers.fits
        columns = [fits.Column(name="TIME", array=np.arange(30), format="D", unit="s"),
                   fits.Column(name="FLUX", array=np.ones(30), format="D")]
        table = fits.BinTableHDU.from_columns(columns)
        table.header["TIMEDEL"] = 1.0
        table.header["EXPTIME"] = 30.0
        table.header["TIMEUNIT"] = "s"
        output = io.BytesIO()
        fits.HDUList([fits.PrimaryHDU(), table]).writeto(output)
        parsed = parsers.parse_fits_bytes(output.getvalue(), return_metadata=True)
        self.assertIsNone(parsed["exposure_seconds"])
        self.assertEqual(parsed["input_metadata"]["exposure"]["unknown_rows"], 30)
        self.assertEqual(parsed["input_metadata"]["exposure"]["header_candidates"]["EXPTIME"]["value"], 30)


class ExposureModelTests(unittest.TestCase):
    def test_midpoint_integral_matches_analytic_triangular_transit(self):
        phase = np.linspace(-.12, .12, 101)
        exposures = np.where(np.arange(len(phase)) % 2, 1800.0, 120.0)
        template_phase = np.linspace(-.5, .5, 20001)
        template_flux = 1 - .01 * triangle_average(template_phase, .04, 0)
        actual = tls_search.exposure_integrated_template(phase, template_phase, template_flux, 1.0, exposures)
        expected = 1 - .01 * triangle_average(phase, .04, exposures / 86400)
        np.testing.assert_allclose(actual, expected, atol=2e-6)
        self.assertGreater(actual[50], template_flux[len(template_flux) // 2])

    def test_zero_and_unknown_exposures_are_instantaneous_without_using_cadence(self):
        template_phase = np.linspace(-.5, .5, 2001)
        template_flux = 1 - .01 * triangle_average(template_phase, .04, 0)
        phase = np.array([-.03, 0, .03])
        expected = np.interp(phase, template_phase, template_flux)
        np.testing.assert_allclose(tls_search.exposure_integrated_template(phase, template_phase, template_flux, 1), expected)
        np.testing.assert_allclose(tls_search.exposure_integrated_template(phase, template_phase, template_flux, 1, 0), expected)
        with self.assertRaises(ValueError):
            tls_search.exposure_integrated_template(phase, template_phase, template_flux, 1, [1, 2])
        with self.assertRaises(ValueError):
            tls_search.exposure_integrated_template(phase, template_phase, template_flux, 1, -1)

    def test_whole_orbital_period_exposures_have_phase_independent_mean(self):
        period = .5
        template_phase = np.linspace(-period / 2, period / 2, 50001)
        template_flux = 1 - .01 * triangle_average(template_phase, .01, 0)
        phases = np.array([0.0, .05, .19, -.249])
        for exposure in (period * 86400, period * 86400 * 2):
            actual = tls_search.exposure_integrated_template(phases, template_phase, template_flux, period, exposure)
            # Triangle area .5 * .02 * .01 divided by period .5 = .0002.
            np.testing.assert_allclose(actual, .9998, atol=1e-13)

    def test_exposure_crossing_orbital_wrap_matches_dense_independent_average(self):
        period = .5
        template_phase = np.linspace(-period / 2, period / 2, 50001)
        template_flux = 1 - .01 * triangle_average(template_phase, .01, 0)
        phases = np.array([-.249, -.18, .04, .249])
        exposure = .67 * 86400
        offsets = (np.arange(200001) + .5) / 200001 * .67 - .67 / 2
        sample_phase = (phases[:, None] + offsets + period / 2) % period - period / 2
        expected = 1 - .01 * triangle_average(sample_phase.ravel(), .01, 0).reshape(sample_phase.shape).mean(axis=1)
        actual = tls_search.exposure_integrated_template(phases, template_phase, template_flux, period, exposure)
        np.testing.assert_allclose(actual, expected, atol=1e-10)

    def test_observation_aligned_model_uses_each_rows_exposure(self):
        phase = np.linspace(-.5, .5, 20001)
        model = {"folded_phase_days": phase, "folded_flux": 1 - .01 * triangle_average(phase, .04, 0)}
        actual = analysis.model_flux_at_observations(np.array([0.0, 1.0]), 1.0, 0.0, model, [0, 1800])
        self.assertAlmostEqual(actual[0], .99)
        self.assertAlmostEqual(actual[1], 1 - .01 * triangle_average(np.array([0.0]), .04, 1800 / 86400)[0], delta=2e-6)

    def test_mixed_cadence_duration_fit_uses_independent_exposures(self):
        rng = np.random.default_rng(42)
        time = np.r_[np.arange(0, 12, .002), np.arange(12, 36, .018)]
        time += rng.uniform(-.0002, .0002, len(time))
        period, epoch, duration = 1.4, .31, .08
        folded = (time - epoch + period / 2) % period - period / 2
        exposures = np.where(time < 12, 90, 1800)
        flux = 1 - .006 * triangle_average(folded, duration / 2, exposures / 86400)
        flux += rng.normal(0, .00015, len(time))
        model_phase = np.linspace(-period / 2, period / 2, 10001)
        seed = duration * 1.25
        model_flux = 1 - .006 * triangle_average(model_phase, seed / 2, 0)
        fit = tls_search.fit_observed_model_duration(time, flux, period, epoch, seed,
            model_phase, model_flux, exposure_seconds=exposures, flux_uncertainty=np.full(len(time), .00015))
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit["duration"], duration, delta=.004)
        self.assertGreater(fit["duration_uncertainty"], 0)
        self.assertEqual(fit["exposure"]["unknown_rows"], 0)
        self.assertLessEqual(fit["representative_sample_count"], 501 * 32)

    def test_shallow_instantaneous_fit_reports_unknown_exposure_limit(self):
        rng = np.random.default_rng(81)
        time = np.sort(rng.uniform(0, 35, 14000))
        period, epoch, duration = 1.6, .27, .09
        folded = (time - epoch + period / 2) % period - period / 2
        flux = 1 - .0006 * triangle_average(folded, duration / 2, 0)
        flux += rng.normal(0, .00012, len(time))
        model_phase = np.linspace(-period / 2, period / 2, 10001)
        model_flux = 1 - .0006 * triangle_average(model_phase, .11 / 2, 0)
        fit = tls_search.fit_observed_model_duration(time, flux, period, epoch, .11, model_phase, model_flux)
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit["duration"], duration, delta=.012)
        self.assertEqual(fit["exposure"]["unknown_rows"], len(time))
        self.assertIn("unknown exposure", fit["uncertainty_basis"])

    def test_joint_amplitudes_use_finite_exposures_for_overlapping_signals(self):
        time = np.linspace(0, 12, 6001)
        exposures = np.where(time < 6, 120, 1800)
        signals, shapes = [], []
        model_phase = np.linspace(-1.5, 1.5, 18001)
        for period, depth in ((2.0, .01), (3.0, .008)):
            model = {"folded_phase_days": model_phase,
                "folded_flux": 1 - depth * triangle_average(model_phase, .04, 0)}
            phase = (time - 1.0 + period / 2) % period - period / 2
            shapes.append(triangle_average(phase, .04, exposures / 86400))
            signals.append({"period": period, "period_epoch": 1.0, "transit_model": model})
        flux = 1.001 - .006 * shapes[0] - .003 * shapes[1]
        fit = analysis.joint_template_amplitudes(time, flux, signals,
            uncertainty=np.full(len(time), .0001), exposure_seconds=exposures)
        self.assertIsNotNone(fit)
        self.assertAlmostEqual(fit["depths"][0], .006, delta=1e-5)
        self.assertAlmostEqual(fit["depths"][1], .003, delta=1e-5)
        self.assertLess(float(np.std(fit["residual_flux"])), 1e-6)


if __name__ == "__main__":
    unittest.main()
