import json as Json
from pathlib import Path
import sys as Sys
import unittest as Unittest

import numpy as Np

Sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"))
import analysis as Analysis
import tls_search as TlsSearch


#MARK: transit checks
class EventEvidenceTests(Unittest.TestCase):
    def testSearchEdgeWarningUsesLocalPeriodScale(self):
        for Period, Lower, Upper, Sigma, Expected in [
            (.81347, .5, 245, .000026, False),
            (1.3382, .5, 253, .000074, False),
            (.50001, .5, 245, .000001, True),
            (244.99, .5, 245, .000001, True),
            (2.18, 1, 2.2, .01, True),
        ]:
            with self.subTest(period=Period, bounds=(Lower, Upper)):
                _, Warnings = Analysis.BuildCandidateDiagnostics([], {
                    "period": Period, "period_method": "TLS", "period_uncertainty": Sigma,
                    "period_search": {"min_period": Lower, "max_period": Upper},
                })
                self.assertEqual(any(W["title"] == "Period peak near search edge" for W in Warnings), Expected)

    def windows(self, Time, Flux, Centers=(1.0, 3.0, 5.0), Duration=0.2):
        return Analysis.TransitsFromTlsResult(Time, Flux, {
            "period": 2.0, "duration": Duration, "transit_time": 1.0,
            "tls_result": {"transit_times": Centers, "per_transit_count": [0, 0, 0],
                           "transit_depth_fractions": [0.02, 0.02, 0.02]},
        })

    def testFlatEphemerisWindowsDoNotBecomeObservedEvents(self):
        Time = Np.linspace(0, 6, 3001)
        windows = self.windows(Time, Np.ones(len(Time)))
        self.assertEqual(len(windows), 3)
        self.assertTrue(all(W["state"] == "unsupported_window" for W in windows))
        self.assertTrue(all(W["depth"] == 0 and W["measured_center"] is None for W in windows))
        Detection = {"period": 2, "period_epoch": 1, "period_method": "TLS", "period_duration": .2,
                     "period_sde": 9, "tls_snr": 20, "tls_fap": None, "tls": {}}
        Diagnostics, Warnings = Analysis.BuildCandidateDiagnostics(windows, Detection)
        Assessment = Analysis.BuildPlanetAssessment(windows, Detection, Diagnostics, Warnings)
        self.assertEqual(Diagnostics["supported_event_count"], 0)
        self.assertIsNone(Diagnostics["ephemeris_match_fraction"])
        self.assertNotEqual(Assessment["status"], "strong_candidate")
        self.assertFalse(any("ephemeris" in Item["title"].lower() for Item in Assessment["supporting_evidence"]))
        self.assertFalse(any("false-alarm" in Item["title"].lower() for Item in Assessment["supporting_evidence"]))

    def testFinalWindowCountsAndNegativeDepthAreMeasured(self):
        Time = Np.linspace(0, 6, 3001)
        Flux = Np.ones(len(Time))
        Flux[Np.abs(Time - 1) <= .1] += .01
        windows = self.windows(Time, Flux)
        First = windows[0]
        self.assertGreaterEqual(First["points"], 99)
        self.assertLess(First["signed_depth"], 0)
        self.assertEqual(First["state"], "unsupported_window")

    def testLocalCentroidIsNotCopiedFromEphemeris(self):
        Time = Np.linspace(0, 6, 6001)
        Flux = 1 + Np.random.default_rng(201).normal(0, .0002, len(Time))
        for Center in (1.025, 3.025, 5.025):
            Flux -= .01 * Np.clip(1 - Np.abs(Time - Center) / .055, 0, 1)
        windows = self.windows(Time, Flux)
        self.assertTrue(all(W["state"] == "supported_dip" for W in windows))
        for Window in windows:
            self.assertAlmostEqual(Window["measured_center"] - Window["center"], .025, delta=.008)
            self.assertGreater(Window["timing_uncertainty"], 0)

    def testCycleParitySurvivesAMissingCycle(self):
        windows = [{"center": C, "cycle_number": N, "depth": D, "points": 30,
                    "duration": .1, "state": "supported_dip"}
                   for C, N, D in [(1, 0, .01), (3, 1, .02), (7, 3, .02), (9, 4, .01)]]
        Diagnostics, _ = Analysis.BuildCandidateDiagnostics(windows, {"period": 2, "period_epoch": 1})
        self.assertEqual(Diagnostics["odd_depth"], .02)
        self.assertEqual(Diagnostics["even_depth"], .01)

    def testGapSeparatesTrendsAndLocalBaselines(self):
        Time = Np.r_[Np.linspace(0, 2, 300), Np.linspace(10, 12, 300)]
        Flux = Np.r_[Np.ones(300), Np.ones(300) * 1.05]
        Flattened = Analysis.FlattenedFluxForPeriodSearch(Time, Flux)
        self.assertLess(Np.max(Np.abs(Flattened)), 1e-12)
        windows = self.windows(Time, Flux, Centers=(1.95, 6.0, 10.05))
        self.assertEqual(windows[1]["state"], "outside_observations")
        self.assertAlmostEqual(windows[0]["local_baseline"], 1.0)
        self.assertAlmostEqual(windows[2]["local_baseline"], 1.05)

    def testPhaseBinsIncludeCountsAndUncertainties(self):
        Time = Np.linspace(0, 6, 1201)
        Flux = 1 + Np.random.default_rng(8).normal(0, .001, len(Time))
        Plot = Analysis.MakePhasePlot(Time, Flux, Flux, 2.0, 1.0, .1)
        self.assertEqual(sum(Plot["binned_count"]), len(Time))
        self.assertEqual(len(Plot["binned_uncertainty"]), len(Plot["binned_flux"]))
        Json.dumps(Plot, allow_nan=False)

    def testTwoTransitOptionChangesAutomaticSearchBounds(self):
        _, Maximum = Analysis.PeriodSearchBounds(.001, 24, {"tls_min_transits": 2})
        self.assertEqual(Maximum, 12)

    def testExploratoryLocalFeaturesKeepUnassignedDipsWithoutScoringThem(self):
        Time = Np.r_[Np.linspace(0, 2, 1001), Np.linspace(10, 12, 1001)]
        Flux = 1 + Np.random.default_rng(18).normal(0, .0001, len(Time))
        for Center in (.8, 10.8):
            Flux -= .02 * Np.clip(1 - Np.abs(Time - Center) / .05, 0, 1)
        Dips, Metadata = Analysis.ExploratoryLocalDips(Time, Flux, Analysis.DEFAULT_DETECTION_OPTIONS, 0.0)
        self.assertGreaterEqual(len(Dips), 2)
        Result = {"time_reference": 0.0, "exploratory_dips": Dips,
                  "planet_assessment": {"candidate_score": 12},
                  "predicted_windows": [{"start": .7, "end": .9}]}
        Analysis.TagExploratoryAssignments(Result, [Result])
        self.assertTrue(any(Dip["assignment"] == "unassigned" for Dip in Dips))
        self.assertTrue(any(Dip["assignment"] == "overlaps_predicted_window" for Dip in Dips))
        self.assertTrue(all(Dip["validated"] is False for Dip in Dips))
        self.assertEqual(Result["planet_assessment"]["candidate_score"], 12)
        self.assertIn("never", Metadata["interpretation"])


