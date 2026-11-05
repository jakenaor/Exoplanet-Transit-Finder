"""Seeded end-to-end scientific checks; emits measurements rather than a score.

Run with the repo interpreter. --app-dir permits comparison with a preserved
checkout. This deliberately uses the installed reference TLS engine.
"""
import argparse
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import resource
import sys
import time

import batman
import numpy as np


def injected(time_values, period=2.4, epoch=0.7, radius_ratio=0.09, a=7.5):
    params = batman.TransitParams()
    params.t0 = epoch
    params.per = period
    params.rp = radius_ratio
    params.a = a
    params.inc = 89.2
    params.ecc = 0.0
    params.w = 90.0
    params.u = [0.4804, 0.1867]
    params.limb_dark = 'quadratic'
    flux = batman.TransitModel(params, time_values).light_curve(params)
    b = a * math.cos(math.radians(params.inc))
    duration = period / math.pi * math.asin(
        math.sqrt((1 + radius_ratio) ** 2 - b ** 2) /
        (a * math.sin(math.radians(params.inc)))
    )
    return flux, {'period_days': period, 'duration_days': duration,
                  'radius_ratio': radius_ratio, 'epoch_days': epoch}


def fixtures():
    base = np.linspace(0, 12, 1200)
    rng = np.random.default_rng(20261105)
    irregular = np.sort(rng.uniform(0, 12, 1200))
    gapped = np.r_[np.linspace(0, 6, 600), np.linspace(24, 30, 600)]
    mixed = np.r_[np.arange(0, 6, 0.006), np.arange(6, 12, 0.025)]
    for name, t in [('continuous', base), ('irregular', irregular),
                    ('gapped', gapped), ('mixed_cadence', mixed)]:
        clean, truth = injected(t)
        flux = clean + rng.normal(0, 0.0008, len(t))
        if name == 'gapped':
            flux[t > 20] *= 1.08
        yield name, t, flux, [truth], 1
    clean, truth = injected(base, radius_ratio=math.sqrt(0.0006))
    yield 'shallow_600ppm', base, clean + rng.normal(0, 0.0008, len(base)), [truth], 1
    yield 'white_noise', base, 1 + rng.normal(0, 0.0008, len(base)), [], 1
    t = np.linspace(0, 16, 1800)
    f1, truth1 = injected(t, period=1.7, epoch=0.4, radius_ratio=0.095, a=6.8)
    f2, truth2 = injected(t, period=2.8, epoch=1.0, radius_ratio=0.075, a=8.7)
    yield 'two_planets', t, f1 * f2 + rng.normal(0, 0.0005, len(t)), [truth1, truth2], 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'Exoplanet data parsing tool')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--only', action='append', help='Run just this named fixture (repeatable).')
    parser.add_argument('--save-results-dir', type=Path, help='Save full current results for browser inspection.')
    args = parser.parse_args()
    sys.path.insert(0, str(args.app_dir.resolve()))
    import analysis
    results = []
    started = time.perf_counter()
    for name, t, f, truths, max_signals in fixtures():
        if args.only and name not in args.only:
            continue
        options = dict(analysis.DEFAULT_DETECTION_OPTIONS)
        options.update(search_mode='tls', min_period=1.4, max_period=3.5,
                       tls_oversampling=2, tls_threads=1, tls_max_signals=max_signals,
                       max_signals=max_signals)
        begin = time.perf_counter()
        messages = []
        def progress(stage, label, details=None):
            if details:
                messages.append(dict(stage=stage, **details))
        with contextlib.redirect_stdout(io.StringIO()):
            result = analysis.analyze(t + 2459000, f, options, progress_callback=progress)
        if args.save_results_dir:
            from analysis_jobs import annotate_analysis_result
            args.save_results_dir.mkdir(parents=True,exist_ok=True)
            result=annotate_analysis_result(result,options,name+'.csv')
            (args.save_results_dir/(name+'-result.json')).write_text(json.dumps(result,allow_nan=False,separators=(',',':')))
        signals = result.get('signals') or [result]
        recovered = []
        for signal in signals:
            r = signal.get('result') or signal
            recovered.append({
                'period_days': r.get('period'),
                'duration_days': r.get('period_duration'),
                'verdict': r.get('planet_assessment', {}).get('status'),
                'sde': r.get('period_sde'), 'boxed_windows': len(r.get('transits', [])),
                'observed_events': len(r.get('observed_events', [])),
            })
        comparisons = []
        for truth in truths:
            matches = [r for r in recovered if r['period_days'] is not None]
            nearest = min(matches, key=lambda r: abs(r['period_days']/truth['period_days'] - 1)) if matches else None
            comparisons.append({
                'truth': truth, 'nearest': nearest,
                'period_error_percent': 100 * (nearest['period_days']/truth['period_days'] - 1) if nearest else None,
                'duration_error_percent': 100 * (nearest['duration_days']/truth['duration_days'] - 1) if nearest and nearest['duration_days'] else None,
                'period_recovered_within_1_percent': bool(nearest and abs(nearest['period_days']/truth['period_days'] - 1) <= 0.01),
            })
        row = dict(case=name, samples=len(t), elapsed_seconds=time.perf_counter()-begin,
                   input_sha256=hashlib.sha256(np.c_[t, f].tobytes()).hexdigest(),
                   signals=recovered, comparisons=comparisons,
                   measured_progress_messages=len(messages), last_progress=messages[-1] if messages else None)
        results.append(row)
        print(name, json.dumps({k:v for k,v in row.items() if k not in ('input_sha256','last_progress')}), flush=True)
    document = dict(seed=20261105, app_dir=str(args.app_dir.resolve()),
                    elapsed_seconds=time.perf_counter()-started,
                    peak_process_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    results=results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
