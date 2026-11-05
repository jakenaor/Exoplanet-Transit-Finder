"""Background process management for long-running light-curve analyses."""

import inspect
from datetime import datetime, timezone
from importlib import metadata as package_metadata
import json
import hashlib
import math
import multiprocessing
import os
import signal
import statistics
import sys
import threading
import time
import uuid

import numpy as np

from analysis import analyze


TERMINAL_STATES = {"completed", "failed", "cancelled"}
RESULT_SCHEMA_VERSION = 2
ANALYSIS_VERSION = "2026.11.05.2"
APP_VERSION = "65"
PROGRESS_FIELDS = ("completed_trials", "total_trials", "estimated_remaining_seconds",
                   "eta_lower_seconds", "eta_upper_seconds", "eta_scope", "work_completed",
                   "work_total", "remaining_seconds_range", "eta_state", "search_elapsed_seconds",
                   "throughput_elapsed_seconds", "search_complete", "eta_method",
                   "eta_sample_seconds", "eta_variation")


class ExecutionTelemetry:
    """Bounded evidence for auditing a completed job without retaining its inputs."""

    def __init__(self, history_limit=256):
        self.history_limit = max(8, int(history_limit))
        self.history = []
        self.sample_interval = 5.0
        self.sampled = False
        self.stages = []
        self.searches = []
        self.current_stage = None
        self.last_search_elapsed = None

    def update(self, stage, label, details, elapsed):
        elapsed = max(0.0, float(elapsed))
        changed = self.current_stage is None or stage != self.current_stage["stage"]
        if changed:
            self._close_stage(elapsed)
            self.current_stage = {"stage": str(stage), "stage_label": str(label),
                                  "started_elapsed_seconds": elapsed}
        progress = cleaned_progress_details(details)
        search_id = None
        if progress.get("total_trials") is not None and progress.get("completed_trials") is not None:
            search_elapsed = progress.get("search_elapsed_seconds")
            new_search = (not self.searches or self.searches[-1].get("finished_elapsed_seconds") is not None
                          or (search_elapsed is not None and self.last_search_elapsed is not None
                              and search_elapsed < self.last_search_elapsed))
            # A repeated final notification must not create an empty search.
            if new_search and not progress.get("search_complete"):
                self.searches.append({"search_id": len(self.searches) + 1,
                    "started_elapsed_seconds": max(0.0, elapsed - (search_elapsed or 0.0)),
                    "total_trials": progress["total_trials"]})
            if self.searches:
                search = self.searches[-1]
                search_id = search["search_id"]
                search["completed_trials"] = progress["completed_trials"]
                if progress.get("search_complete"):
                    search["finished_elapsed_seconds"] = elapsed
                    search["duration_seconds"] = max(0.0, elapsed - search["started_elapsed_seconds"])
            self.last_search_elapsed = search_elapsed
        snapshot = {"elapsed_seconds": elapsed, "stage": str(stage), **progress}
        if search_id is not None:
            snapshot["search_id"] = search_id
        previous = self.history[-1] if self.history else {}
        eta_changed = progress.get("eta_state") != previous.get("eta_state")
        if (not self.history or changed or eta_changed or progress.get("search_complete")
                or elapsed - previous.get("elapsed_seconds", 0.0) >= self.sample_interval):
            self.history.append(snapshot)
            if len(self.history) > self.history_limit:
                # Preserve first/latest samples and thin older observations.
                latest = self.history[-1]
                self.history = self.history[::2]
                if self.history[-1] is not latest:
                    self.history.append(latest)
                self.sample_interval *= 2.0
                self.sampled = True

    def _close_stage(self, elapsed):
        if self.current_stage is not None:
            stage = {**self.current_stage, "finished_elapsed_seconds": elapsed,
                     "duration_seconds": max(0.0, elapsed - self.current_stage["started_elapsed_seconds"])}
            self.stages.append(stage)
            self.stages = self.stages[-64:]
            self.current_stage = None

    def finish(self, stage, label, elapsed, queue_wait=0.0):
        self.update(stage, label, {}, elapsed)
        self._close_stage(elapsed)
        searches = {search["search_id"]: search for search in self.searches}
        history = [dict(snapshot) for snapshot in self.history]
        errors, coverage = [], []
        for snapshot in history:
            forecast = snapshot.get("estimated_remaining_seconds")
            search_end = searches.get(snapshot.get("search_id"), {}).get("finished_elapsed_seconds")
            if forecast is None or search_end is None:
                continue
            actual = max(0.0, search_end - snapshot["elapsed_seconds"])
            error = forecast - actual
            snapshot.update({"actual_remaining_seconds": actual, "eta_error_seconds": error})
            errors.append(abs(error))
            low, high = snapshot.get("eta_lower_seconds"), snapshot.get("eta_upper_seconds")
            if low is not None and high is not None:
                covered = low <= actual <= high
                snapshot["range_contains_actual"] = covered
                coverage.append(covered)
        return {"schema_version": 1, "elapsed_seconds": max(0.0, float(elapsed)),
                "queue_wait_seconds": max(0.0, float(queue_wait)), "stage_durations": self.stages,
                "searches": self.searches, "progress_history": history,
                "progress_history_limit": self.history_limit,
                "progress_history_sampled": self.sampled,
                "eta_audit": {"scope": "search", "retained_forecasts_audited": len(errors),
                    "mean_absolute_error_seconds": statistics.mean(errors) if errors else None,
                    "median_absolute_error_seconds": statistics.median(errors) if errors else None,
                    "ranges_audited": len(coverage),
                    "observed_range_coverage_fraction": statistics.mean(coverage) if coverage else None,
                    "note": "Audit uses retained forecasts only; observed throughput ranges are not confidence intervals."}}


