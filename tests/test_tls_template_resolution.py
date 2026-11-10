"""Gaps must not replace a dense physical template with a few model knots."""
from pathlib import Path
import sys as Sys
from types import SimpleNamespace
import unittest as Unittest
from unittest import mock as Mock

import numpy as Np

APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
Sys.path.insert(0, str(APP_DIR))
Sys.path.insert(0, str(Path(__file__).resolve().parent))

import tls_search as TlsSearch
import validate_updates as ValidateUpdates


#MARK: shape
def Shape(Phase, Duration):
    return Np.clip(1 - (2 * Np.asarray(Phase) / Duration) ** 2, 0, 1)


#MARK: model shape
class DenseTemplateTests(Unittest.TestCase):
    def MockedResult(self, Gap):
        Observed = Np.r_[Np.linspace(0, 1, 1001), Np.linspace(Gap - 1, Gap, 1001)]
        Fill = TlsSearch.SamplingFillFactor(Observed)
        Period, Duration = 1.0, .1
        Centers = Np.arange(.5, Gap, Period)
        CoarsePhase = Np.linspace(-.5, .5, 41)
        ModelTime = Np.concatenate([Center + CoarsePhase for Center in Centers])
        ModelFlux = Np.tile(1 - .01 * Shape(CoarsePhase, Duration), len(Centers))
        Phase = Np.linspace(0, 1, 120001)
        Folded = 1 - .01 * Shape(Phase - .5, Duration * (1 + Fill) / 2)
        return Observed, SimpleNamespace(period=Period, duration=Duration * Fill,
            T0=.5, periods=Np.asarray([.9, 1, 1.1]), power=Np.asarray([1, 9, 1]),
            power_raw=Np.asarray([1, 9, 1]), model_lightcurve_time=ModelTime,
            model_lightcurve_model=ModelFlux, model_folded_phase=Phase,
            model_folded_model=Folded, transit_times=Centers, SDE=9.0, depth=.99)

    def testCoarseUnfoldedCycleDoesNotReplaceDenseFoldedShape(self):
        Observed, EngineResult = self.MockedResult(100)
        Engine = Mock.Mock()
        Engine.power.return_value = EngineResult
        with Mock.patch.object(TlsSearch, "Transitleastsquares", return_value=Engine), \
             Mock.patch.object(TlsSearch, "FitObservedModelDuration", return_value=None) as Fit:
            Result = TlsSearch.RunTlsSearch(Observed, Np.ones(len(Observed)), {"period_min": .8, "period_max": 1.2})
        self.assertEqual(Result["template_source"], "engine folded template")
        self.assertLess(Result["template_resolution"]["engine_unfolded_contact_samples"], 10)
        self.assertGreater(Result["template_resolution"]["retained_contact_samples"], 1000)
        self.assertAlmostEqual(Result["duration"], .1, places=8)
        self.assertGreater(TlsSearch.ModelContactSampleCount(Fit.call_args[0][6]), 1000)
        Phase = Np.asarray(Result["model"]["folded_phase_days"])
        Flux = Np.asarray(Result["model"]["folded_flux"])
        Np.testing.assert_allclose(Flux[Np.isclose(Np.abs(Phase), .05)], 1.0, atol=1e-12)
        HeldOut = Np.linspace(-.2, .2, 1001)
        Np.testing.assert_allclose(Np.interp(HeldOut, Phase, Flux), 1 - .01 * Shape(HeldOut, .1), atol=1e-5)

    def testEmptyEpochsDoNotChangeRetainedObservedShape(self):
        Curves = []
        for Gap in (10, 100):
            Observed, EngineResult = self.MockedResult(Gap)
            Engine = Mock.Mock()
            Engine.power.return_value = EngineResult
            with Mock.patch.object(TlsSearch, "Transitleastsquares", return_value=Engine), \
                 Mock.patch.object(TlsSearch, "FitObservedModelDuration", return_value=None):
                Result = TlsSearch.RunTlsSearch(Observed, Np.ones(len(Observed)), {"period_min": .8, "period_max": 1.2})
            Curves.append(Np.interp(Np.linspace(-.15, .15, 1001),
                Result["model"]["folded_phase_days"], Result["model"]["folded_flux"]))
        Np.testing.assert_allclose(Curves[0], Curves[1], atol=1e-5)

    def testReferenceFallbackCannotSilentlyDropRequestedBounds(self):
        for BestPeriod, Grid in ((1.3, [.9, 1.0, 1.1]), (1.0, [.6, 1.0, 1.3])):
            Observed, EngineResult = self.MockedResult(10)
            EngineResult.period = BestPeriod
            EngineResult.periods = Np.asarray(Grid)
            Engine = Mock.Mock()
            Engine.power.return_value = EngineResult
            with Mock.patch.object(TlsSearch, "Transitleastsquares", return_value=Engine):
                with self.assertRaisesRegex(ValueError, "outside requested bounds.*oversampling"):
                    TlsSearch.RunTlsSearch(Observed, Np.ones(len(Observed)), {"period_min": .8, "period_max": 1.2})

    def testSmallRealGappedTlsFixtureKeepsIndependentDenseShape(self):
        Time = Np.r_[Np.linspace(0, 6, 700), Np.linspace(100, 106, 700)]
        Flux, Truth = ValidateUpdates.Injected(Time, Period=2.4, Epoch=.7)
        Flux += Np.random.default_rng(20261105).normal(0, .0004, len(Time))
        Result = TlsSearch.RunTlsSearch(Time, Flux, {"period_min": 1.4, "period_max": 3.5,
            "tls_oversampling": 1, "tls_threads": 1, "exposure_seconds": 0})
        self.assertAlmostEqual(Result["period"], Truth["period_days"], delta=.02)
        self.assertEqual(Result["template_source"], "engine folded template")
        Resolution = Result["template_resolution"]
        self.assertGreater(Resolution["engine_folded_contact_samples"], Resolution["engine_unfolded_contact_samples"])
        self.assertGreater(Resolution["retained_contact_samples"], 20)
        self.assertAlmostEqual(Result["duration"], Truth["duration_days"], delta=Truth["duration_days"] * .2)


if __name__ == "__main__":
    Unittest.RunApp()