#MARK: model shape
class ConditionalDurationTests(Unittest.TestCase):
    def testJointAmplitudesRecoverOverlappingSeededTemplates(self):
        Time = Np.linspace(0, 12, 6001)
        Phase = Np.linspace(-1.5, 1.5, 3001)
        Shape = Np.clip(1 - Np.abs(Phase) / .08, 0, 1)
        Signals = []
        EvaluatedShapes = []
        for Index, (Period, PriorDepth) in enumerate([(2.0, .015), (3.0, .010)]):
            Signal = {"signal_id": f"signal-{Index + 1}", "label": f"Signal {Index + 1}",
                      "period": Period, "period_epoch": 1.0,
                      "transit_model": {"folded_phase_days": Phase.tolist(), "folded_flux": (1 - PriorDepth * Shape).tolist()}}
            Aligned = Analysis.ModelFluxAtObservations(Time, Period, 1.0, Signal["transit_model"])
            EvaluatedShapes.append((1 - Aligned) / PriorDepth)
            Signals.append(Signal)
        Flux = 1.001 - .006 * EvaluatedShapes[0] - .003 * EvaluatedShapes[1]
        Flux += Np.random.default_rng(20261105).normal(0, .0002, len(Time))
        Joint = Analysis.JointTemplateAmplitudes(Time, Flux, Signals)
        self.assertIsNotNone(Joint)
        self.assertGreater(Joint["metadata"]["overlapping_sample_count"], 0)
        self.assertAlmostEqual(Joint["baseline"], 1.001, delta=.00005)
        self.assertAlmostEqual(Joint["depths"][0], .006, delta=.00010)
        self.assertAlmostEqual(Joint["depths"][1], .003, delta=.00010)
        self.assertLess(float(Np.std(Joint["residual_flux"])), .00022)
        Analysis.UpdateSignalJointDepth(Signals[0], Joint["depths"][0], Joint["depth_uncertainties"][0])
        self.assertAlmostEqual(1 - min(Signals[0]["transit_model"]["folded_flux"]), Joint["depths"][0])
        self.assertEqual(Signals[0]["period"], 2.0)

    def testCollectiveShallowTlsSignalDoesNotRequireThreeIndividualDetections(self):
        import validate_updates as ValidateUpdates
        _, Time, Flux, _, _ = next(Case for Case in ValidateUpdates.Fixtures() if Case[0] == "shallow_600ppm")
        Options = {**Analysis.DEFAULT_DETECTION_OPTIONS, "min_period": 1.4, "max_period": 3.5,
                   "tls_oversampling": 2, "tls_threads": 1}
        Options["_flux_uncertainty"] = [.0008] * len(Time)
        Options["_flux_uncertainty"][0] = None
        Result = Analysis.RunCurve(Time + 2459000, Flux, Options)
        self.assertIn(Result["planet_assessment"]["status"], ("possible_candidate", "strong_candidate"))
        self.assertLess(len(Result["observed_events"]), 3)
        self.assertTrue(Result["diagnostics"]["combined_signal_supported"])
        self.assertAlmostEqual(Result["period"], 2.4, delta=.025)
        self.assertTrue(any("combined" in Evidence["title"].lower() for Evidence in Result["planet_assessment"]["supporting_evidence"]))
        self.assertIsNone(Result["plot"]["flux_uncertainty"][0])
        self.assertIn("unweighted fallback", Result["uncertainty_usage"])
        self.assertNotIn("_flux_uncertainty", Result["detection_options"])
        Json.dumps(Result, allow_nan=False)

    def testTemplateDurationCanShortenAndEstimatesUncertainty(self):
        Time = Np.linspace(0, 8, 8001)
        Period, Epoch, Truth = 1.0, .5, .1
        Phase = ((Time - Epoch + Period/2) % Period) - Period/2
        Flux = 1 - .01 * Np.clip(1 - Np.abs(Phase) / (Truth / 2), 0, 1)
        Flux += Np.random.default_rng(9).normal(0, .0002, len(Time))
        ModelPhase = Np.linspace(-.5, .5, 3001)
        Model = 1 - .01 * Np.clip(1 - Np.abs(ModelPhase) / .065, 0, 1)
        Result = TlsSearch.FitObservedModelDuration(Time, Flux, Period, Epoch, .13, ModelPhase, Model)
        self.assertIsNotNone(Result)
        self.assertAlmostEqual(Result["duration"], Truth, delta=.012)
        self.assertLess(Result["duration"], .13)
        self.assertGreater(Result["duration_uncertainty"], 0)


if __name__ == "__main__":
    Unittest.RunApp()
