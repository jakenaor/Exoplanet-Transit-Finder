"""Small reproducible BLS/TLS injection-recovery benchmark.

Run from the repository root with:
    .venv/bin/python tests/benchmark_searches.py
"""

import contextlib as Contextlib
import io as Io
from pathlib import Path
import sys as Sys
import time as Time

import batman as Batman
import numpy as Np


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
Sys.path.insert(0, str(APP_DIR))

import analysis as Analysis  # noqa: E402


TRUE_PERIOD = 2.4
DEPTHS = (0.0006, 0.0010, 0.0020)
SEEDS = range(6)


#MARK: injected curve
def InjectedCurve(Depth, Seed):
    TimeValues = Np.linspace(2459000.0, 2459012.0, 1200)
    Params = Batman.TransitParams()
    Params.t0 = 2459000.7
    Params.per = TRUE_PERIOD
    Params.rp = Np.sqrt(Depth)
    Params.a = 7.5
    Params.inc = 89.2
    Params.ecc = 0.0
    Params.w = 90.0
    Params.u = [0.4804, 0.1867]
    Params.limb_dark = "quadratic"
    CleanFlux = Batman.TransitModel(Params, TimeValues).light_curve(Params)
    Noise = Np.random.default_rng(1000 + Seed).normal(0.0, 0.0008, len(TimeValues))
    return TimeValues, CleanFlux + Noise


#MARK: run
def Run():
    Rows = []
    Started = Time.perf_counter()
    for Depth in DEPTHS:
        for Seed in SEEDS:
            TimeValues, FluxValues = InjectedCurve(Depth, Seed)
            for Mode in ("bls", "tls"):
                Options = dict(Analysis.DEFAULT_DETECTION_OPTIONS)
                Options.update({
                    "search_mode": Mode,
                    "min_period": 1.5,
                    "max_period": 3.5,
                    "tls_oversampling": 2,
                    "tls_threads": 1,
                })
                with Contextlib.redirect_stdout(Io.StringIO()):
                    Result = Analysis.RunCurve(TimeValues, FluxValues, Options)
                Recovered = (
                    Result["period"] is not None
                    and abs(Result["period"] - TRUE_PERIOD) / TRUE_PERIOD <= 0.01
                )
                Candidate = Result["planet_assessment"]["status"] in (
                    "possible_candidate",
                    "strong_candidate",
                )
                Rows.append((Depth, Mode, Recovered, Candidate, Result["period"]))

    print(f"Elapsed: {Time.perf_counter() - Started:.2f} seconds")
    for Depth in DEPTHS:
        for Mode in ("bls", "tls"):
            Subset = [Row for Row in Rows if Row[0] == Depth and Row[1] == Mode]
            Recovered = sum(Row[2] for Row in Subset)
            Candidates = sum(Row[3] for Row in Subset)
            Errors = [abs(Row[4] - TRUE_PERIOD) for Row in Subset if Row[4] is not None]
            print(
                f"{Depth * 1000000:4.0f} ppm {Mode.upper():3s}: "
                f"period {Recovered}/{len(Subset)}, "
                f"credible {Candidates}/{len(Subset)}, "
                f"median |period error| {Np.median(Errors):.6f} d"
            )


if __name__ == "__main__":
    Run()
