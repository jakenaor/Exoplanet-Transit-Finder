"""Opt-in end-to-end TLS measurements for physically integrated exposures.

Run with the repository interpreter. Numerical results are a small controlled
benchmark, not a universal completeness or uncertainty calibration claim.
"""
import argparse as Argparse
import contextlib as Contextlib
import hashlib as Hashlib
import io as Io
import json as Json
import math as Math
from pathlib import Path
import sys as Sys
import time as Time

import batman as Batman
import numpy as Np


APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
Sys.path.insert(0, str(APP_DIR))
import analysis as Analysis


#MARK: integrated batman
def IntegratedBatman(ObservedTime, ExposureSeconds, NominalAreaDepth):
    Params = Batman.TransitParams()
    Params.t0, Params.per = .7, 1.7
    Params.rp, Params.a, Params.inc = Math.sqrt(NominalAreaDepth), 6.8, 89.2
    Params.ecc, Params.w = 0.0, 90.0
    Params.u, Params.limb_dark = [.4804, .1867], "quadratic"
    Flux = Np.empty(len(ObservedTime))
    # independent batman integration, rather than the app's template integral.
    for Exposure in Np.unique(ExposureSeconds):
        Selected = ExposureSeconds == Exposure
        Model = Batman.TransitModel(Params, ObservedTime[Selected],
            supersample_factor=31, exp_time=float(Exposure) / 86400.0)
        Flux[Selected] = Model.light_curve(Params)
    Central = Batman.TransitModel(Params, Np.array([Params.t0])).light_curve(Params)[0]
    Impact = Params.a * Math.cos(Math.radians(Params.inc))
    Duration = Params.per / Math.pi * Math.asin(Math.sqrt((1 + Params.rp) ** 2 - Impact ** 2)
        / (Params.a * Math.sin(Math.radians(Params.inc))))
    return Flux, {"period_days": Params.per, "epoch_days": Params.t0,
        "intrinsic_duration_days": Duration, "instantaneous_midtransit_depth_fraction": float(1 - Central),
        "radius_ratio": Params.rp, "nominal_area_depth_fraction": NominalAreaDepth,
        "batman_supersample_factor": 31, "limb_darkening": Params.u}


#MARK: fixture inputs
def FixtureInputs():
    Layouts = [
        ("uniform_2min", Np.arange(0, 8, 2 / 1440)),
        ("uniform_30min", Np.arange(0, 24, 30 / 1440)),
        ("mixed_2min_30min", Np.r_[Np.arange(0, 5, 2 / 1440), Np.arange(5, 20, 30 / 1440)]),
    ]
    for LayoutIndex, (Name, ObservedTime) in enumerate(Layouts):
        if Name == "uniform_2min":
            Exposures = Np.full(len(ObservedTime), 120.0)
        elif Name == "uniform_30min":
            Exposures = Np.full(len(ObservedTime), 1800.0)
        else:
            Exposures = Np.where(ObservedTime < 5, 120.0, 1800.0)
        for DepthIndex, NominalDepth in enumerate((.008, .0006)):
            Seed = 20261105 + LayoutIndex * 100 + DepthIndex
            Clean, Truth = IntegratedBatman(ObservedTime, Exposures, NominalDepth)
            Sigma = .00025
            Flux = Clean + Np.random.default_rng(Seed).normal(0, Sigma, len(Clean))
            yield (f"{Name}_area_{NominalDepth * 1e6:g}ppm", ObservedTime, Exposures, Flux, Truth, Sigma, Seed)


