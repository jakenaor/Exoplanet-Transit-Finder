"""Opt-in end-to-end TLS measurements for physically integrated exposures.

Run with the repository interpreter. Numerical results are a small controlled
benchmark, not a universal completeness or uncertainty calibration claim.
"""
import argparse
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import time

import batman
import numpy as np


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
sys.path.insert(0, str(APP_DIR))
import analysis


def integrated_batman(observed_time, exposure_seconds, nominal_area_depth):
    params = batman.TransitParams()
    params.t0, params.per = .7, 1.7
    params.rp, params.a, params.inc = math.sqrt(nominal_area_depth), 6.8, 89.2
    params.ecc, params.w = 0.0, 90.0
    params.u, params.limb_dark = [.4804, .1867], "quadratic"
    flux = np.empty(len(observed_time))
    # Independent BATMAN integration, rather than the app's template integral.
    for exposure in np.unique(exposure_seconds):
        selected = exposure_seconds == exposure
        model = batman.TransitModel(params, observed_time[selected],
            supersample_factor=31, exp_time=float(exposure) / 86400.0)
        flux[selected] = model.light_curve(params)
    central = batman.TransitModel(params, np.array([params.t0])).light_curve(params)[0]
    impact = params.a * math.cos(math.radians(params.inc))
    duration = params.per / math.pi * math.asin(math.sqrt((1 + params.rp) ** 2 - impact ** 2)
        / (params.a * math.sin(math.radians(params.inc))))
    return flux, {"period_days": params.per, "epoch_days": params.t0,
        "intrinsic_duration_days": duration, "instantaneous_midtransit_depth_fraction": float(1 - central),
        "radius_ratio": params.rp, "nominal_area_depth_fraction": nominal_area_depth,
        "batman_supersample_factor": 31, "limb_darkening": params.u}


def fixture_inputs():
    layouts = [
        ("uniform_2min", np.arange(0, 8, 2 / 1440)),
        ("uniform_30min", np.arange(0, 24, 30 / 1440)),
        ("mixed_2min_30min", np.r_[np.arange(0, 5, 2 / 1440), np.arange(5, 20, 30 / 1440)]),
    ]
    for layout_index, (name, observed_time) in enumerate(layouts):
        if name == "uniform_2min":
            exposures = np.full(len(observed_time), 120.0)
        elif name == "uniform_30min":
            exposures = np.full(len(observed_time), 1800.0)
        else:
            exposures = np.where(observed_time < 5, 120.0, 1800.0)
        for depth_index, nominal_depth in enumerate((.008, .0006)):
            seed = 20261105 + layout_index * 100 + depth_index
            clean, truth = integrated_batman(observed_time, exposures, nominal_depth)
            sigma = .00025
            flux = clean + np.random.default_rng(seed).normal(0, sigma, len(clean))
            yield (f"{name}_area_{nominal_depth * 1e6:g}ppm", observed_time, exposures, flux, truth, sigma, seed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", action="append", help="Fixture name filter; repeatable.")
    args = parser.parse_args()
    started = time.perf_counter()
    rows = []
    for name, observed_time, exposures, flux, truth, sigma, seed in fixture_inputs():
        if args.only and name not in args.only:
            continue
        row = {"case": name, "samples": len(observed_time), "span_days": float(np.ptp(observed_time)),
            "seed": seed, "white_noise_sigma": sigma, "truth": truth,
            "exposure_seconds": sorted(np.unique(exposures).tolist()),
            "input_sha256": hashlib.sha256(np.c_[observed_time, exposures, flux].tobytes()).hexdigest(),
            "analyses": []}
        for condition in ("known_exposure", "unknown_exposure"):
            options = {**analysis.DEFAULT_DETECTION_OPTIONS, "min_period": 1.2, "max_period": 3.0,
                "tls_oversampling": 2, "tls_threads": 1, "_flux_uncertainty": np.full(len(flux), sigma),
                "_input_metadata": {"source_format": "controlled BATMAN injection", "exposure": {
                    "source": "injected per-row duration" if condition == "known_exposure" else "unknown"}}}
            if condition == "known_exposure":
                options["_exposure_seconds"] = exposures
            begin = time.perf_counter()
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    result = analysis.analyze(observed_time + 2459000, flux, options)
                tls = result.get("tls") or {}
                period, duration, depth = result.get("period"), result.get("period_duration"), tls.get("depth_fraction")
                measured = {"condition": condition, "elapsed_seconds": time.perf_counter() - begin,
                    "period_days": period, "intrinsic_template_duration_days": duration,
                    "template_midtransit_depth_fraction": depth,
                    "period_error_seconds": (period - truth["period_days"]) * 86400 if period else None,
                    "duration_error_percent": (duration / truth["intrinsic_duration_days"] - 1) * 100 if duration else None,
                    "depth_error_percent": (depth / truth["instantaneous_midtransit_depth_fraction"] - 1) * 100 if depth else None,
                    "period_recovered_within_1_percent": bool(period and abs(period / truth["period_days"] - 1) < .01),
                    "verdict": result.get("planet_assessment", {}).get("status"), "sde": result.get("period_sde"),
                    "observed_events": len(result.get("observed_events", [])),
                    "duration_fit": tls.get("duration_fit"), "duration_source": tls.get("duration_source"),
                    "exposure_metadata": result.get("exposure_metadata"),
                    "template_resolution": tls.get("template_resolution"), "actual_period_grid": tls.get("actual_period_grid")}
            except Exception as exc:
                measured = {"condition": condition, "elapsed_seconds": time.perf_counter() - begin,
                    "error": f"{type(exc).__name__}: {exc}"}
            row["analyses"].append(measured)
            print(name, condition, json.dumps({key: measured.get(key) for key in (
                "elapsed_seconds", "verdict", "period_error_seconds", "duration_error_percent", "depth_error_percent", "error")}))
        rows.append(row)
    document = {"elapsed_seconds": time.perf_counter() - started, "tls_workers_per_analysis": 1,
        "design": "Same physically integrated and noisy observations searched twice; only exposure metadata is supplied or withheld.",
        "depth_comparison": "Conditional intrinsic template mid-transit deficit versus the injected instantaneous BATMAN mid-transit deficit; not median-window depth or radius-ratio area.",
        "limits": ["Six seeded fixtures; not population recovery or calibrated uncertainty coverage.",
            "BATMAN uses 31 exposure subsamples; the app integrates its piecewise-linear TLS template exactly.",
            "Template shape, stellar assumptions and limb-darkening remain conditional; period search uses reference TLS unchanged.",
            "Unknown exposure is intentionally instantaneous and its uncertainty excludes exposure smearing systematics.",
            "White-noise fixtures omit stellar variability, correlated noise and mission-specific systematics.",
            "Durations/depths at an unrecovered period or an inconclusive fit are not valid accuracy measurements."],
        "cases": rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
    print("saved", args.output, "elapsed", document["elapsed_seconds"])


if __name__ == "__main__":
    main()
