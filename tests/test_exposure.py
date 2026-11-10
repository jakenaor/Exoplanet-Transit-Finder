"""Physical exposure durations stay distinct from sampling cadence."""
import io as Io
from pathlib import Path
import sys as Sys
import unittest as Unittest
from types import SimpleNamespace

import numpy as Np

APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
Sys.path.insert(0, str(APP_DIR))

import analysis as Analysis
import parsers as Parsers
import tls_search as TlsSearch


#MARK: triangle average
def TriangleAverage(Phase, HalfWidth, ExposureDays):
    """Independent analytic integral of a unit-depth triangular transit."""
    Phase = Np.asarray(Phase)
    Durations = Np.broadcast_to(ExposureDays, Phase.shape)

    def Primitive(X):
        return Np.where(X <= -HalfWidth, 0.0,
            Np.where(X <= 0, (X + HalfWidth) ** 2 / (2 * HalfWidth),
                Np.where(X < HalfWidth, HalfWidth / 2 + X - X ** 2 / (2 * HalfWidth), HalfWidth)))

    Result = Np.clip(1 - Np.abs(Phase) / HalfWidth, 0, 1)
    Finite = Durations > 0
    Result[Finite] = (Primitive(Phase[Finite] + Durations[Finite] / 2)
        - Primitive(Phase[Finite] - Durations[Finite] / 2)) / Durations[Finite]
    return Result


#MARK: exposure model
class ExposureParserTests(Unittest.TestCase):
    def testExplicitZeroOverrideIsPreservedAndNegativeRejected(self):
        self.assertEqual(Analysis.ParseDetectionOptions({"exposureSeconds": SimpleNamespace(value="0")})["exposure_seconds"], 0)
        self.assertIsNone(Analysis.ParseDetectionOptions({})["exposure_seconds"])
        with self.assertRaises(ValueError):
            Analysis.ParseDetectionOptions({"exposureSeconds": SimpleNamespace(value="-1")})

    def testCsvExposureTracksSortQualityAndDuplicateCleaning(self):
        Rows = ["Time,Flux,exposure_seconds,Quality"]
        Rows += [f"{I},1,{I * 10},0" for I in range(29, -1, -1)]
        Rows += ["10,.8,999,0", "31,1,100,1", "32,1,,0", "33,1,-10,0"]
        Parsed = Parsers.ParseCsvBytes("\n".join(Rows).encode(), ReturnMetadata=True)
        self.assertEqual(Parsed["exposure_seconds"][10], 100)
        self.assertEqual(Parsed["flux"][10], 1)
        self.assertTrue(Np.isnan(Parsed["exposure_seconds"][-2:]).all())
        self.assertEqual(Parsed["input_metadata"]["exposure"]["known_rows"], 30)
        self.assertEqual(Parsed["input_metadata"]["exposure"]["unknown_rows"], 2)
        self.assertEqual(Parsed["cleaning"]["invalid_exposure_rows"], 2)
        self.assertTrue(Parsed["cleaning"]["counts_reconcile"])

    def testCsvExplicitExposureDaysAreIndependentOfTimeUnit(self):
        Raw = ("Time,Flux,exposure_days\n" + "\n".join(f"{I * 60},1,.001" for I in range(30))).encode()
        Parsed = Parsers.ParseCsvBytes(Raw, ReturnMetadata=True, TimeUnit="seconds")
        Np.testing.assert_allclose(Parsed["exposure_seconds"], 86.4)
        self.assertAlmostEqual(Parsed["time"][1], 60 / 86400)

    def testUnlabelledCsvExposureAndCadenceAreNotAssumed(self):
        Raw = ("Time,Flux,exptime\n" + "\n".join(f"{I},1,10" for I in range(30))).encode()
        Parsed = Parsers.ParseCsvBytes(Raw, ReturnMetadata=True)
        self.assertIsNone(Parsed["exposure_seconds"])
        self.assertEqual(Parsed["input_metadata"]["exposure"]["unknown_rows"], 30)
        self.assertFalse(Parsed["input_metadata"]["exposure"]["cadence_is_exposure"])

    @Unittest.skipIf(Parsers.Fits is None, "astropy unavailable")
    def testFitsPerRowExposureUsesItsDeclaredUnits(self):
        Fits = Parsers.Fits
        Columns = [Fits.Column(name="TIME", array=Np.arange(30), format="D", unit="d"),
                   Fits.Column(name="FLUX", array=Np.ones(30), format="D"),
                   Fits.Column(name="EXPTIME", array=Np.full(30, 2.0), format="D", unit="min")]
        Table = Fits.BinTableHDU.from_columns(Columns)
        Table.header["TIMEDEL"] = .5
        Table.header["TIMEUNIT"] = "d"
        Table.header["EXPTIME"] = 3600.0
        Output = Io.BytesIO()
        Fits.HDUList([Fits.PrimaryHDU(), Table]).writeto(Output)
        Parsed = Parsers.ParseFitsBytes(Output.getvalue(), ReturnMetadata=True)
        Np.testing.assert_allclose(Parsed["exposure_seconds"], 120)
        Metadata = Parsed["input_metadata"]["exposure"]
        self.assertEqual(Metadata["source"], "FITS per-row column")
        self.assertFalse(Metadata["header_candidates"]["TIMEDEL"]["used_as_sample_exposure"])

    @Unittest.skipIf(Parsers.Fits is None, "astropy unavailable")
    def testFitsHeaderDurationsDoNotBecomePerSampleExposures(self):
        Fits = Parsers.Fits
        Columns = [Fits.Column(name="TIME", array=Np.arange(30), format="D", unit="s"),
                   Fits.Column(name="FLUX", array=Np.ones(30), format="D")]
        Table = Fits.BinTableHDU.from_columns(Columns)
        Table.header["TIMEDEL"] = 1.0
        Table.header["EXPTIME"] = 30.0
        Table.header["TIMEUNIT"] = "s"
        Output = Io.BytesIO()
        Fits.HDUList([Fits.PrimaryHDU(), Table]).writeto(Output)
        Parsed = Parsers.ParseFitsBytes(Output.getvalue(), ReturnMetadata=True)
        self.assertIsNone(Parsed["exposure_seconds"])
        self.assertEqual(Parsed["input_metadata"]["exposure"]["unknown_rows"], 30)
        self.assertEqual(Parsed["input_metadata"]["exposure"]["header_candidates"]["EXPTIME"]["value"], 30)


