"""Seeded end-to-end scientific checks; emits measurements rather than a score.

Run with the repo interpreter. --app-dir permits comparison with a preserved
checkout. This deliberately uses the installed reference TLS engine.
"""
import argparse as Argparse
import contextlib as Contextlib
import hashlib as Hashlib
import io as Io
import json as Json
import math as Math
from pathlib import Path
import resource as Resource
import sys as Sys
import time as Time

import batman as Batman
import numpy as Np


#MARK: injected
def Injected(TimeValues, Period=2.4, Epoch=0.7, RadiusRatio=0.09, A=7.5):
    Params = Batman.TransitParams()
    Params.t0 = Epoch
    Params.per = Period
    Params.rp = RadiusRatio
    Params.a = A
    Params.inc = 89.2
    Params.ecc = 0.0
    Params.w = 90.0
    Params.u = [0.4804, 0.1867]
    Params.limb_dark = 'quadratic'
    Flux = Batman.TransitModel(Params, TimeValues).light_curve(Params)
    B = A * Math.cos(Math.radians(Params.inc))
    Duration = Period / Math.pi * Math.asin(
        Math.sqrt((1 + RadiusRatio) ** 2 - B ** 2) /
        (A * Math.sin(Math.radians(Params.inc)))
    )
    return Flux, {'period_days': Period, 'duration_days': Duration,
                  'radius_ratio': RadiusRatio, 'epoch_days': Epoch}


#MARK: fixtures
def Fixtures():
    Base = Np.linspace(0, 12, 1200)
    Rng = Np.random.default_rng(20261105)
    Irregular = Np.sort(Rng.uniform(0, 12, 1200))
    Gapped = Np.r_[Np.linspace(0, 6, 600), Np.linspace(24, 30, 600)]
    Mixed = Np.r_[Np.arange(0, 6, 0.006), Np.arange(6, 12, 0.025)]
    for Name, T in [('continuous', Base), ('irregular', Irregular),
                    ('gapped', Gapped), ('mixed_cadence', Mixed)]:
        Clean, Truth = Injected(T)
        Flux = Clean + Rng.normal(0, 0.0008, len(T))
        if Name == 'gapped':
            Flux[T > 20] *= 1.08
        yield Name, T, Flux, [Truth], 1
    Clean, Truth = Injected(Base, RadiusRatio=Math.sqrt(0.0006))
    yield 'shallow_600ppm', Base, Clean + Rng.normal(0, 0.0008, len(Base)), [Truth], 1
    yield 'white_noise', Base, 1 + Rng.normal(0, 0.0008, len(Base)), [], 1
    T = Np.linspace(0, 16, 1800)
    F1, Truth1 = Injected(T, Period=1.7, Epoch=0.4, RadiusRatio=0.095, A=6.8)
    F2, Truth2 = Injected(T, Period=2.8, Epoch=1.0, RadiusRatio=0.075, A=8.7)
    yield 'two_planets', T, F1 * F2 + Rng.normal(0, 0.0005, len(T)), [Truth1, Truth2], 2


#MARK: main
def RunApp():
    Parser = Argparse.ArgumentParser(description=__doc__)
    Parser.add_argument('--app-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'Exoplanet data parsing tool', dest='AppDir')
    Parser.add_argument('--output', type=Path, required=True, dest='Output')
    Parser.add_argument('--only', action='append', help='Run just this named fixture (repeatable).', dest='Only')
    Parser.add_argument('--save-results-dir', type=Path, help='Save full current results for browser inspection.', dest='SaveResultsDir')
    Args = Parser.parse_args()
    Sys.path.insert(0, str(Args.AppDir.resolve()))
    import analysis as Analysis
    Results = []
    Started = Time.perf_counter()
    for Name, T, F, Truths, MaxSignals in Fixtures():
        if Args.Only and Name not in Args.Only:
            continue
        Options = dict(Analysis.DEFAULT_DETECTION_OPTIONS)
        Options.update(search_mode='tls', min_period=1.4, max_period=3.5,
                       tls_oversampling=2, tls_threads=1, tls_max_signals=MaxSignals,
                       max_signals=MaxSignals)
        Begin = Time.perf_counter()
        Messages = []
        def Progress(Stage, Label, Details=None):
            if Details:
                Messages.append(dict(stage=Stage, **Details))
        with Contextlib.redirect_stdout(Io.StringIO()):
            Result = Analysis.RunCurve(T + 2459000, F, Options, ProgressCallback=Progress)
        if Args.SaveResultsDir:
            from analysis_jobs import AnnotateAnalysisResult
            Args.SaveResultsDir.mkdir(parents=True,exist_ok=True)
            Result=AnnotateAnalysisResult(Result,Options,Name+'.csv')
            (Args.SaveResultsDir/(Name+'-result.json')).write_text(Json.dumps(Result,allow_nan=False,separators=(',',':')))
        Signals = Result.get('signals') or [Result]
        Recovered = []
        for Signal in Signals:
            R = Signal.get('result') or Signal
            Recovered.append({
                'period_days': R.get('period'),
                'duration_days': R.get('period_duration'),
                'verdict': R.get('planet_assessment', {}).get('status'),
                'sde': R.get('period_sde'), 'boxed_windows': len(R.get('transits', [])),
                'observed_events': len(R.get('observed_events', [])),
            })
        Comparisons = []
        for Truth in Truths:
            Matches = [R for R in Recovered if R['period_days'] is not None]
            Nearest = min(Matches, key=lambda R: abs(R['period_days']/Truth['period_days'] - 1)) if Matches else None
            Comparisons.append({
                'truth': Truth, 'nearest': Nearest,
                'period_error_percent': 100 * (Nearest['period_days']/Truth['period_days'] - 1) if Nearest else None,
                'duration_error_percent': 100 * (Nearest['duration_days']/Truth['duration_days'] - 1) if Nearest and Nearest['duration_days'] else None,
                'period_recovered_within_1_percent': bool(Nearest and abs(Nearest['period_days']/Truth['period_days'] - 1) <= 0.01),
            })
        Row = dict(case=Name, samples=len(T), elapsed_seconds=Time.perf_counter()-Begin,
                   input_sha256=Hashlib.sha256(Np.c_[T, F].tobytes()).hexdigest(),
                   signals=Recovered, comparisons=Comparisons,
                   measured_progress_messages=len(Messages), last_progress=Messages[-1] if Messages else None)
        Results.append(Row)
        print(Name, Json.dumps({K:V for K,V in Row.items() if K not in ('input_sha256','last_progress')}), flush=True)
    Document = dict(seed=20261105, app_dir=str(Args.AppDir.resolve()),
                    elapsed_seconds=Time.perf_counter()-Started,
                    peak_process_rss_bytes=Resource.getrusage(Resource.RUSAGE_SELF).ru_maxrss,
                    results=Results)
    Args.Output.parent.mkdir(parents=True, exist_ok=True)
    Args.Output.write_text(Json.dumps(Document, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    RunApp()
