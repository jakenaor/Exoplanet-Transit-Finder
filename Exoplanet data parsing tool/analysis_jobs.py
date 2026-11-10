"""Run light-curve analyses in cancellable background processes."""

#MARK: imports
import inspect as Inspect
from datetime import datetime as Datetime, timezone as Timezone
from importlib import metadata as PackageMetadata
import json as Json
import hashlib as Hashlib
import math as Math
import multiprocessing as Multiprocessing
import os as Os
import signal as Signal
import statistics as Statistics
import sys as Sys
import threading as Threading
import time as Time
import uuid as Uuid

import numpy as Np

from analysis import RunCurve


#MARK: core stuffs
TERMINAL_STATES = {"completed", "failed", "cancelled"}
RESULT_SCHEMA_VERSION = 2
ANALYSIS_VERSION = "2026.11.10.1"
APP_VERSION = "66"
PROGRESS_FIELDS = ("completed_trials", "total_trials", "estimated_remaining_seconds",
                   "eta_lower_seconds", "eta_upper_seconds", "eta_scope", "work_completed",
                   "work_total", "remaining_seconds_range", "eta_state", "search_elapsed_seconds",
                   "throughput_elapsed_seconds", "search_complete", "eta_method",
                   "eta_sample_seconds", "eta_variation")


#MARK: run progress
class ExecutionTelemetry:
    """Keep job timings and a bounded sample of progress updates."""

    #MARK: event timing
    def __init__(self, HistoryLimit=256):
        self.HistoryLimit = max(8, int(HistoryLimit))
        self.History = []
        self.SampleInterval = 5.0
        self.Sampled = False
        self.Stages = []
        self.Searches = []
        self.CurrStage = None
        self.LastSearchElapsed = None

    #MARK: run progress
    def update(self, Stage, Label, Details, Elapsed):
        Elapsed = max(0.0, float(Elapsed))
        Changed = self.CurrStage is None or Stage != self.CurrStage["stage"]
        if Changed:
            self._CloseStage(Elapsed)
            self.CurrStage = {"stage": str(Stage), "stage_label": str(Label),
                                  "started_elapsed_seconds": Elapsed}
        Progress = CleanedProgressDetails(Details)
        SearchId = self._UpdateSearch(Progress, Elapsed)
        Snapshot = {"elapsed_seconds": Elapsed, "stage": str(Stage), **Progress}
        if SearchId is not None:
            Snapshot["search_id"] = SearchId
        Prev = self.History[-1] if self.History else {}
        EtaChanged = Progress.get("eta_state") != Prev.get("eta_state")
        # keep stage changes even when the normal sampling interval has not passed.
        if (not self.History or Changed or EtaChanged or Progress.get("search_complete")
                or Elapsed - Prev.get("elapsed_seconds", 0.0) >= self.SampleInterval):
            self.History.append(Snapshot)
            if len(self.History) > self.HistoryLimit:
                # keep the first and latest samples as older history is thinned.
                Latest = self.History[-1]
                self.History = self.History[::2]
                if self.History[-1] is not Latest:
                    self.History.append(Latest)
                self.SampleInterval *= 2.0
                self.Sampled = True

    #MARK: separating search runs
    def _UpdateSearch(self, Progress, Elapsed):
        if Progress.get("total_trials") is None or Progress.get("completed_trials") is None:
            return None
        SearchElapsed = Progress.get("search_elapsed_seconds")
        NewSearch = (
            not self.Searches
            or self.Searches[-1].get("finished_elapsed_seconds") is not None
            or (SearchElapsed is not None and self.LastSearchElapsed is not None
                and SearchElapsed < self.LastSearchElapsed)
        )
        # tls can send the final update twice. that is still one search.
        if NewSearch and not Progress.get("search_complete"):
            self.Searches.append({
                "search_id": len(self.Searches) + 1,
                "started_elapsed_seconds": max(0.0, Elapsed - (SearchElapsed or 0.0)),
                "total_trials": Progress["total_trials"],
            })
        self.LastSearchElapsed = SearchElapsed
        if not self.Searches:
            return None
        Search = self.Searches[-1]
        Search["completed_trials"] = Progress["completed_trials"]
        if Progress.get("search_complete"):
            Search["finished_elapsed_seconds"] = Elapsed
            Search["duration_seconds"] = max(0.0, Elapsed - Search["started_elapsed_seconds"])
        return Search["search_id"]

    #MARK: event timing
    def _CloseStage(self, Elapsed):
        if self.CurrStage is not None:
            Stage = {**self.CurrStage, "finished_elapsed_seconds": Elapsed,
                     "duration_seconds": max(0.0, Elapsed - self.CurrStage["started_elapsed_seconds"])}
            self.Stages.append(Stage)
            self.Stages = self.Stages[-64:]
            self.CurrStage = None

    #MARK: run progress
    def finish(self, Stage, Label, Elapsed, QueueWait=0.0):
        self.update(Stage, Label, {}, Elapsed)
        self._CloseStage(Elapsed)
        Searches = {Search["search_id"]: Search for Search in self.Searches}
        History = [dict(Snapshot) for Snapshot in self.History]
        Errors, Coverage = [], []
        # a cancelled search has no completion time to compare against.
        for Snapshot in History:
            Forecast = Snapshot.get("estimated_remaining_seconds")
            SearchEnd = Searches.get(Snapshot.get("search_id"), {}).get("finished_elapsed_seconds")
            if Forecast is None or SearchEnd is None:
                continue
            Actual = max(0.0, SearchEnd - Snapshot["elapsed_seconds"])
            Error = Forecast - Actual
            Snapshot.update({"actual_remaining_seconds": Actual, "eta_error_seconds": Error})
            Errors.append(abs(Error))
            Low, High = Snapshot.get("eta_lower_seconds"), Snapshot.get("eta_upper_seconds")
            if Low is not None and High is not None:
                Covered = Low <= Actual <= High
                Snapshot["range_contains_actual"] = Covered
                Coverage.append(Covered)
        return {"schema_version": 1, "elapsed_seconds": max(0.0, float(Elapsed)),
                "queue_wait_seconds": max(0.0, float(QueueWait)), "stage_durations": self.Stages,
                "searches": self.Searches, "progress_history": History,
                "progress_history_limit": self.HistoryLimit,
                "progress_history_sampled": self.Sampled,
                "eta_audit": {"scope": "search", "retained_forecasts_audited": len(Errors),
                    "mean_absolute_error_seconds": Statistics.mean(Errors) if Errors else None,
                    "median_absolute_error_seconds": Statistics.median(Errors) if Errors else None,
                    "ranges_audited": len(Coverage),
                    "observed_range_coverage_fraction": Statistics.mean(Coverage) if Coverage else None,
                    "note": "Audit uses retained forecasts only; observed throughput ranges are not confidence intervals."}}


