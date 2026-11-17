"""Short observations can be inspected without inventing a transit search."""
import json as Json
from pathlib import Path
from types import SimpleNamespace
import sys as Sys
import unittest as Unittest
from unittest import mock as Mock

import numpy as Np

Sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"))
import analysis as Analysis


#MARK: short curves
class ShortCurveReviewTests(Unittest.TestCase):
    def testTwoThroughFortyNineSamplesNeverReachSearchOrDipDetection(self):
        for Count in (2, 3, 18, 49):
            for SearchMode in ("tls", "bls"):
                with self.subTest(samples=Count, mode=SearchMode), \
                        Mock.patch.object(Analysis, "DetectTransits", side_effect=AssertionError("search ran")), \
                        Mock.patch.object(Analysis, "ExploratoryLocalDips", side_effect=AssertionError("dip detection ran")), \
                        Mock.patch.object(Analysis, "NormalizeFluxBySegments", side_effect=AssertionError("flux was normalized")):
                    Time = 2459000 + Np.arange(Count) * .001
                    Flux = Np.linspace(-200, 30, Count)
                    Stages = []
                    Result = Analysis.RunCurve(Time, Flux, {"search_mode": SearchMode, "tls_max_signals": 3},
                                               ProgressCallback=lambda Stage, Label: Stages.append(Stage))
                    self.assertTrue(Result["review_only"])
                    self.assertEqual(Result["analysis_mode"], "inspection")
                    self.assertEqual(Result["search_status"], "not_run")
                    self.assertEqual(Result["search_requirements"], {"minimum_samples": 50, "usable_samples": Count})
                    self.assertIn(str(Count), Result["review_reason"])
                    self.assertEqual(Stages, ["preparing", "building", "finalizing"])
                    self.assertEqual(Result["plot"]["raw_flux"], Flux.tolist())
                    self.assertEqual(Result["plot"]["smooth_flux"], Flux.tolist())
                    self.assertEqual(Result["plot_smooth_points"], 1)
                    self.assertEqual(Result["normalization"]["method"], "none")
                    self.assertEqual(Result["time_reference"], Time[0])
                    Np.testing.assert_array_equal(Result["plot"]["time"], Time - Time[0])
                    for Key in ("period", "planet_assessment", "fit_quality", "diagnostics", "transit_model",
                                "phase_folded", "transit_stack", "periodogram", "model_comparison", "p_value"):
                        self.assertIsNone(Result[Key], Key)
                    for Key in ("transits", "signals", "predicted_windows", "observed_events", "exploratory_dips"):
                        self.assertEqual(Result[Key], [], Key)
                    Json.dumps(Result, allow_nan=False)

    def testErrorsExposuresAndMetadataRemainAlignedInOriginalUnits(self):
        Time = Np.r_[2459000 + Np.arange(4) * .001, 2459002 + Np.arange(4) * .001]
        Flux = Np.array([-20, -10, 0, 30, 300, 310, 290, 315], dtype=float)
        Errors = [2, None, 0, 3, float("nan"), -1, 5, float("inf")]
        Exposures = [10, 20, None, 0, 5, 15, float("nan"), 30]
        Metadata = {"source_format": "CSV", "flux_column": "target_counts", "time_format": "jd", "flux_unit": "counts"}
        Cleaning = {"retained_rows": len(Time), "counts_reconcile": True}
        Result = Analysis.RunCurve(Time, Flux, {
            "_flux_uncertainty": Errors, "_exposure_seconds": Exposures,
            "_input_metadata": Metadata, "_cleaning_report": Cleaning,
        })
        self.assertEqual(Result["plot"]["raw_flux"], Flux.tolist())
        self.assertEqual(Result["plot"]["smooth_flux"], Flux.tolist())
        self.assertEqual(Result["plot"]["flux_uncertainty"], [2, None, None, 3, None, None, 5, None])
        self.assertEqual(Result["plot"]["exposure_seconds"], [10, 20, None, 0, 5, 15, None, 30])
        self.assertEqual(Result["plot"]["break_indices"], [4])
        self.assertEqual(Result["flux_unit"], "counts")
        self.assertEqual(Result["input_metadata"], Metadata)
        self.assertEqual(Result["cleaning_report"], Cleaning)
        self.assertEqual(Result["exposure_metadata"]["known_rows"], 6)
        self.assertFalse(Result["exposure_metadata"]["cadence_is_exposure"])
        self.assertEqual(Result["clean_domain"], Result["raw_domain"])
        self.assertLess(Result["raw_domain"]["flux_min"], -22)
        self.assertGreater(Result["raw_domain"]["flux_max"], 315)
        self.assertGreater(Result["domain"]["time_max"], 0)
        self.assertNotIn("_flux_uncertainty", Result["detection_options"])
        self.assertIsNone(Result["effective_settings"]["search_bounds"])
        Json.dumps(Result, allow_nan=False)

    def testDomainIncludesLargeErrorsAndAConstantCurve(self):
        for Flux in ([-10, -10], [100, 100]):
            Result = Analysis.RunCurve([1, 2], Flux, {"_flux_uncertainty": [20, 30]})
            self.assertLess(Result["raw_domain"]["flux_min"], min(Flux) - 30)
            self.assertGreater(Result["raw_domain"]["flux_max"], max(Flux) + 30)
        for Level in (0, 1e12):
            Result = Analysis.RunCurve([1, 2], [Level, Level])
            self.assertLess(Result["raw_domain"]["flux_min"], Level)
            self.assertGreater(Result["raw_domain"]["flux_max"], Level)
            self.assertEqual(Result["plot"]["flux_uncertainty"], [None, None])

    def testExplicitExposureOverrideDoesNotChangeFlux(self):
        Result = Analysis.RunCurve([1, 2, 3], [.5, .9, .7], {
            "_exposure_seconds": [1, 2, 3], "exposure_seconds": 120,
        })
        self.assertEqual(Result["plot"]["exposure_seconds"], [120, 120, 120])
        self.assertEqual(Result["plot"]["raw_flux"], [.5, .9, .7])
        self.assertEqual(Result["exposure_metadata"]["source"], "explicit per-file override")

    def testMissingOrMisalignedErrorsNeverBecomeFabricatedErrorBars(self):
        for Errors in (None, [1], [None, None, None]):
            Result = Analysis.RunCurve([1, 2, 3], [3, 2, 1], {"_flux_uncertainty": Errors})
            self.assertEqual(Result["plot"]["flux_uncertainty"], [None, None, None])

    def testFiftySamplesStillEnterTheExistingPeriodSearch(self):
        class SearchReached(Exception):
            pass

        for SearchMode in ("tls", "bls"):
            with self.subTest(mode=SearchMode), \
                    Mock.patch.object(Analysis, "DetectTransits", side_effect=SearchReached), \
                    Mock.patch.object(Analysis, "_MakeReviewThing", side_effect=AssertionError("review path ran")):
                with self.assertRaises(SearchReached):
                    Analysis.RunCurve(Np.linspace(1, 2, 50), Np.ones(50), {"search_mode": SearchMode})

    def testInvalidMeasurementsStillFailAndDirectTlsGuardStaysInPlace(self):
        for Time, Flux in (([], []), ([1], [1]), ([1, 1], [1, 2]), ([2, 1], [1, 2]),
                           ([1, 2], [1]), ([1, 2], [1, float("nan")])):
            with self.subTest(time=Time, flux=Flux), self.assertRaises(ValueError):
                Analysis.RunCurve(Time, Flux)
        with self.assertRaisesRegex(ValueError, "at least 50"):
            Analysis.EstimatePeriodWithTls(Np.arange(49), Np.ones(49))


