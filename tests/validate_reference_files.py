"""Opt-in checks on external user CSVs; never substitutes literature for a fit.

HD's constrained 3–4 day search checks preprocessing/shape recovery, not blind
discovery. TRAPPIST-1 uses explicit published stellar priors, not filename-based
behavior in the application. Original CSV time/passband provenance is unknown.
"""
import argparse
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / 'Exoplanet data parsing tool'
sys.path.insert(0, str(APP_DIR))
import analysis
from analysis_jobs import annotate_analysis_result
from parsers import parse_light_curve_upload


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--only',action='append',choices=['hd209458','trappist1'])
    parser.add_argument('--baseline-dir',type=Path,help='Load preserved analysis/TLS modules for a matched before comparison.')
    args=parser.parse_args()
    engine=analysis
    if args.baseline_dir:
        for module_name,filename in [('tls_search','tls_search.py'),('baseline_analysis','analysis.py')]:
            spec=importlib.util.spec_from_file_location(module_name,args.baseline_dir/filename)
            module=importlib.util.module_from_spec(spec)
            sys.modules[module_name]=module
            spec.loader.exec_module(module)
            if module_name=='baseline_analysis':
                engine=module
    args.output_dir.mkdir(parents=True,exist_ok=True)
    for name in args.only or ['hd209458','trappist1']:
        path=args.dataset_dir/(name+'_time_flux.csv')
        parsed=parse_light_curve_upload(SimpleNamespace(filename=path.name,file=io.BytesIO(path.read_bytes())),return_metadata=True)
        options=dict(engine.DEFAULT_DETECTION_OPTIONS)
        options.update(tls_threads=4,tls_oversampling=1,
                       _input_metadata=parsed['input_metadata'],_cleaning_report=parsed['cleaning'])
        if name=='hd209458':
            options.update(min_period=3,max_period=4)
        else:
            options.update(stellar_radius=.1192,stellar_mass=.0898,tls_max_signals=3)
        started=time.monotonic()
        updates=[]
        def progress(stage,label,details=None):
            stamp=time.monotonic()-started
            record=dict(elapsed_seconds=stamp,stage=stage,label=label,**(details or {}))
            updates.append(record)
            if details:
                print(name,round(stamp,1),stage,details.get('completed_trials'),details.get('total_trials'),details.get('remaining_seconds_range'),file=sys.stderr,flush=True)
        with contextlib.redirect_stdout(io.StringIO()):
            result=engine.analyze(parsed['time'],parsed['flux'],options,progress_callback=progress)
        result=annotate_analysis_result(result,options,path.name)
        if args.baseline_dir:
            result['provenance'].update(analysis_version='preserved pre-v63 HEAD',app_version='62',validation_only=True)
        (args.output_dir/f'{name}-result.json').write_text(json.dumps(result,allow_nan=False,separators=(',',':')))
        elapsed=time.monotonic()-started
        summary=dict(file=path.name,elapsed_seconds=elapsed,period=result.get('period'),
                     duration_hours=(result.get('period_duration') or 0)*24,
                     assessment=result['planet_assessment'],settings=result.get('effective_settings') or {k:v for k,v in options.items() if not k.startswith('_')},
                     predicted_windows=len(result.get('predicted_windows',[])),observed_events=len(result.get('observed_events',[])),
                     multi_signal_search=result.get('multi_signal_search'),progress=updates,
                     limits=__doc__,stellar_prior_source='https://exoplanetarchive.ipac.caltech.edu/overview/TRAPPIST-1' if name=='trappist1' else None)
        (args.output_dir/f'{name}-summary.json').write_text(json.dumps(summary,indent=2,allow_nan=False)+'\n')
        print(name,'completed',round(elapsed,2),'seconds',result['period'],summary['duration_hours'],result['planet_assessment']['status'],flush=True)


if __name__=='__main__':
    main()
