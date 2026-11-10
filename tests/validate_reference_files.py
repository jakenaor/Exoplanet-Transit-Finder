"""Opt-in checks on external user CSVs; never substitutes literature for a fit.

HD's constrained 3–4 day search checks preprocessing/shape recovery, not blind
discovery. TRAPPIST-1 uses explicit published stellar priors, not filename-based
behavior in the application. Original CSV time/passband provenance is unknown.
"""
import argparse as Argparse
import contextlib as Contextlib
import importlib.util
import importlib as Importlib
import io as Io
import json as Json
from pathlib import Path
import sys as Sys
import time as Time
from types import SimpleNamespace

APP_DIR = Path(__file__).resolve().parents[1] / 'Exoplanet data parsing tool'
Sys.path.insert(0, str(APP_DIR))
import analysis as Analysis
from analysis_jobs import AnnotateAnalysisResult
from parsers import ReadCurveUpload


#MARK: main
def RunApp():
    Parser=Argparse.ArgumentParser(description=__doc__)
    Parser.add_argument('--dataset-dir',type=Path,required=True, dest='DatasetDir')
    Parser.add_argument('--output-dir',type=Path,required=True, dest='OutputDir')
    Parser.add_argument('--only',action='append',choices=['hd209458','trappist1'], dest='Only')
    Parser.add_argument('--baseline-dir',type=Path,help='Load preserved analysis/TLS modules for a matched before comparison.', dest='BaselineDir')
    Args=Parser.parse_args()
    Engine=Analysis
    if Args.BaselineDir:
        for ModuleName,Filename in [('tls_search','tls_search.py'),('baseline_analysis','analysis.py')]:
            Spec=Importlib.util.spec_from_file_location(ModuleName,Args.BaselineDir/Filename)
            Module=Importlib.util.module_from_spec(Spec)
            Sys.modules[ModuleName]=Module
            Spec.loader.exec_module(Module)
            if ModuleName=='baseline_analysis':
                Engine=Module
    Args.OutputDir.mkdir(parents=True,exist_ok=True)
    for Name in Args.Only or ['hd209458','trappist1']:
        FilePath=Args.DatasetDir/(Name+'_time_flux.csv')
        Parsed=ReadCurveUpload(SimpleNamespace(filename=FilePath.name,file=Io.BytesIO(FilePath.read_bytes())),ReturnMetadata=True)
        Options=dict(Engine.DEFAULT_DETECTION_OPTIONS)
        Options.update(tls_threads=4,tls_oversampling=1,
                       _input_metadata=Parsed['input_metadata'],_cleaning_report=Parsed['cleaning'])
        if Name=='hd209458':
            Options.update(min_period=3,max_period=4)
        else:
            Options.update(stellar_radius=.1192,stellar_mass=.0898,tls_max_signals=3)
        Started=Time.monotonic()
        Updates=[]
        def Progress(Stage,Label,Details=None):
            Stamp=Time.monotonic()-Started
            Record=dict(elapsed_seconds=Stamp,stage=Stage,label=Label,**(Details or {}))
            Updates.append(Record)
            if Details:
                print(Name,round(Stamp,1),Stage,Details.get('completed_trials'),Details.get('total_trials'),Details.get('remaining_seconds_range'),file=Sys.stderr,flush=True)
        with Contextlib.redirect_stdout(Io.StringIO()):
            ProgressOptions={"progress_callback" if Args.BaselineDir else "ProgressCallback": Progress}
            RunCurveFunc=Engine.analyze if Args.BaselineDir else Engine.RunCurve
            Result=RunCurveFunc(Parsed['time'],Parsed['flux'],Options,**ProgressOptions)
        Result=AnnotateAnalysisResult(Result,Options,FilePath.name)
        if Args.BaselineDir:
            Result['provenance'].update(analysis_version='preserved pre-v63 HEAD',app_version='62',validation_only=True)
        (Args.OutputDir/f'{Name}-result.json').write_text(Json.dumps(Result,allow_nan=False,separators=(',',':')))
        Elapsed=Time.monotonic()-Started
        Summary=dict(file=FilePath.name,elapsed_seconds=Elapsed,period=Result.get('period'),
                     duration_hours=(Result.get('period_duration') or 0)*24,
                     assessment=Result['planet_assessment'],settings=Result.get('effective_settings') or {K:V for K,V in Options.items() if not K.startswith('_')},
                     predicted_windows=len(Result.get('predicted_windows',[])),observed_events=len(Result.get('observed_events',[])),
                     multi_signal_search=Result.get('multi_signal_search'),progress=Updates,
                     limits=__doc__,stellar_prior_source='https://exoplanetarchive.ipac.caltech.edu/overview/TRAPPIST-1' if Name=='trappist1' else None)
        (Args.OutputDir/f'{Name}-summary.json').write_text(Json.dumps(Summary,indent=2,allow_nan=False)+'\n')
        print(Name,'completed',round(Elapsed,2),'seconds',Result['period'],Summary['duration_hours'],Result['planet_assessment']['status'],flush=True)


if __name__=='__main__':
    RunApp()