#MARK: run progress
def AnnotateAnalysisResult(Result, Options=None, SourceFile=None):
    """Add version and source metadata to a newly computed result."""
    if not isinstance(Result, dict):
        raise ValueError("The analysis worker did not return a result object.")
    Options = Options or {}
    PrevProvenance = Result.get("provenance") if isinstance(Result.get("provenance"), dict) else {}
    SourceFile = (SourceFile or (Options.get("_input_metadata") or {}).get("source_file")
                   or Result.get("source_file") or PrevProvenance.get("source_file"))
    #MARK: recording the environment
    Dependencies = {}
    for Name in ("numpy", "scipy", "astropy", "transitleastsquares", "batman-package", "numba"):
        try:
            Dependencies[Name] = PackageMetadata.version(Name)
        except PackageMetadata.PackageNotFoundError:
            Dependencies[Name] = "unavailable"
    AnalyzedAt = Datetime.now(Timezone.utc).isoformat()
    Effective = Result.get("effective_settings") or {K: V for K, V in Options.items() if not K.startswith("_")}
    Result["result_schema_version"] = RESULT_SCHEMA_VERSION
    Result["analyzed_at"] = AnalyzedAt
    Result["provenance"] = {"app_version": APP_VERSION, "analysis_version": ANALYSIS_VERSION,
        "result_schema_version": RESULT_SCHEMA_VERSION, "analyzed_at": AnalyzedAt,
        "dependency_versions": Dependencies, "python_version": Sys.version.split()[0], "effective_settings": Effective,
        "source_file": SourceFile, "legacy": False}
    if Options.get("_input_metadata") is not None:
        Result.setdefault("input_metadata", Options["_input_metadata"])
    if Options.get("_cleaning_report") is not None:
        Result.setdefault("cleaning", Options["_cleaning_report"])
    #MARK: run progress
    # a later signal can have different search settings from the first one.
    for SignalResult in Result.get("signals", []):
        if isinstance(SignalResult, dict):
            SignalAnalyzedAt = SignalResult.get("analyzed_at") or AnalyzedAt
            SignalResult["result_schema_version"] = RESULT_SCHEMA_VERSION
            SignalResult["analyzed_at"] = SignalAnalyzedAt
            SignalResult["provenance"] = {**Result["provenance"],
                "analyzed_at": SignalAnalyzedAt,
                "effective_settings": SignalResult.get("effective_settings") or Effective}
            if Result.get("input_metadata") is not None:
                SignalResult.setdefault("input_metadata", Result["input_metadata"])
            if SignalResult.get("cleaning_report") is not None:
                SignalResult.setdefault("cleaning", SignalResult["cleaning_report"])
            elif Result.get("cleaning") is not None:
                SignalResult.setdefault("cleaning", Result["cleaning"])
    # catch invalid result values here, before a browser tries to read them.
    try:
        Json.dumps(Result, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as Exc:
        raise ValueError("Analysis returned nonfinite or unsupported result values; no invalid JSON result was saved.") from Exc
    return Result


#MARK: worker stuffs
def CleanedProgressDetails(Details):
    """Keep the progress fields we can safely send to the browser."""
    Output = {}
    for Key in PROGRESS_FIELDS:
        Value = Details.get(Key)
        if Key == "search_complete":
            if isinstance(Value, bool):
                Output[Key] = Value
        elif Key in {"eta_scope", "eta_state", "eta_method"}:
            if isinstance(Value, str):
                Output[Key] = Value[:40]
        elif Key == "remaining_seconds_range":
            if isinstance(Value, (list, tuple)) and len(Value) == 2:
                Numbers = [float(V) for V in Value if isinstance(V, (int, float)) and Math.isfinite(V) and V >= 0]
                if len(Numbers) == 2:
                    Output[Key] = sorted(Numbers)
        elif isinstance(Value, (int, float)) and not isinstance(Value, bool) and Math.isfinite(Value) and Value >= 0:
            Output[Key] = Value
        elif Value is None:
            Output[Key] = None
    return Output


#MARK: worker stuffs
def _AnalysisWorker(SendConnection, TimeValues, FluxValues, Options, Runner, SourceFile=None):
    """Run an analysis and report either its result or its error."""
    #MARK: run progress
    def PublishProgress(Stage, StageLabel, Details=None, **Extra):
        try:
            SendConnection.send({
                "status": "progress",
                "stage": str(Stage),
                "stage_label": str(StageLabel),
                **CleanedProgressDetails({**(Details or {}), **Extra}),
            })
        except (BrokenPipeError, EOFError, OSError):
            pass

    try:
        # give the job its own process group so cancellation reaches its workers.
        if hasattr(Os, "setsid"):
            try:
                Os.setsid()
            except OSError:
                pass
        #MARK: callback compatibility
        # older runners still use progress_callback.
        try:
            Parameters = Inspect.signature(Runner).parameters.values()
            Parameters = list(Parameters)
            if any(Parameter.name == "ProgressCallback" for Parameter in Parameters):
                ProgressKeyword = "ProgressCallback"
            elif any(Parameter.name == "progress_callback" for Parameter in Parameters):
                ProgressKeyword = "progress_callback"
            elif any(Parameter.kind == Inspect.Parameter.VAR_KEYWORD for Parameter in Parameters):
                ProgressKeyword = "ProgressCallback"
            else:
                ProgressKeyword = None
        except (TypeError, ValueError):
            ProgressKeyword = None
        if ProgressKeyword:
            Result = Runner(
                TimeValues,
                FluxValues,
                Options,
                **{ProgressKeyword: PublishProgress},
            )
        else:
            Result = Runner(TimeValues, FluxValues, Options)
        Message = {"status": "completed", "result": AnnotateAnalysisResult(Result, Options, SourceFile)}
    except BaseException as Exc:  # report worker exits as well as ordinary errors.
        Message = {"status": "failed", "error": str(Exc) or Exc.__class__.__name__}

    #MARK: core stuffs
    try:
        SendConnection.send(Message)
    except (BrokenPipeError, EOFError, OSError):
        pass
    finally:
        SendConnection.close()


#MARK: worker stuffs
class AnalysisJobManager:
    """Queue analyses and manage their worker processes."""

    #MARK: queue settings
    def __init__(
        self,
        MaxRunning=1,
        RetentionSeconds=3600,
        StartMethod="spawn",
        Runner=RunCurve,
        **LegacyOptions,
    ):
        #MARK: old calls
        # accept the old names, but do not silently accept other extra settings.
        MaxRunning = LegacyOptions.pop("max_running", MaxRunning)
        RetentionSeconds = LegacyOptions.pop("retention_seconds", RetentionSeconds)
        StartMethod = LegacyOptions.pop("start_method", StartMethod)
        if LegacyOptions:
            raise TypeError(f"Unknown job options: {', '.join(LegacyOptions)}")
        self.MaxRunning = max(1, int(MaxRunning))
        self.RetentionSeconds = max(60, int(RetentionSeconds))
        self.Context = Multiprocessing.get_context(StartMethod)
        self.Runner = Runner
        self.Jobs = {}
        self.Lock = Threading.RLock()
        self.Closed = False

    #MARK: worker stuffs
    def submit(self, TimeValues, FluxValues, Options, SourceFile=None):
        JobId = Uuid.uuid4().hex
        Now = Time.time()
        Record = {
            "job_id": JobId,
            "status": "queued",
            "source_file": SourceFile,
            "submitted_at": Now,
            "started_at": None,
            "finished_at": None,
            "time_values": TimeValues,
            "flux_values": FluxValues,
            "options": Options,
            "process": None,
            "connection": None,
            "result": None,
            "error": None,
            "stage": "queued",
            "stage_label": "Waiting for analysis worker",
            "batch_id": Options.get("_batch_id"),
            "request_id": Options.get("_request_id"),
            "progress": {},
            "telemetry": None,
            "execution": None,
        }
        with self.Lock:
            if self.Closed:
                raise RuntimeError("Analysis job manager is shutting down.")
            self._CleanupLocked(Now)
            #MARK: core stuffs
            # a retry should reconnect to the same work, not start another search.
            if Record["request_id"]:
                Digest = Hashlib.sha256(Json.dumps({
                    "source_file": SourceFile, "settings": Options,
                }, sort_keys=True, default=str).encode())
                Digest.update(Np.asarray(TimeValues, dtype=float).tobytes())
                Digest.update(Np.asarray(FluxValues, dtype=float).tobytes())
                Fingerprint = Digest.hexdigest()
                Record["request_fingerprint"] = Fingerprint
                for Existing in self.Jobs.values():
                    if Existing.get("request_id") == Record["request_id"]:
                        if Existing.get("request_fingerprint") != Fingerprint:
                            raise ValueError("This submission ID was already used for different analysis inputs.")
                        return self._PublicRecordLocked(Existing, IncludeResult=True)
            self.Jobs[JobId] = Record
            self._ScheduleLocked()
            return self._PublicRecordLocked(Record, IncludeResult=False)

    #MARK: worker stuffs
    def get(self, JobId, IncludeResult=True):
        with self.Lock:
            self._CleanupLocked(Time.time())
            Record = self.Jobs.get(JobId)
            if Record is None:
                return None
            return self._PublicRecordLocked(Record, IncludeResult=IncludeResult)

    def FindByRequestId(self, RequestId, IncludeResult=True):
        """Find a job when its submission response never reached the browser."""
        if not isinstance(RequestId, str) or not RequestId or len(RequestId) > 160:
            return None
        with self.Lock:
            self._CleanupLocked(Time.time())
            for Record in self.Jobs.values():
                if Record.get("request_id") == RequestId:
                    return self._PublicRecordLocked(Record, IncludeResult=IncludeResult)
        return None

    #MARK: cancel runs
    def cancel(self, JobId):
        Process = None
        with self.Lock:
            Record = self.Jobs.get(JobId)
            if Record is None:
                return None
            if Record["status"] in TERMINAL_STATES:
                return self._PublicRecordLocked(Record)
            if Record["status"] == "queued":
                self._MarkCancelledLocked(Record)
                self._ScheduleLocked()
                return self._PublicRecordLocked(Record)
            Record["status"] = "cancelling"
            Record["stage"] = "cancelling"
            Record["stage_label"] = "Cancelling analysis"
            Process = Record.get("process")

        self._TerminateProcess(Process)

        with self.Lock:
            Record = self.Jobs.get(JobId)
            if Record is None:
                return None
            if Record["status"] not in TERMINAL_STATES:
                self._MarkCancelledLocked(Record)
                Record["error"] = None
                Record["result"] = None
            self._ScheduleLocked()
            return self._PublicRecordLocked(Record)

    #MARK: core stuffs
    def shutdown(self):
        with self.Lock:
            if self.Closed:
                return
            self.Closed = True
            Active = [
                Record.get("process")
                for Record in self.Jobs.values()
                if Record["status"] in {"running", "cancelling"}
            ]
            for Record in self.Jobs.values():
                if Record["status"] == "queued":
                    self._MarkCancelledLocked(Record)

        for Process in Active:
            self._TerminateProcess(Process)

    #MARK: worker stuffs
    def _RunningCountLocked(self):
        return sum(
            Record["status"] in {"running", "cancelling"}
            for Record in self.Jobs.values()
        )

    #MARK: worker stuffs
    def _ScheduleLocked(self):
        if self.Closed:
            return
        while self._RunningCountLocked() < self.MaxRunning:
            Queued = next(
                (Record for Record in self.Jobs.values() if Record["status"] == "queued"),
                None,
            )
            if Queued is None:
                return
            self._LaunchLocked(Queued)

    #MARK: worker stuffs
    def _LaunchLocked(self, Record):
        ReceiveConnection, SendConnection = self.Context.Pipe(duplex=False)
        Process = self.Context.Process(
            target=_AnalysisWorker,
            args=(
                SendConnection,
                Record["time_values"],
                Record["flux_values"],
                Record["options"],
                self.Runner,
                Record.get("source_file"),
            ),
            name=f"transit-analysis-{Record['job_id'][:8]}",
        )
        Process.daemon = False
        Record["status"] = "running"
        Record["started_at"] = Time.time()
        Record["telemetry"] = ExecutionTelemetry()
        Record["telemetry"].update("starting", "Starting analysis", {}, 0.0)
        Record["stage"] = "starting"
        Record["stage_label"] = "Starting analysis"
        Record["process"] = Process
        Record["connection"] = ReceiveConnection
        try:
            Process.start()
        except Exception as Exc:
            ReceiveConnection.close()
            SendConnection.close()
            Record["status"] = "failed"
            Record["error"] = f"Could not start analysis worker: {Exc}"
            Record["finished_at"] = Time.time()
            Record["stage"] = "failed"
            Record["stage_label"] = "Analysis failed"
            self._DropInputsLocked(Record)
            return
        SendConnection.close()
        # the monitor waits for messages without blocking http requests.
        Monitor = Threading.Thread(
            target=self._Monitor,
            args=(Record["job_id"], Process, ReceiveConnection),
            daemon=True,
            name=f"analysis-monitor-{Record['job_id'][:8]}",
        )
        Monitor.start()

    #MARK: run progress
    def _Monitor(self, JobId, Process, ReceiveConnection):
        Message = None
        try:
            while True:
                Incoming = ReceiveConnection.recv()
                if Incoming.get("status") != "progress":
                    Message = Incoming
                    break
                with self.Lock:
                    Record = self.Jobs.get(JobId)
                    if Record is None or Record["status"] != "running":
                        continue
                    Record["stage"] = Incoming.get("stage") or Record.get("stage")
                    Record["stage_label"] = (
                        Incoming.get("stage_label")
                        or Record.get("stage_label")
                    )
                    Record["progress"] = CleanedProgressDetails(Incoming)
                    Record["progress_updated_at"] = Time.time()
                    Record["telemetry"].update(Record["stage"], Record["stage_label"],
                        Record["progress"], Record["progress_updated_at"] - Record["started_at"])
        except (EOFError, OSError):
            pass
        finally:
            ReceiveConnection.close()
            Process.join(timeout=2.0)

        #MARK: worker stuffs
        with self.Lock:
            Record = self.Jobs.get(JobId)
            if Record is None:
                return
            if Record["status"] in {"cancelled", "cancelling"}:
                Record["status"] = "cancelled"
                Record["stage"] = "cancelled"
                Record["stage_label"] = "Cancelled"
            elif Message and Message.get("status") == "completed":
                Record["status"] = "completed"
                Record["result"] = Message.get("result")
                Record["stage"] = "completed"
                Record["stage_label"] = "Complete"
            else:
                Record["status"] = "failed"
                Record["error"] = (
                    Message.get("error")
                    if Message
                    else f"Analysis worker exited unexpectedly (exit code {Process.exitcode})."
                )
                Record["stage"] = "failed"
                Record["stage_label"] = "Analysis failed"
            Record["finished_at"] = Record.get("finished_at") or Time.time()
            Telemetry = Record.get("telemetry")
            if Telemetry is not None:
                Record["execution"] = Telemetry.finish(Record["stage"], Record["stage_label"],
                    Record["finished_at"] - Record["started_at"],
                    Record["started_at"] - Record["submitted_at"])
                if isinstance(Record.get("result"), dict):
                    Record["result"]["execution"] = Record["execution"]
                Record["telemetry"] = None
            Record["process"] = None
            Record["connection"] = None
            self._DropInputsLocked(Record)
            self._ScheduleLocked()

    #MARK: worker stuffs
    def _PublicRecordLocked(self, Record, IncludeResult=True):
        Now = Time.time()
        Start = Record.get("started_at") or Record["submitted_at"]
        End = Record.get("finished_at") or Now
        QueuedBefore = 0
        if Record["status"] == "queued":
            for Item in self.Jobs.values():
                if Item is Record:
                    break
                if Item["status"] == "queued":
                    QueuedBefore += 1
        Payload = {
            "job_id": Record["job_id"],
            "status": Record["status"],
            "source_file": Record.get("source_file"),
            "submitted_at": Record["submitted_at"],
            "started_at": Record.get("started_at"),
            "finished_at": Record.get("finished_at"),
            "elapsed_seconds": max(0.0, End - Start) if Record.get("started_at") else 0.0,
            "queue_position": QueuedBefore + 1 if Record["status"] == "queued" else None,
            "stage": Record.get("stage"),
            "stage_label": Record.get("stage_label"),
            "batch_id": Record.get("batch_id"),
            "request_id": Record.get("request_id"),
            "queue_wait_seconds": max(0.0, (Record.get("started_at") or End) - Record["submitted_at"]),
            "progress_updated_at": Record.get("progress_updated_at"),
        }
        if Record["status"] == "running":
            Payload.update(Record.get("progress") or {})
            if not Payload.get("eta_state"):
                Payload["eta_state"] = "available" if Payload.get("estimated_remaining_seconds") is not None else "estimating"
            # stop showing an old eta if the worker has stopped reporting progress.
            if Record.get("progress_updated_at") and Now - Record["progress_updated_at"] > 45:
                Payload.update({Key: None for Key in ("estimated_remaining_seconds", "eta_lower_seconds", "eta_upper_seconds", "remaining_seconds_range")})
                Payload["eta_state"] = "estimating"
        else:
            # finished or queued work should not keep a live search eta.
            Payload.update({Key: None for Key in PROGRESS_FIELDS})
        if Record["status"] == "failed":
            Payload["error"] = Record.get("error") or "Analysis failed."
        if Record.get("execution") is not None:
            Payload["execution"] = Record["execution"]
        if IncludeResult and Record["status"] == "completed":
            Payload["result"] = Record.get("result")
        return Payload

    #MARK: cancel runs
    def _MarkCancelledLocked(self, Record):
        Record.update(status="cancelled", finished_at=Time.time(),
                      stage="cancelled", stage_label="Cancelled")
        self._DropInputsLocked(Record)

    def _DropInputsLocked(self, Record):
        Record["time_values"] = None
        Record["flux_values"] = None
        Record["options"] = None

    def _CleanupLocked(self, Now):
        Expired = [
            JobId
            for JobId, Record in self.Jobs.items()
            if Record["status"] in TERMINAL_STATES
            and Record.get("finished_at") is not None
            and Now - Record["finished_at"] > self.RetentionSeconds
        ]
        for JobId in Expired:
            del self.Jobs[JobId]

    #MARK: worker stuffs
    @staticmethod
    def _TerminateProcess(Process):
        if Process is None or not Process.is_alive():
            return
        TerminatedGroup = False
        if hasattr(Os, "getpgid") and hasattr(Os, "killpg"):
            try:
                ProcessGroup = Os.getpgid(Process.pid)
                if ProcessGroup == Process.pid:
                    Os.killpg(ProcessGroup, Signal.SIGTERM)
                    TerminatedGroup = True
            except (OSError, ProcessLookupError):
                pass
        if not TerminatedGroup:
            try:
                Process.terminate()
            except (OSError, ProcessLookupError):
                pass
        Process.join(timeout=2.0)
        # escalate only if the normal termination request did not finish it.
        if Process.is_alive():
            try:
                Process.kill()
            except (AttributeError, OSError, ProcessLookupError):
                Process.terminate()
            Process.join(timeout=1.0)


#MARK: old calls
# keep the old entry point for scripts written before the naming change.
def annotate_analysis_result(result, options=None, source_file=None):
    return AnnotateAnalysisResult(result, options, SourceFile=source_file)
