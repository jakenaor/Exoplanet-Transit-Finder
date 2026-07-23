"""Small reproducible BLS/TLS injection-recovery benchmark.

Run from the repository root with:
    .venv/bin/python tests/benchmark_searches.py
"""

import contextlib
import io
from pathlib import Path
import sys
import time

import batman
import numpy as np


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
sys.path.insert(0, str(APP_DIR))

import analysis  # noqa: E402


TRUE_PERIOD = 2.4
DEPTHS = (0.0006, 0.0010, 0.0020)
SEEDS = range(6)


def injected_curve(depth, seed):
    time_values = np.linspace(2459000.0, 2459012.0, 1200)
    params = batman.TransitParams()
    params.t0 = 2459000.7
    params.per = TRUE_PERIOD
    params.rp = np.sqrt(depth)
    params.a = 7.5
    params.inc = 89.2
    params.ecc = 0.0
    params.w = 90.0
    params.u = [0.4804, 0.1867]
    params.limb_dark = "quadratic"
    clean_flux = batman.TransitModel(params, time_values).light_curve(params)
    noise = np.random.default_rng(1000 + seed).normal(0.0, 0.0008, len(time_values))
    return time_values, clean_flux + noise


def run():
    rows = []
    started = time.perf_counter()
    for depth in DEPTHS:
        for seed in SEEDS:
            time_values, flux_values = injected_curve(depth, seed)
            for mode in ("bls", "tls"):
                options = dict(analysis.DEFAULT_DETECTION_OPTIONS)
                options.update({
                    "search_mode": mode,
                    "min_period": 1.5,
                    "max_period": 3.5,
                    "tls_oversampling": 2,
                    "tls_threads": 1,
                })
                with contextlib.redirect_stdout(io.StringIO()):
                    result = analysis.analyze(time_values, flux_values, options)
                recovered = (
                    result["period"] is not None
                    and abs(result["period"] - TRUE_PERIOD) / TRUE_PERIOD <= 0.01
                )
                candidate = result["planet_assessment"]["status"] in (
                    "possible_candidate",
                    "strong_candidate",
                )
                rows.append((depth, mode, recovered, candidate, result["period"]))

    print(f"Elapsed: {time.perf_counter() - started:.2f} seconds")
    for depth in DEPTHS:
        for mode in ("bls", "tls"):
            subset = [row for row in rows if row[0] == depth and row[1] == mode]
            recovered = sum(row[2] for row in subset)
            candidates = sum(row[3] for row in subset)
            errors = [abs(row[4] - TRUE_PERIOD) for row in subset if row[4] is not None]
            print(
                f"{depth * 1000000:4.0f} ppm {mode.upper():3s}: "
                f"period {recovered}/{len(subset)}, "
                f"credible {candidates}/{len(subset)}, "
                f"median |period error| {np.median(errors):.6f} d"
            )


if __name__ == "__main__":
    run()
