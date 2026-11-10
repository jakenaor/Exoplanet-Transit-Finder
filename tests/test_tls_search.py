import json as Json
from pathlib import Path
import sys as Sys
from types import SimpleNamespace
import unittest as Unittest
from unittest import mock as Mock

import numpy as Np


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
Sys.path.insert(0, str(APP_DIR))

import analysis as Analysis  # noqa: E402
import tls_search as TlsSearch  # noqa: E402


#MARK: form item
class FormItem:
    def __init__(self, Value):
        self.value = Value


#MARK: tls funcs
def TlsOptions(**Overrides):
    Options = dict(Analysis.DEFAULT_DETECTION_OPTIONS)
    Options.update({
        "search_mode": "tls",
        "min_period": 1.5,
        "max_period": 3.5,
        "tls_oversampling": 2,
        "tls_threads": 1,
    })
    Options.update(Overrides)
    return Options


#MARK: synthetic light curve
def SyntheticLightCurve(Seed=4, Depth=0.006):
    Time = Np.linspace(2459000.0, 2459012.0, 1200)
    Period = 2.4
    Epoch = 2459000.7
    Duration = 0.14
    Phase = ((Time - Epoch + Period / 2.0) % Period) - Period / 2.0
    TriangularCore = Np.clip(1.0 - Np.abs(Phase) / (Duration / 2.0), 0.0, 1.0)
    TransitShape = (0.25 + 0.75 * TriangularCore) * (Np.abs(Phase) < Duration / 2.0)
    Flux = 1.0 - Depth * TransitShape
    Flux += Np.random.default_rng(Seed).normal(0.0, 0.0008, len(Time))
    return Time, Flux, Period