#MARK: exposure model
class ExposureModelTests(Unittest.TestCase):
    def testMidpointIntegralMatchesAnalyticTriangularTransit(self):
        Phase = Np.linspace(-.12, .12, 101)
        Exposures = Np.where(Np.arange(len(Phase)) % 2, 1800.0, 120.0)
        TemplatePhase = Np.linspace(-.5, .5, 20001)
        TemplateFlux = 1 - .01 * TriangleAverage(TemplatePhase, .04, 0)
        Actual = TlsSearch.ExposureIntegratedTemplate(Phase, TemplatePhase, TemplateFlux, 1.0, Exposures)
        Expected = 1 - .01 * TriangleAverage(Phase, .04, Exposures / 86400)
        Np.testing.assert_allclose(Actual, Expected, atol=2e-6)
        self.assertGreater(Actual[50], TemplateFlux[len(TemplateFlux) // 2])

    def testZeroAndUnknownExposuresAreInstantaneousWithoutUsingCadence(self):
        TemplatePhase = Np.linspace(-.5, .5, 2001)
        TemplateFlux = 1 - .01 * TriangleAverage(TemplatePhase, .04, 0)
        Phase = Np.array([-.03, 0, .03])
        Expected = Np.interp(Phase, TemplatePhase, TemplateFlux)
        Np.testing.assert_allclose(TlsSearch.ExposureIntegratedTemplate(Phase, TemplatePhase, TemplateFlux, 1), Expected)
        Np.testing.assert_allclose(TlsSearch.ExposureIntegratedTemplate(Phase, TemplatePhase, TemplateFlux, 1, 0), Expected)
        with self.assertRaises(ValueError):
            TlsSearch.ExposureIntegratedTemplate(Phase, TemplatePhase, TemplateFlux, 1, [1, 2])
        with self.assertRaises(ValueError):
            TlsSearch.ExposureIntegratedTemplate(Phase, TemplatePhase, TemplateFlux, 1, -1)

    def testWholeOrbitalPeriodExposuresHavePhaseIndependentMean(self):
        Period = .5
        TemplatePhase = Np.linspace(-Period / 2, Period / 2, 50001)
        TemplateFlux = 1 - .01 * TriangleAverage(TemplatePhase, .01, 0)
        Phases = Np.array([0.0, .05, .19, -.249])
        for Exposure in (Period * 86400, Period * 86400 * 2):
            Actual = TlsSearch.ExposureIntegratedTemplate(Phases, TemplatePhase, TemplateFlux, Period, Exposure)
            # triangle area .5 * .02 * .01 divided by period .5 = .0002.
            Np.testing.assert_allclose(Actual, .9998, atol=1e-13)

    def testExposureCrossingOrbitalWrapMatchesDenseIndependentAverage(self):
        Period = .5
        TemplatePhase = Np.linspace(-Period / 2, Period / 2, 50001)
        TemplateFlux = 1 - .01 * TriangleAverage(TemplatePhase, .01, 0)
        Phases = Np.array([-.249, -.18, .04, .249])
        Exposure = .67 * 86400
        Offsets = (Np.arange(200001) + .5) / 200001 * .67 - .67 / 2
        SamplePhase = (Phases[:, None] + Offsets + Period / 2) % Period - Period / 2
        Expected = 1 - .01 * TriangleAverage(SamplePhase.ravel(), .01, 0).reshape(SamplePhase.shape).mean(axis=1)
        Actual = TlsSearch.ExposureIntegratedTemplate(Phases, TemplatePhase, TemplateFlux, Period, Exposure)
        Np.testing.assert_allclose(Actual, Expected, atol=1e-10)

    def testObservationAlignedModelUsesEachRowsExposure(self):
        Phase = Np.linspace(-.5, .5, 20001)
        Model = {"folded_phase_days": Phase, "folded_flux": 1 - .01 * TriangleAverage(Phase, .04, 0)}
        Actual = Analysis.ModelFluxAtObservations(Np.array([0.0, 1.0]), 1.0, 0.0, Model, [0, 1800])
        self.assertAlmostEqual(Actual[0], .99)
        self.assertAlmostEqual(Actual[1], 1 - .01 * TriangleAverage(Np.array([0.0]), .04, 1800 / 86400)[0], delta=2e-6)

    def testMixedCadenceDurationFitUsesIndependentExposures(self):
        Rng = Np.random.default_rng(42)
        Time = Np.r_[Np.arange(0, 12, .002), Np.arange(12, 36, .018)]
        Time += Rng.uniform(-.0002, .0002, len(Time))
        Period, Epoch, Duration = 1.4, .31, .08
        Folded = (Time - Epoch + Period / 2) % Period - Period / 2
        Exposures = Np.where(Time < 12, 90, 1800)
        Flux = 1 - .006 * TriangleAverage(Folded, Duration / 2, Exposures / 86400)
        Flux += Rng.normal(0, .00015, len(Time))
        ModelPhase = Np.linspace(-Period / 2, Period / 2, 10001)
        Seed = Duration * 1.25
        ModelFlux = 1 - .006 * TriangleAverage(ModelPhase, Seed / 2, 0)
        Fit = TlsSearch.FitObservedModelDuration(Time, Flux, Period, Epoch, Seed,
            ModelPhase, ModelFlux, ExposureSeconds=Exposures, FluxUncertainty=Np.full(len(Time), .00015))
        self.assertIsNotNone(Fit)
        self.assertAlmostEqual(Fit["duration"], Duration, delta=.004)
        self.assertGreater(Fit["duration_uncertainty"], 0)
        self.assertEqual(Fit["exposure"]["unknown_rows"], 0)
        self.assertLessEqual(Fit["representative_sample_count"], 501 * 32)

    def testShallowInstantaneousFitReportsUnknownExposureLimit(self):
        Rng = Np.random.default_rng(81)
        Time = Np.sort(Rng.uniform(0, 35, 14000))
        Period, Epoch, Duration = 1.6, .27, .09
        Folded = (Time - Epoch + Period / 2) % Period - Period / 2
        Flux = 1 - .0006 * TriangleAverage(Folded, Duration / 2, 0)
        Flux += Rng.normal(0, .00012, len(Time))
        ModelPhase = Np.linspace(-Period / 2, Period / 2, 10001)
        ModelFlux = 1 - .0006 * TriangleAverage(ModelPhase, .11 / 2, 0)
        Fit = TlsSearch.FitObservedModelDuration(Time, Flux, Period, Epoch, .11, ModelPhase, ModelFlux)
        self.assertIsNotNone(Fit)
        self.assertAlmostEqual(Fit["duration"], Duration, delta=.012)
        self.assertEqual(Fit["exposure"]["unknown_rows"], len(Time))
        self.assertIn("unknown exposure", Fit["uncertainty_basis"])

    def testJointAmplitudesUseFiniteExposuresForOverlappingSignals(self):
        Time = Np.linspace(0, 12, 6001)
        Exposures = Np.where(Time < 6, 120, 1800)
        Signals, Shapes = [], []
        ModelPhase = Np.linspace(-1.5, 1.5, 18001)
        for Period, Depth in ((2.0, .01), (3.0, .008)):
            Model = {"folded_phase_days": ModelPhase,
                "folded_flux": 1 - Depth * TriangleAverage(ModelPhase, .04, 0)}
            Phase = (Time - 1.0 + Period / 2) % Period - Period / 2
            Shapes.append(TriangleAverage(Phase, .04, Exposures / 86400))
            Signals.append({"period": Period, "period_epoch": 1.0, "transit_model": Model})
        Flux = 1.001 - .006 * Shapes[0] - .003 * Shapes[1]
        Fit = Analysis.JointTemplateAmplitudes(Time, Flux, Signals,
            Uncertainty=Np.full(len(Time), .0001), ExposureSeconds=Exposures)
        self.assertIsNotNone(Fit)
        self.assertAlmostEqual(Fit["depths"][0], .006, delta=1e-5)
        self.assertAlmostEqual(Fit["depths"][1], .003, delta=1e-5)
        self.assertLess(float(Np.std(Fit["residual_flux"])), 1e-6)


if __name__ == "__main__":
    Unittest.RunApp()