#MARK: observation viewer and gaps
class ObservationViewTests(Unittest.TestCase):
    def testViewOnlyOpensFortyEightHoursWithoutSearchingOrNormalizing(self):
        Times = 2459000 + Np.linspace(0, 2, 97)
        Flux = 400 + Np.sin(Np.arange(len(Times)))
        with Mock.patch.object(Analysis, "DetectTransits", side_effect=AssertionError("search ran")), \
                Mock.patch.object(Analysis, "NormalizeFluxBySegments", side_effect=AssertionError("normalized")):
            Result = Analysis.RunCurve(Times, Flux, {"inspection_only": True, "cut_gaps": True})
        self.assertTrue(Result["review_only"])
        self.assertIn("view-only", Result["review_reason"])
        View = Result["observation_view"]
        Np.testing.assert_equal(View["plot"]["raw_flux"], Flux)
        Np.testing.assert_equal(View["plot"]["time"], Times - Times[0])
        Np.testing.assert_equal(View["plot"]["display_time"], View["plot"]["time"])
        self.assertEqual(View["display_time_map"]["gap_count"], 0)
        self.assertEqual(View["domain"]["time_max"], 2)
        self.assertIsNone(Result["period"])

    def testThreeNightsCompressOnlyEmptyIntervalsAndKeepMeasurements(self):
        Times = Np.r_[Np.arange(4), 2880 + Np.arange(4), 7200 + Np.arange(4)] / 1440
        Flux = Np.arange(12, dtype=float) - 3
        Errors = Np.arange(12) / 100 + .01
        Exposures = Np.arange(12, dtype=float)
        Views = []
        for Cut in (False, True):
            Result = Analysis.RunCurve(Times, Flux, {"cut_gaps": Cut, "gap_minutes": 30,
                "_flux_uncertainty": Errors, "_exposure_seconds": Exposures})
            View = Result["observation_view"]
            Views.append(View)
            self.assertEqual(View["display_time_map"]["gap_count"], 2)
            self.assertEqual(View["plot"]["break_indices"], [4, 8])
            Np.testing.assert_equal(View["plot"]["time"], Times)
            Np.testing.assert_equal(View["plot"]["raw_flux"], Flux)
            Np.testing.assert_equal(View["plot"]["flux_uncertainty"], Errors)
            Np.testing.assert_equal(View["plot"]["exposure_seconds"], Exposures)
            self.assertEqual(View["domain"]["time_max"], Times[-1])
            Json.dumps(Result, allow_nan=False)
        Np.testing.assert_equal(Views[0]["plot"]["display_time"], Times)
        Np.testing.assert_allclose(Np.diff(Views[1]["plot"]["display_time"]), 1 / 1440)
        self.assertAlmostEqual(Views[1]["display_time_map"]["removed_days"], Times[-1] - 11 / 1440)

    def testTwoSamplesDoNotInventCadenceAndDenseCurvesKeepRunEdges(self):
        View = Analysis.RunCurve([1, 8], [3, 4], {"cut_gaps": True})["observation_view"]
        self.assertIsNone(View["display_time_map"]["cadence_days"])
        self.assertIn("three", View["display_time_map"]["reason"])
        self.assertEqual(View["plot"]["display_time"], [0, 7])
        Times = Np.r_[Np.arange(15000) / 86400, 3 + Np.arange(15000) / 86400]
        Flux = Np.ones(len(Times))
        Flux[7312] = .5
        View = Analysis.MakeObservationThing(Times, Flux, {"cut_gaps": True}, Np.zeros(len(Times)))
        self.assertLess(len(View["plot"]["time"]), len(Times))
        self.assertEqual(View["total_points"], len(Times))
        for Edge in (Times[0], Times[14999], Times[15000], Times[-1]):
            self.assertIn(Edge, View["plot"]["time"])
        self.assertIn(.5, View["plot"]["raw_flux"])
        self.assertAlmostEqual(View["display_time_map"]["cadence_days"], 1 / 86400)

    def testGapFilterDoesNotChangeScientificResults(self):
        Times = Np.r_[Np.linspace(0, 2, 250), Np.linspace(4, 6, 250)]
        Phase = ((Times - .25 + .5) % 1) - .5
        Flux = 1000 * (1 - .01 * (Np.abs(Phase) < .04))
        Options = {"search_mode": "bls", "min_period": .9, "max_period": 1.1}
        Original = Analysis.RunCurve(Times, Flux, {**Options, "cut_gaps": False})
        Cut = Analysis.RunCurve(Times, Flux, {**Options, "cut_gaps": True})
        for Key in ("period", "period_epoch", "transits", "transit_model", "planet_assessment", "phase_folded", "plot"):
            self.assertEqual(Original.get(Key), Cut.get(Key), Key)
        self.assertNotEqual(Original["observation_view"]["plot"]["display_time"], Cut["observation_view"]["plot"]["display_time"])

    def testUploadGapChoicesRejectInvalidValues(self):
        Options = Analysis.ParseDetectionOptions({Key: SimpleNamespace(value=Value) for Key, Value in {"cutGaps": "true", "gapMinutes": "45", "inspectOnly": "true"}.items()})
        self.assertTrue(Options["cut_gaps"])
        self.assertTrue(Options["inspection_only"])
        self.assertEqual(Options["gap_minutes"], 45)
        for Fields in ({"cutGaps": "maybe"}, {"inspectOnly": "maybe"}, {"gapMinutes": "nan"}, {"gapMinutes": "0"}, {"gapMinutes": "-1"}):
            with self.subTest(fields=Fields), self.assertRaises(ValueError):
                Analysis.ParseDetectionOptions({Key: SimpleNamespace(value=Value) for Key, Value in Fields.items()})


if __name__ == "__main__":
    Unittest.main()