#MARK: tls funcs
class TLSOptionTests(Unittest.TestCase):
    def testTlsAndFourWorkersAreDefaults(self):
        Options = Analysis.ParseDetectionOptions({})

        self.assertEqual(Options["search_mode"], "tls")
        self.assertEqual(Options["tls_threads"], 4)

        IndexHtml = (APP_DIR / "static" / "index.html").read_text()
        self.assertIn('<option value="tls" selected>Physical TLS</option>', IndexHtml)
        self.assertIn('id="TlsThreadsInput" type="number" min="1" max="8" step="1" value="4"', IndexHtml)

    def testParsesPhysicalTlsOptions(self):
        Options = Analysis.ParseDetectionOptions({
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
        self.assertEqual(Options["search_mode"], "tls")
        self.assertEqual(Options["tls_template"], "grazing")
        self.assertEqual(Options["tls_oversampling"], 4)
        self.assertEqual(Options["tls_min_transits"], 2)
        self.assertAlmostEqual(Options["stellar_radius"], 0.82)
        self.assertAlmostEqual(Options["limb_darkening_u2"], 0.18)

    def testRequiresBothLimbDarkeningCoefficients(self):
        with self.assertRaisesRegex(ValueError, "Both limbDarkening"):
            Analysis.ParseDetectionOptions({
                "searchMode": FormItem("tls"),
                "limbDarkeningU1": FormItem("0.4"),
            })

    def testTransitStackViewReplacesManualBoxEditor(self):
        IndexHtml = (APP_DIR / "static" / "index.html").read_text()
        AppJs = (APP_DIR / "static" / "app.js").read_text()

        self.assertIn('data-view="stack">Transit stack</button>', IndexHtml)
        self.assertIn("function DrawTransitStackChart(Geo)", AppJs)
        self.assertNotIn("Edit boxes", IndexHtml)
        self.assertNotIn("editBoxesButton", AppJs)


#MARK: tls funcs
class TLSSearchTests(Unittest.TestCase):
    def testTransitStackAlignsAndNormalizesIndividualEvents(self):
        Time = Np.linspace(0.0, 8.0, 4001)
        Period = 2.0
        Duration = 0.16
        Centers = [1.0, 3.0, 5.0, 7.0]
        Flux = 1.0 + 0.0004 * (Time - 4.0)
        for Center in Centers:
            Phase = Np.abs(Time - Center)
            Shape = Np.clip(1.0 - Phase / (Duration / 2.0), 0.0, 1.0)
            Flux -= 0.012 * Shape
        Transits = [
            {
                "center": Center,
                "start": Center - Duration / 2.0,
                "end": Center + Duration / 2.0,
                "duration": Duration,
            }
            for Center in Centers
        ]

        Stack = Analysis.BuildTransitStack(Time, Flux, Transits, Period, Duration)

        self.assertIsNotNone(Stack)
        self.assertEqual(len(Stack["traces"]), len(Centers))
        self.assertTrue(all(Trace["point_count"] > 100 for Trace in Stack["traces"]))
        self.assertTrue(all(
            min(Trace["phase_days"]) < 0 < max(Trace["phase_days"])
            for Trace in Stack["traces"]
        ))
        MedianPhase = Np.asarray(Stack["median_phase_days"])
        MedianFlux = Np.asarray(Stack["median_flux"])
        self.assertLess(float(Np.min(MedianFlux[Np.abs(MedianPhase) < 0.02])), 0.99)
        Shoulder = MedianFlux[Np.abs(MedianPhase) > Duration]
        self.assertAlmostEqual(float(Np.median(Shoulder)), 1.0, delta=0.001)
        self.assertGreater(Stack["window_half_width"], Duration)
        Json.dumps(Stack)

    def testZeroCenteredPpmFluxIsConvertedBeforeSegmentNormalization(self):
        TimeValues = Np.linspace(0.0, 20.0, 2001)
        ResidualPpm = Np.random.default_rng(14).normal(3.0, 110.0, len(TimeValues))
        ResidualPpm[995:1006] -= 450.0

        Normalized, Segments = Analysis.NormalizeFluxBySegments(
            TimeValues,
            ResidualPpm,
        )
        Plan = Analysis.FluxNormalizationPlan(ResidualPpm)
        TlsFlux, _ = Analysis.NormalizedFluxForTls(TimeValues, ResidualPpm)

        self.assertEqual(Segments, [(0, len(TimeValues))])
        self.assertEqual(Plan["input_representation"], "zero-centered residual flux (ppm)")
        self.assertEqual(Plan["residual_scale"], 1000000.0)
        self.assertAlmostEqual(float(Np.median(Normalized)), 1.0, delta=1e-12)
        self.assertGreater(float(Np.min(Normalized)), 0.999)
        self.assertLess(float(Np.max(Normalized)), 1.001)
        self.assertAlmostEqual(float(Np.median(TlsFlux)), 1.0, delta=1e-12)
        self.assertGreater(float(Np.min(TlsFlux)), 0.999)
        self.assertLess(float(Np.max(TlsFlux)), 1.001)

    def testAbsoluteRelativeFluxKeepsFractionalTransitDepth(self):
        TimeValues = Np.linspace(0.0, 10.0, 1001)
        RelativeFlux = Np.ones_like(TimeValues)
        RelativeFlux[495:506] = 0.99

        Normalized, _ = Analysis.NormalizeFluxBySegments(
            TimeValues,
            RelativeFlux,
        )
        Plan = Analysis.FluxNormalizationPlan(RelativeFlux)

        self.assertEqual(Plan["input_representation"], "absolute or relative flux")
        self.assertIsNone(Plan["residual_scale"])
        self.assertAlmostEqual(float(Np.median(Normalized)), 1.0)
        self.assertAlmostEqual(float(Np.min(Normalized)), 0.99)

    def testRecoversTransitWithReferenceTls(self):
        Time, Flux, InjectedPeriod = SyntheticLightCurve()
        Result = Analysis.RunCurve(Time, Flux, TlsOptions())

        self.assertEqual(Result["period_method"], "TLS")
        self.assertAlmostEqual(Result["period"], InjectedPeriod, delta=0.02)
        self.assertGreaterEqual(Result["period_sde"], 7.0)
        self.assertLessEqual(Result["tls_fap"], 0.01)
        self.assertGreaterEqual(len(Result["transits"]), 4)
        self.assertTrue(all(Item.get("source") == "TLS model" for Item in Result["transits"]))
        self.assertGreater(len(Result["transit_model"]["folded_phase_days"]), 100)
        self.assertEqual(Result["planet_assessment"]["status"], "strong_candidate")
        Json.dumps(Result)

    def testNoiseDoesNotBecomeCandidate(self):
        Time = Np.linspace(2459000.0, 2459012.0, 1200)
        Flux = 1.0 + Np.random.default_rng(41).normal(0.0, 0.0008, len(Time))
        Result = Analysis.RunCurve(Time, Flux, TlsOptions())

        self.assertLess(Result["period_sde"], 5.0)
        self.assertEqual(Result["planet_assessment"]["status"], "no_planet_like_signal")
        self.assertLessEqual(Result["planet_assessment"]["candidate_score"], 44)

    def testBlsRuntimeFailureUsesBinnedFallback(self):
        class BrokenBLS:
            def __init__(self, *Args, **Kwargs):
                pass

            def power(self, *Args, **Kwargs):
                raise RuntimeError("forced BLS failure")

        Sentinel = {"method": "binned BLS fallback", "period": 2.0}
        Time = Np.linspace(0.0, 10.0, 100)
        Flux = Np.ones_like(Time)
        with Mock.patch.object(Analysis, "BoxLeastSquares", BrokenBLS), Mock.patch.object(
            Analysis,
            "EstimatePeriodWithBinnedBls",
            return_value=Sentinel,
        ) as Fallback:
            Result = Analysis.EstimatePeriodWithBls(Time, Flux)

        self.assertIs(Result, Sentinel)
        Fallback.assert_called_once()

    def testModelCompactionPreservesNarrowTransitBottoms(self):
        TimeValues = Np.arange(200000, dtype=float)
        FluxValues = Np.ones_like(TimeValues)
        TransitIndices = Np.arange(1000, 199000, 5000)
        FluxValues[TransitIndices] = 0.975

        CompactTime, CompactFlux = TlsSearch.CompactModel(
            TimeValues,
            FluxValues,
            MaxPoints=2000,
        )

        KeptTimes = set(Np.asarray(CompactTime, dtype=int).tolist())
        self.assertTrue(set(TransitIndices.tolist()).issubset(KeptTimes))
        self.assertEqual(min(CompactFlux), 0.975)
        self.assertLessEqual(len(CompactTime), 2000)

    def testDurationIsMeasuredFromFoldedPhysicalModel(self):
        Phase = Np.linspace(-0.5, 0.5, 10001)
        Flux = Np.ones_like(Phase)
        Flux[Np.abs(Phase) <= 0.02] = 0.98

        Duration = TlsSearch.DurationFromFoldedModel(Phase, Flux, Period=1.0)

        self.assertAlmostEqual(Duration, 0.04, delta=0.0003)

    def testUnfoldedTlsModelRestoresGapCompressedDuration(self):
        Period = 1.0
        Centers = Np.arange(0.5, 4.0, Period)
        ModelTime = Np.concatenate([
            Np.linspace(Center - Period / 2.0, Center + Period / 2.0, 1001)
            for Center in Centers
        ])
        ModelFlux = Np.concatenate([
            Np.where(
                Np.abs(Np.linspace(-Period / 2.0, Period / 2.0, 1001)) <= 0.05,
                0.98,
                1.0,
            )
            for _ in Centers
        ])
        FoldedPhase = Np.linspace(0.0, 1.0, 1001)
        CompressedFoldedFlux = Np.where(Np.abs(FoldedPhase - 0.5) <= 0.025, 0.98, 1.0)
        FakeResult = SimpleNamespace(
            period=Period,
            duration=0.05,
            T0=Centers[0],
            periods=Np.asarray([0.9, Period, 1.1]),
            power=Np.asarray([1.0, 9.0, 1.0]),
            power_raw=Np.asarray([1.0, 9.0, 1.0]),
            model_lightcurve_time=ModelTime,
            model_lightcurve_model=ModelFlux,
            model_folded_phase=FoldedPhase,
            model_folded_model=CompressedFoldedFlux,
            transit_times=Centers,
            transit_depths=Np.full(len(Centers), 0.98),
            per_transit_count=Np.full(len(Centers), 100),
            transit_count=len(Centers),
            distinct_transit_count=len(Centers),
            empty_transit_count=0,
            depth=0.98,
            SDE=9.0,
            SDE_raw=9.0,
            FAP=0.001,
            snr=20.0,
        )
        FakeModel = Mock.Mock()
        FakeModel.power.return_value = FakeResult
        ObservedTime = Np.r_[
            Np.linspace(0.0, 1.0, 1001),
            Np.linspace(3.0, 4.0, 1001),
        ]

        with Mock.patch.object(TlsSearch, "Transitleastsquares", return_value=FakeModel):
            Result = TlsSearch.RunTlsSearch(
                ObservedTime,
                Np.ones_like(ObservedTime),
                {
                    "period_min": 0.8,
                    "period_max": 1.2,
                    "tls_threads": 1,
                },
            )

        self.assertAlmostEqual(Result["folded_engine_duration"], 0.05, delta=0.002)
        self.assertAlmostEqual(Result["duration"], 0.10, delta=0.002)
        self.assertAlmostEqual(Result["unfolded_model_duration"], 0.10, delta=0.002)
        self.assertAlmostEqual(Result["sampling_fill_factor"], 0.5, delta=0.002)
        self.assertAlmostEqual(Result["uncompressed_duration"], 0.10, delta=0.002)
        self.assertEqual(
            Result["duration_source"],
            "TLS duration with sampling-gap compression removed",
        )
        FoldedPhase = Np.asarray(Result["model"]["folded_phase_days"])
        FoldedFlux = Np.asarray(Result["model"]["folded_flux"])
        ContactIndices = Np.flatnonzero(
            Np.isclose(Np.abs(FoldedPhase), Result["duration"] / 2.0)
        )
        self.assertEqual(ContactIndices.size, 2)
        self.assertTrue(Np.allclose(FoldedFlux[ContactIndices], 1.0))

    def testObservedDurationRefinementCoversIngressAndEgress(self):
        TimeValues = Np.linspace(0.0, 8.0, 8001)
        Period = 1.0
        Epoch = 0.5
        Phase = ((TimeValues - Epoch + Period / 2.0) % Period) - Period / 2.0
        FluxValues = Np.ones_like(TimeValues)
        FluxValues[Np.abs(Phase) <= 0.05] = 0.98
        FluxValues += Np.random.default_rng(91).normal(0.0, 0.0001, len(FluxValues))

        Refinement = TlsSearch.ObservedPhaseFoldedDuration(
            TimeValues,
            FluxValues,
            Period,
            Epoch,
            SeedDuration=0.06,
        )

        self.assertIsNotNone(Refinement)
        self.assertLessEqual(Refinement["measured_start"], -0.049)
        self.assertGreaterEqual(Refinement["measured_end"], 0.049)
        self.assertGreaterEqual(Refinement["duration"], 0.10)
        self.assertLess(Refinement["duration"], 0.13)

    def testRescaledFoldedModelIsCenteredInsideDurationBox(self):
        Phase = Np.linspace(-0.5, 0.5, 1001)
        ShiftedModel = Np.where(
            (Phase >= -0.07) & (Phase <= 0.03),
            0.98,
            1.0,
        )

        ScaledPhase, ScaledFlux = TlsSearch.RescaleFoldedModelDuration(
            Phase,
            ShiftedModel,
            TargetDuration=0.06,
            Period=1.0,
        )
        Support = ScaledPhase[ScaledFlux < 0.999]
        LeftContact = int(Np.argmin(Np.abs(ScaledPhase + 0.03)))
        RightContact = int(Np.argmin(Np.abs(ScaledPhase - 0.03)))

        self.assertAlmostEqual(float(ScaledPhase[LeftContact]), -0.03, delta=1e-9)
        self.assertAlmostEqual(float(ScaledPhase[RightContact]), 0.03, delta=1e-9)
        self.assertAlmostEqual(float(ScaledFlux[LeftContact]), 1.0)
        self.assertAlmostEqual(float(ScaledFlux[RightContact]), 1.0)
        self.assertGreater(float(Np.min(Support)), -0.03)
        self.assertLess(float(Np.max(Support)), 0.03)

    def testObservationAlignedModelKeepsEveryVisibleTransit(self):
        TimeValues = Np.linspace(0.0, 10.0, 10001)
        Period = 1.0
        Epoch = 0.2
        FoldedPhase = Np.linspace(-0.5, 0.5, 2001)
        TransitShape = Np.clip(1.0 - Np.abs(FoldedPhase) / 0.025, 0.0, 1.0)
        FoldedFlux = 1.0 - 0.02 * TransitShape
        Model = {
            "folded_phase_days": FoldedPhase.tolist(),
            "folded_flux": FoldedFlux.tolist(),
        }

        Aligned = Analysis.ModelFluxAtObservations(
            TimeValues,
            Period,
            Epoch,
            Model,
        )
        Smoothed = Analysis.MovingAverageBySegments(
            Aligned,
            21,
            [(0, len(TimeValues))],
        )
        Keep = Analysis.DownsampleIndicesForSeries(
            [Np.ones_like(Smoothed), Smoothed],
            MaxPoints=400,
        )
        CompactTime = TimeValues[Keep]
        CompactFlux = Smoothed[Keep]

        for Center in Np.arange(Epoch, TimeValues[-1], Period):
            Nearby = Np.abs(CompactTime - Center) <= 0.03
            self.assertTrue(Np.any(Nearby), f"missing model samples near {Center}")
            self.assertLess(float(Np.min(CompactFlux[Nearby])), 0.99)

    def testPlotSmoothingCannotAverageOverWholeTransit(self):
        Cadence = 2.0 / (24.0 * 60.0)
        Duration = 0.0232

        Width = Analysis.TransitPreservingSmoothingWidth(
            RequestedWidth=95,
            Cadence=Cadence,
            Duration=Duration,
        )

        self.assertEqual(Width, 5)
        self.assertLess(Width * Cadence, Duration / 2.0)

    def testSmoothedTlsBoxBoundsCoverFilterRadius(self):
        DisplayStart, DisplayEnd = Analysis.SmoothedTransitDisplayBounds(
            Start=1.0,
            End=1.1,
            Cadence=0.01,
            SmoothWidth=5,
            DomainMin=0.0,
            DomainMax=2.0,
        )

        self.assertAlmostEqual(DisplayStart, 0.98)
        self.assertAlmostEqual(DisplayEnd, 1.12)

    def testPhaseFoldedBinsPreserveIndividualTransitShape(self):
        Cadence = 10.0 / (24.0 * 60.0)
        TimeValues = Np.arange(0.0, 60.0, Cadence)
        Period = 3.5
        Epoch = 1.2
        Duration = 0.15
        Phase = ((TimeValues - Epoch + Period / 2.0) % Period) - Period / 2.0
        AbsolutePhase = Np.abs(Phase)
        TransitProfile = Np.zeros_like(Phase)
        TransitProfile[AbsolutePhase <= 0.045] = 1.0
        Ingress = (AbsolutePhase > 0.045) & (AbsolutePhase < Duration / 2.0)
        TransitProfile[Ingress] = (
            Duration / 2.0 - AbsolutePhase[Ingress]
        ) / (Duration / 2.0 - 0.045)
        FluxValues = 1.0 - 0.016 * TransitProfile

        Folded = Analysis.MakePhasePlot(
            TimeValues,
            FluxValues,
            FluxValues,
            Period,
            Epoch,
            Duration,
        )
        BinnedPhase = Np.asarray(Folded["binned_phase"])
        BinnedFlux = Np.asarray(Folded["binned_flux"])
        InTransitBins = Np.abs(BinnedPhase) <= Duration / 2.0
        OutsideTransit = (Np.abs(BinnedPhase) >= 0.11) & (Np.abs(BinnedPhase) <= 0.18)

        self.assertGreaterEqual(Np.count_nonzero(InTransitBins), 16)
        self.assertLess(float(Np.min(BinnedFlux[InTransitBins])), 0.985)
        self.assertGreater(float(Np.min(BinnedFlux[OutsideTransit])), 0.999)

    def testSegmentSmoothingDoesNotBridgeObservationGaps(self):
        Values = Np.r_[Np.zeros(20), Np.ones(20)]
        Smoothed = Analysis.MovingAverageBySegments(
            Values,
            9,
            [(0, 20), (20, 40)],
        )

        self.assertTrue(Np.allclose(Smoothed[:20], 0.0))
        self.assertTrue(Np.allclose(Smoothed[20:], 1.0))


if __name__ == "__main__":
    Unittest.RunApp()
