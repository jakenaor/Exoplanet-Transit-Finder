"""Background process management for long-running light-curve analyses."""

import multiprocessing
import os
import signal
import threading
import time
import uuid

from analysis import analyze


TERMINAL_STATES = {"completed", "failed", "cancelled"}


def _analysis_worker(send_connection, time_values, flux_values, options, runner):
    """Run one analysis in an isolated process and return one terminal message."""
    try:
        if hasattr(os, "setsid"):
            try:
                os.setsid()
            except OSError:
                pass
        result = runner(time_values, flux_values, options)
        message = {"status": "completed", "result": result}
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
        }
        with self.lock:
            if self.closed:
                raise RuntimeError("Analysis job manager is shutting down.")
            self._cleanup_locked(now)
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
                self._drop_inputs_locked(record)
                self._schedule_locked()
                return self._public_record_locked(record)
            record["status"] = "cancelling"
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
            ),
            name=f"transit-analysis-{record['job_id'][:8]}",
        )
        process.daemon = False
        record["status"] = "running"
        record["started_at"] = time.time()
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
            message = receive_connection.recv()
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
            elif message and message.get("status") == "completed":
                record["status"] = "completed"
                record["result"] = message.get("result")
            else:
                record["status"] = "failed"
                record["error"] = (
                    message.get("error")
                    if message
                    else f"Analysis worker exited unexpectedly (exit code {process.exitcode})."
                )
            record["finished_at"] = record.get("finished_at") or time.time()
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
            "elapsed_seconds": max(0.0, end - start),
            "queue_position": queued_before + 1 if record["status"] == "queued" else None,
        }
        if record["status"] == "failed":
            payload["error"] = record.get("error") or "Analysis failed."
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