#MARK: main
def RunApp():
    Parser = Argparse.ArgumentParser(description=__doc__)
    Parser.add_argument("--output", type=Path, required=True, dest='Output')
    Parser.add_argument("--only", action="append", help="Fixture name filter; repeatable.", dest='Only')
    Args = Parser.parse_args()
    Started = Time.perf_counter()
    Rows = []
    for Name, ObservedTime, Exposures, Flux, Truth, Sigma, Seed in FixtureInputs():
        if Args.Only and Name not in Args.Only:
            continue
        Row = {"case": Name, "samples": len(ObservedTime), "span_days": float(Np.ptp(ObservedTime)),
            "seed": Seed, "white_noise_sigma": Sigma, "truth": Truth,
            "exposure_seconds": sorted(Np.unique(Exposures).tolist()),
            "input_sha256": Hashlib.sha256(Np.c_[ObservedTime, Exposures, Flux].tobytes()).hexdigest(),
            "analyses": []}
        for Condition in ("known_exposure", "unknown_exposure"):
            Options = {**Analysis.DEFAULT_DETECTION_OPTIONS, "min_period": 1.2, "max_period": 3.0,
                "tls_oversampling": 2, "tls_threads": 1, "_flux_uncertainty": Np.full(len(Flux), Sigma),
                "_input_metadata": {"source_format": "controlled BATMAN injection", "exposure": {
                    "source": "injected per-row duration" if Condition == "known_exposure" else "unknown"}}}
            if Condition == "known_exposure":
                Options["_exposure_seconds"] = Exposures
            Begin = Time.perf_counter()
            try:
                with Contextlib.redirect_stdout(Io.StringIO()):
                    Result = Analysis.RunCurve(ObservedTime + 2459000, Flux, Options)
                Tls = Result.get("tls") or {}
                Period, Duration, Depth = Result.get("period"), Result.get("period_duration"), Tls.get("depth_fraction")
                Measured = {"condition": Condition, "elapsed_seconds": Time.perf_counter() - Begin,
                    "period_days": Period, "intrinsic_template_duration_days": Duration,
                    "template_midtransit_depth_fraction": Depth,
                    "period_error_seconds": (Period - Truth["period_days"]) * 86400 if Period else None,
                    "duration_error_percent": (Duration / Truth["intrinsic_duration_days"] - 1) * 100 if Duration else None,
                    "depth_error_percent": (Depth / Truth["instantaneous_midtransit_depth_fraction"] - 1) * 100 if Depth else None,
                    "period_recovered_within_1_percent": bool(Period and abs(Period / Truth["period_days"] - 1) < .01),
                    "verdict": Result.get("planet_assessment", {}).get("status"), "sde": Result.get("period_sde"),
                    "observed_events": len(Result.get("observed_events", [])),
                    "duration_fit": Tls.get("duration_fit"), "duration_source": Tls.get("duration_source"),
                    "exposure_metadata": Result.get("exposure_metadata"),
                    "template_resolution": Tls.get("template_resolution"), "actual_period_grid": Tls.get("actual_period_grid")}
            except Exception as Exc:
                Measured = {"condition": Condition, "elapsed_seconds": Time.perf_counter() - Begin,
                    "error": f"{type(Exc).__name__}: {Exc}"}
            Row["analyses"].append(Measured)
            print(Name, Condition, Json.dumps({Key: Measured.get(Key) for Key in (
                "elapsed_seconds", "verdict", "period_error_seconds", "duration_error_percent", "depth_error_percent", "error")}))
        Rows.append(Row)
    Document = {"elapsed_seconds": Time.perf_counter() - Started, "tls_workers_per_analysis": 1,
        "design": "Same physically integrated and noisy observations searched twice; only exposure metadata is supplied or withheld.",
        "depth_comparison": "Conditional intrinsic template mid-transit deficit versus the injected instantaneous BATMAN mid-transit deficit; not median-window depth or radius-ratio area.",
        "limits": ["Six seeded fixtures; not population recovery or calibrated uncertainty coverage.",
            "BATMAN uses 31 exposure subsamples; the app integrates its piecewise-linear TLS template exactly.",
            "Template shape, stellar assumptions and limb-darkening remain conditional; period search uses reference TLS unchanged.",
            "Unknown exposure is intentionally instantaneous and its uncertainty excludes exposure smearing systematics.",
            "White-noise fixtures omit stellar variability, correlated noise and mission-specific systematics.",
            "Durations/depths at an unrecovered period or an inconclusive fit are not valid accuracy measurements."],
        "cases": Rows}
    Args.Output.parent.mkdir(parents=True, exist_ok=True)
    Args.Output.write_text(Json.dumps(Document, indent=2, allow_nan=False) + "\n")
    print("saved", Args.Output, "elapsed", Document["elapsed_seconds"])


if __name__ == "__main__":
    RunApp()