def annotate_analysis_result(result, options=None, source_file=None):
    """Stamp analysis provenance once; cache saves must never refresh this date."""
    if not isinstance(result, dict):
        raise ValueError("The analysis worker did not return a result object.")
    options = options or {}
    previous_provenance = result.get("provenance") if isinstance(result.get("provenance"), dict) else {}
    source_file = (source_file or (options.get("_input_metadata") or {}).get("source_file")
                   or result.get("source_file") or previous_provenance.get("source_file"))
    dependencies = {}
    for name in ("numpy", "scipy", "astropy", "transitleastsquares", "batman-package", "numba"):
        try:
            dependencies[name] = package_metadata.version(name)
        except package_metadata.PackageNotFoundError:
            dependencies[name] = "unavailable"
    analyzed_at = datetime.now(timezone.utc).isoformat()
    effective = result.get("effective_settings") or {k: v for k, v in options.items() if not k.startswith("_")}
    result["result_schema_version"] = RESULT_SCHEMA_VERSION
    result["analyzed_at"] = analyzed_at
    result["provenance"] = {"app_version": APP_VERSION, "analysis_version": ANALYSIS_VERSION,
        "result_schema_version": RESULT_SCHEMA_VERSION, "analyzed_at": analyzed_at,
        "dependency_versions": dependencies, "python_version": sys.version.split()[0], "effective_settings": effective,
        "source_file": source_file, "legacy": False}
    if options.get("_input_metadata") is not None:
        result.setdefault("input_metadata", options["_input_metadata"])
    if options.get("_cleaning_report") is not None:
        result.setdefault("cleaning", options["_cleaning_report"])
    for signal_result in result.get("signals", []):
        if isinstance(signal_result, dict):
            signal_analyzed_at = signal_result.get("analyzed_at") or analyzed_at
            signal_result["result_schema_version"] = RESULT_SCHEMA_VERSION
            signal_result["analyzed_at"] = signal_analyzed_at
            signal_result["provenance"] = {**result["provenance"],
                "analyzed_at": signal_analyzed_at,
                "effective_settings": signal_result.get("effective_settings") or effective}
            if result.get("input_metadata") is not None:
                signal_result.setdefault("input_metadata", result["input_metadata"])
            if signal_result.get("cleaning_report") is not None:
                signal_result.setdefault("cleaning", signal_result["cleaning_report"])
            elif result.get("cleaning") is not None:
                signal_result.setdefault("cleaning", result["cleaning"])
    # Fail the job explicitly rather than send NaN/Infinity that browser JSON
    # parsers reject, or discover an unsupported scalar only while polling.
    try:
        json.dumps(result, allow_nan=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Analysis returned nonfinite or unsupported result values; no invalid JSON result was saved.") from exc
    return result


def cleaned_progress_details(details):
    """Only carry finite, bounded progress values across the worker boundary."""
    output = {}
    for key in PROGRESS_FIELDS:
        value = details.get(key)
        if key == "search_complete":
            if isinstance(value, bool):
                output[key] = value
        elif key in {"eta_scope", "eta_state", "eta_method"}:
            if isinstance(value, str):
                output[key] = value[:40]
        elif key == "remaining_seconds_range":
            if isinstance(value, (list, tuple)) and len(value) == 2:
                numbers = [float(v) for v in value if isinstance(v, (int, float)) and math.isfinite(v) and v >= 0]
                if len(numbers) == 2:
                    output[key] = sorted(numbers)
        elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0:
            output[key] = value
        elif value is None:
            output[key] = None
    return output


def _analysis_worker(send_connection, time_values, flux_values, options, runner, source_file=None):
    """Run one analysis in an isolated process and return one terminal message."""
    def publish_progress(stage, stage_label, details=None, **extra):
        try:
            send_connection.send({
                "status": "progress",
                "stage": str(stage),
                "stage_label": str(stage_label),
                **cleaned_progress_details({**(details or {}), **extra}),
            })
        except (BrokenPipeError, EOFError, OSError):
            pass

    try:
        if hasattr(os, "setsid"):
            try:
                os.setsid()
            except OSError:
                pass
        try:
            parameters = inspect.signature(runner).parameters.values()
            supports_progress = any(
                parameter.name == "progress_callback"
                or parameter.kind == inspect.Parameter.VAR_KEYWORD
                for parameter in parameters
            )
        except (TypeError, ValueError):
            supports_progress = False
        if supports_progress:
            result = runner(
                time_values,
                flux_values,
                options,
                progress_callback=publish_progress,
            )
        else:
            result = runner(time_values, flux_values, options)
        message = {"status": "completed", "result": annotate_analysis_result(result, options, source_file)}
    except BaseException as exc:  # The parent must hear about worker-level failures.
        message = {"status": "failed", "error": str(exc) or exc.__class__.__name__}

    try:
        send_connection.send(message)
    except (BrokenPipeError, EOFError, OSError):
        pass
    finally:
        send_connection.close()


class AnalysisJobManager:
    """Queue analyses, isolate them from HTTP requests, and support cancellation."""

    def __init__(
        self,
        max_running=1,
        retention_seconds=3600,
        start_method="spawn",
        runner=analyze,
    ):
        self.max_running = max(1, int(max_running))
        self.retention_seconds = max(60, int(retention_seconds))
        self.context = multiprocessing.get_context(start_method)
        self.runner = runner
        self.jobs = {}
        self.lock = threading.RLock()
        self.closed = False

    def submit(self, time_values, flux_values, options, source_file=None):
        job_id = uuid.uuid4().hex
        now = time.time()
        record = {
            "job_id": job_id,
            "status": "queued",
            "source_file": source_file,
            "submitted_at": now,
            "started_at": None,
            "finished_at": None,
            "time_values": time_values,
            "flux_values": flux_values,
            "options": options,
            "process": None,
            "connection": None,
            "result": None,
            "error": None,
            "stage": "queued",
            "stage_label": "Waiting for analysis worker",
            "batch_id": options.get("_batch_id"),
            "request_id": options.get("_request_id"),
            "progress": {},
            "telemetry": None,
            "execution": None,
        }
        with self.lock:
            if self.closed:
                raise RuntimeError("Analysis job manager is shutting down.")
            self._cleanup_locked(now)
            if record["request_id"]:
                digest = hashlib.sha256(json.dumps({
                    "source_file": source_file, "settings": options,
                }, sort_keys=True, default=str).encode())
                digest.update(np.asarray(time_values, dtype=float).tobytes())
                digest.update(np.asarray(flux_values, dtype=float).tobytes())
                fingerprint = digest.hexdigest()
                record["request_fingerprint"] = fingerprint
                for existing in self.jobs.values():
                    if existing.get("request_id") == record["request_id"]:
                        if existing.get("request_fingerprint") != fingerprint:
                            raise ValueError("This submission ID was already used for different analysis inputs.")
                        return self._public_record_locked(existing, include_result=True)
            self.jobs[job_id] = record
            self._schedule_locked()
            return self._public_record_locked(record, include_result=False)

    def get(self, job_id, include_result=True):
        with self.lock:
            self._cleanup_locked(time.time())
            record = self.jobs.get(job_id)
            if record is None:
                return None
            return self._public_record_locked(record, include_result=include_result)

    def find_by_request_id(self, request_id, include_result=True):
        """Reconnect after an accepted submission whose response was lost."""
        if not isinstance(request_id, str) or not request_id or len(request_id) > 160:
            return None
        with self.lock:
            self._cleanup_locked(time.time())
            for record in self.jobs.values():
                if record.get("request_id") == request_id:
                    return self._public_record_locked(record, include_result=include_result)
        return None

    def cancel(self, job_id):
        process = None
        with self.lock:
            record = self.jobs.get(job_id)
            if record is None:
                return None
            if record["status"] in TERMINAL_STATES:
                return self._public_record_locked(record)
            if record["status"] == "queued":
                record["status"] = "cancelled"
                record["finished_at"] = time.time()
                record["stage"] = "cancelled"
                record["stage_label"] = "Cancelled"
                self._drop_inputs_locked(record)
                self._schedule_locked()
                return self._public_record_locked(record)
            record["status"] = "cancelling"
            record["stage"] = "cancelling"
            record["stage_label"] = "Cancelling analysis"
            process = record.get("process")

        self._terminate_process(process)

        with self.lock:
            record = self.jobs.get(job_id)
            if record is None:
                return None
            if record["status"] not in TERMINAL_STATES:
                record["status"] = "cancelled"
                record["finished_at"] = time.time()
                record["error"] = None
                record["result"] = None
                record["stage"] = "cancelled"
                record["stage_label"] = "Cancelled"
                self._drop_inputs_locked(record)
            self._schedule_locked()
            return self._public_record_locked(record)

    def shutdown(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            active = [
                record.get("process")
                for record in self.jobs.values()
                if record["status"] in {"running", "cancelling"}
            ]
            for record in self.jobs.values():
                if record["status"] == "queued":
                    record["status"] = "cancelled"
                    record["finished_at"] = time.time()
                    record["stage"] = "cancelled"
                    record["stage_label"] = "Cancelled"
                    self._drop_inputs_locked(record)

        for process in active:
            self._terminate_process(process)

    def _running_count_locked(self):
        return sum(
            record["status"] in {"running", "cancelling"}
            for record in self.jobs.values()
        )

    def _schedule_locked(self):
        if self.closed:
            return
        while self._running_count_locked() < self.max_running:
            queued = next(
                (record for record in self.jobs.values() if record["status"] == "queued"),
                None,
            )
            if queued is None:
                return
            self._launch_locked(queued)

    def _launch_locked(self, record):
        receive_connection, send_connection = self.context.Pipe(duplex=False)
        process = self.context.Process(
            target=_analysis_worker,
            args=(
                send_connection,
                record["time_values"],
                record["flux_values"],
                record["options"],
                self.runner,
                record.get("source_file"),
            ),
            name=f"transit-analysis-{record['job_id'][:8]}",
        )
        process.daemon = False
        record["status"] = "running"
        record["started_at"] = time.time()
        record["telemetry"] = ExecutionTelemetry()
        record["telemetry"].update("starting", "Starting analysis", {}, 0.0)
        record["stage"] = "starting"
        record["stage_label"] = "Starting analysis"
        record["process"] = process
        record["connection"] = receive_connection
        try:
            process.start()
        except Exception as exc:
            receive_connection.close()
            send_connection.close()
            record["status"] = "failed"
            record["error"] = f"Could not start analysis worker: {exc}"
            record["finished_at"] = time.time()
            record["stage"] = "failed"
            record["stage_label"] = "Analysis failed"
            self._drop_inputs_locked(record)
            return
        send_connection.close()
        monitor = threading.Thread(
            target=self._monitor,
            args=(record["job_id"], process, receive_connection),
            daemon=True,
            name=f"analysis-monitor-{record['job_id'][:8]}",
        )
        monitor.start()

    def _monitor(self, job_id, process, receive_connection):
        message = None
        try:
            while True:
                incoming = receive_connection.recv()
                if incoming.get("status") != "progress":
                    message = incoming
                    break
                with self.lock:
                    record = self.jobs.get(job_id)
                    if record is None or record["status"] != "running":
                        continue
                    record["stage"] = incoming.get("stage") or record.get("stage")
                    record["stage_label"] = (
                        incoming.get("stage_label")
                        or record.get("stage_label")
                    )
                    record["progress"] = cleaned_progress_details(incoming)
                    record["progress_updated_at"] = time.time()
                    record["telemetry"].update(record["stage"], record["stage_label"],
                        record["progress"], record["progress_updated_at"] - record["started_at"])
        except (EOFError, OSError):
            pass
        finally:
            receive_connection.close()
            process.join(timeout=2.0)

        with self.lock:
            record = self.jobs.get(job_id)
            if record is None:
                return
            if record["status"] in {"cancelled", "cancelling"}:
                record["status"] = "cancelled"
                record["stage"] = "cancelled"
                record["stage_label"] = "Cancelled"
            elif message and message.get("status") == "completed":
                record["status"] = "completed"
                record["result"] = message.get("result")
                record["stage"] = "completed"
                record["stage_label"] = "Complete"
            else:
                record["status"] = "failed"
                record["error"] = (
                    message.get("error")
                    if message
                    else f"Analysis worker exited unexpectedly (exit code {process.exitcode})."
                )
                record["stage"] = "failed"
                record["stage_label"] = "Analysis failed"
            record["finished_at"] = record.get("finished_at") or time.time()
            telemetry = record.get("telemetry")
            if telemetry is not None:
                record["execution"] = telemetry.finish(record["stage"], record["stage_label"],
                    record["finished_at"] - record["started_at"],
                    record["started_at"] - record["submitted_at"])
                if isinstance(record.get("result"), dict):
                    record["result"]["execution"] = record["execution"]
                record["telemetry"] = None
            record["process"] = None
            record["connection"] = None
            self._drop_inputs_locked(record)
            self._schedule_locked()

    def _public_record_locked(self, record, include_result=True):
        now = time.time()
        start = record.get("started_at") or record["submitted_at"]
        end = record.get("finished_at") or now
        queued_before = 0
        if record["status"] == "queued":
            for item in self.jobs.values():
                if item is record:
                    break
                if item["status"] == "queued":
                    queued_before += 1
        payload = {
            "job_id": record["job_id"],
            "status": record["status"],
            "source_file": record.get("source_file"),
            "submitted_at": record["submitted_at"],
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "elapsed_seconds": max(0.0, end - start) if record.get("started_at") else 0.0,
            "queue_position": queued_before + 1 if record["status"] == "queued" else None,
            "stage": record.get("stage"),
            "stage_label": record.get("stage_label"),
            "batch_id": record.get("batch_id"),
            "request_id": record.get("request_id"),
            "queue_wait_seconds": max(0.0, (record.get("started_at") or end) - record["submitted_at"]),
            "progress_updated_at": record.get("progress_updated_at"),
        }
        if record["status"] == "running":
            payload.update(record.get("progress") or {})
            if not payload.get("eta_state"):
                payload["eta_state"] = "available" if payload.get("estimated_remaining_seconds") is not None else "estimating"
            # An estimate based on old throughput is withdrawn after progress stalls.
            if record.get("progress_updated_at") and now - record["progress_updated_at"] > 45:
                payload.update({key: None for key in ("estimated_remaining_seconds", "eta_lower_seconds", "eta_upper_seconds", "remaining_seconds_range")})
                payload["eta_state"] = "estimating"
        else:
            payload.update({key: None for key in PROGRESS_FIELDS})
        if record["status"] == "failed":
            payload["error"] = record.get("error") or "Analysis failed."
        if record.get("execution") is not None:
            payload["execution"] = record["execution"]
        if include_result and record["status"] == "completed":
            payload["result"] = record.get("result")
        return payload

    def _drop_inputs_locked(self, record):
        record["time_values"] = None
        record["flux_values"] = None
        record["options"] = None

    def _cleanup_locked(self, now):
        expired = [
            job_id
            for job_id, record in self.jobs.items()
            if record["status"] in TERMINAL_STATES
            and record.get("finished_at") is not None
            and now - record["finished_at"] > self.retention_seconds
        ]
        for job_id in expired:
            del self.jobs[job_id]

    @staticmethod
    def _terminate_process(process):
        if process is None or not process.is_alive():
            return
        terminated_group = False
        if hasattr(os, "getpgid") and hasattr(os, "killpg"):
            try:
                process_group = os.getpgid(process.pid)
                if process_group == process.pid:
                    os.killpg(process_group, signal.SIGTERM)
                    terminated_group = True
            except (OSError, ProcessLookupError):
                pass
        if not terminated_group:
            try:
                process.terminate()
            except (OSError, ProcessLookupError):
                pass
        process.join(timeout=2.0)
        if process.is_alive():
            try:
                process.kill()
            except (AttributeError, OSError, ProcessLookupError):
                process.terminate()
            process.join(timeout=1.0)
