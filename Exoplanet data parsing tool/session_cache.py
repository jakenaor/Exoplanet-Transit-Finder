"""Disk-backed browser session caches for completed transit analyses."""

from datetime import datetime, timezone
import copy
import json
import math
import os
from pathlib import Path
import re
import threading
import uuid


SESSION_SCHEMA_VERSION = 1
SESSION_CACHE_DIR_ENV = "TRANSIT_FINDER_SESSION_CACHE_DIR"
SESSION_CACHE_DIR_NAME = "Exoplanet Transit Finder Sessions"
DEFAULT_MAX_SESSION_BYTES = 250 * 1024 * 1024
SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,80}$")
SESSION_FILENAME_PATTERN = re.compile(r"^session-([a-zA-Z0-9_-]{8,80})\.json$")
CURRENT_RESULT_SCHEMA_VERSION = 2


def _finite_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _reject_nonfinite_json(value):
    raise ValueError(f"Nonfinite JSON value: {value}")


def _validate_array_group(section, keys, label, allow_null=False):
    values = [section.get(key) for key in keys]
    if not any(value is not None for value in values):
        return
    if any(not isinstance(value, list) for value in values) or len({len(value) for value in values}) != 1:
        raise ValueError(f"The saved result has mismatched {label} arrays. The original cache is unchanged.")
    if any(not _finite_number(value) and not (allow_null and value is None) for array in values for value in array):
        raise ValueError(f"The saved result has invalid {label} values. The original cache is unchanged.")


def validate_result(result, file_name="saved file"):
    """Validate the arrays the renderer needs, preserving supported legacy data."""
    if not isinstance(result, dict):
        raise ValueError(f"The saved result for {file_name} is not a result object.")
    version = result.get("result_schema_version", 1)
    if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= CURRENT_RESULT_SCHEMA_VERSION:
        raise ValueError(f"The saved result for {file_name} uses an unsupported result schema. The original cache is unchanged.")
    provenance = result.get("provenance")
    if provenance is not None:
        if not isinstance(provenance, dict):
            raise ValueError(f"The saved result for {file_name} has invalid provenance metadata.")
        provenance_version = provenance.get("result_schema_version", version)
        if not isinstance(provenance_version, int) or isinstance(provenance_version, bool) or provenance_version != version:
            raise ValueError(f"The saved result for {file_name} has inconsistent provenance/result schemas.")
        for key in ("analysis_version", "app_version"):
            if key in provenance and not isinstance(provenance[key], str):
                raise ValueError(f"The saved result for {file_name} has invalid {key} metadata.")
        for key in ("dependency_versions", "effective_settings"):
            if key in provenance and not isinstance(provenance[key], dict):
                raise ValueError(f"The saved result for {file_name} has invalid {key} metadata.")
        if result.get("analyzed_at") and provenance.get("analyzed_at") and result["analyzed_at"] != provenance["analyzed_at"]:
            raise ValueError(f"The saved result for {file_name} has inconsistent analysis timestamps.")
    for analyzed_at in (result.get("analyzed_at"), (provenance or {}).get("analyzed_at")):
        if analyzed_at is not None:
            if not isinstance(analyzed_at, str):
                raise ValueError(f"The saved result for {file_name} has an invalid analysis timestamp.")
            try:
                parsed_at = datetime.fromisoformat(analyzed_at.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"The saved result for {file_name} has an invalid analysis timestamp.") from exc
            if parsed_at.tzinfo is None:
                raise ValueError(f"The saved result for {file_name} has an analysis timestamp without a time zone.")
    plot = result.get("plot")
    if not isinstance(plot, dict):
        raise ValueError(f"The saved result for {file_name} has no usable plot arrays. The original cache is unchanged.")
    arrays = [plot.get(key) for key in ("time", "raw_flux", "smooth_flux")]
    if any(not isinstance(a, list) or not a for a in arrays) or len({len(a) for a in arrays}) != 1:
        raise ValueError(f"The saved result for {file_name} has mismatched plot arrays. The original cache is unchanged.")
    if any(not _finite_number(v) for a in arrays for v in a):
        raise ValueError(f"The saved result for {file_name} contains nonfinite plot values. The original cache is unchanged.")
    if any(right < left for left, right in zip(arrays[0], arrays[0][1:])):
        raise ValueError(f"The saved result for {file_name} has unsorted plot times.")
    period = result.get("period")
    if period is not None and (not _finite_number(period) or period <= 0):
        raise ValueError(f"The saved result for {file_name} has an invalid period.")
    transits = result.get("transits", [])
    if not isinstance(transits, list):
        raise ValueError(f"The saved result for {file_name} has invalid transit windows.")
    for transit in transits:
        if (not isinstance(transit, dict)
            or not all(_finite_number(transit.get(key)) for key in ("start", "end"))
            or transit["end"] < transit["start"]
            or (transit.get("center") is not None and not _finite_number(transit["center"]))):
            raise ValueError(f"The saved result for {file_name} has an invalid transit window.")
    for name, keys in (("phase_folded", ("phase", "raw_flux", "smooth_flux")),
                       ("transit_model", ("time", "flux"))):
        section = result.get(name)
        if section is None:
            continue
        if not isinstance(section, dict):
            raise ValueError(f"The saved result for {file_name} has invalid {name} data.")
        values = [section.get(key) for key in keys]
        if any(value is not None for value in values):
            if any(not isinstance(value, list) for value in values) or len({len(value) for value in values}) != 1:
                raise ValueError(f"The saved result for {file_name} has mismatched {name} arrays.")
            if any(not _finite_number(v) for a in values for v in a):
                raise ValueError(f"The saved result for {file_name} has nonfinite {name} values.")
    phase = result.get("phase_folded") or {}
    _validate_array_group(phase, ("binned_phase", "binned_flux"), "binned phase")
    _validate_array_group(result.get("transit_model") or {}, ("folded_phase_days", "folded_flux"), "folded model")
    comparison = result.get("model_comparison")
    if comparison is not None:
        if not isinstance(comparison, dict):
            raise ValueError("The saved result has invalid model comparison data.")
        _validate_array_group(comparison, ("time", "search_flux", "model_flux", "residual_flux"), "model comparison")
    stack = result.get("transit_stack")
    if stack is not None:
        if not isinstance(stack, dict) or not isinstance(stack.get("traces", []), list):
            raise ValueError("The saved result has invalid transit stack data.")
        _validate_array_group(stack, ("median_phase_days", "median_flux"), "transit stack median")
        for trace in stack.get("traces", []):
            if not isinstance(trace, dict):
                raise ValueError("The saved result has an invalid transit stack trace.")
            _validate_array_group(trace, ("phase_days", "flux"), "transit stack trace")
    errors = plot.get("flux_uncertainty")
    if errors is not None and (not isinstance(errors, list) or len(errors) != len(arrays[0])
            or any(value is not None and (not _finite_number(value) or value <= 0) for value in errors)):
        raise ValueError("The saved result has invalid flux uncertainty samples.")
    return result


def validated_session_state(state):
    if not isinstance(state, dict):
        raise ValueError("Analysis session state must be a JSON object.")
    results = state.get("results", [])
    if not isinstance(results, list) or len(results) > 100:
        raise ValueError("Analysis session results must contain at most 100 files.")
    ui_version = state.get("ui_schema_version", 1)
    if not isinstance(ui_version, int) or isinstance(ui_version, bool) or not 1 <= ui_version <= 2:
        raise ValueError("This saved session uses an unsupported interface schema. The original cache is unchanged.")
    # Work on a copy: viewing or saving cannot alter the caller's analysis date.
    state = copy.deepcopy(state)
    notices = []
    for item in state.get("results", []):
        if not isinstance(item, dict):
            raise ValueError("A saved file entry is not an object.")
        result = item.get("result")
        if result is None:
            continue
        validate_result(result, str(item.get("file_name") or "saved file"))
        provenance = result.get("provenance")
        if not isinstance(provenance, dict) or not provenance.get("analysis_version"):
            result.setdefault("result_schema_version", 1)
            result.setdefault("analyzed_at", None)
            result["provenance"] = {"analysis_version": "unknown", "app_version": "unknown",
                "result_schema_version": result["result_schema_version"],
                "analyzed_at": result["analyzed_at"], "dependency_versions": {},
                "legacy": True, "compatibility_notice": "Legacy result: analysis version unknown; retained without rescoring."}
            notices.append(str(item.get("file_name") or "saved file"))
        signals = result.get("signals")
        if signals is not None:
            if not isinstance(signals, list) or len(signals) > 10:
                raise ValueError("A saved result has invalid signal entries.")
            # The signal picker renders each entry as a full result.
            for signal in signals:
                if not isinstance(signal, dict):
                    raise ValueError("A saved signal is not an object.")
                validate_result(signal, str(item.get("file_name") or "saved signal"))
    active_job = state.get("active_job_id")
    if active_job is not None and (not isinstance(active_job, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,160}", active_job)):
        raise ValueError("The saved active job ID is invalid.")
    active_request = state.get("active_request_id")
    if active_request is not None and (not isinstance(active_request, str) or not re.fullmatch(r"[a-zA-Z0-9_.:-]{1,160}", active_request)):
        raise ValueError("The saved active submission ID is invalid.")
    if active_job or active_request:
        index = state.get("active_file_index")
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(results):
            raise ValueError("The saved active job has no matching file entry. The original cache is unchanged.")
    pending = state.get("pending_files", [])
    if not isinstance(pending, list) or len(pending) > 100 or any(not isinstance(item, dict) for item in pending):
        raise ValueError("The saved session has invalid pending file entries.")
    if notices:
        state["cache_compatibility"] = {"legacy_results": notices,
            "notice": "Legacy results retain their saved measurements and assessment. Analysis version unknown."}
    return state


def default_session_cache_directory():
    configured = os.environ.get(SESSION_CACHE_DIR_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return (Path.home() / "Desktop" / SESSION_CACHE_DIR_NAME).resolve()


def validate_session_id(session_id):
    value = str(session_id or "")
    if not SESSION_ID_PATTERN.fullmatch(value):
        raise ValueError("Invalid analysis session ID.")
    return value


class SessionCache:
    """Store one atomic JSON document per browser session."""

    def __init__(self, directory=None, max_bytes=DEFAULT_MAX_SESSION_BYTES):
        self.directory = Path(directory or default_session_cache_directory()).expanduser().resolve()
        self.max_bytes = max(1024, int(max_bytes))

    def path_for(self, session_id):
        session_id = validate_session_id(session_id)
        return self.directory / f"session-{session_id}.json"

    def load(self, session_id):
        path = self.path_for(session_id)
        if not path.is_file():
            return None
        if path.stat().st_size > self.max_bytes:
            raise ValueError("The saved analysis session is too large to load safely.")
        try:
            with path.open("r", encoding="utf-8") as source:
                document = json.load(source, parse_constant=_reject_nonfinite_json)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError("The saved analysis session contains invalid JSON. The original cache is unchanged.") from exc
        if not isinstance(document, dict) or document.get("session_id") != session_id:
            raise ValueError("The saved analysis session is invalid.")
        version = document.get("schema_version", 1)
        if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= SESSION_SCHEMA_VERSION:
            raise ValueError("This saved session uses an unsupported cache schema. The original cache is unchanged.")
        document["state"] = validated_session_state(document.get("state"))
        return document

    def save(self, session_id, state):
        session_id = validate_session_id(session_id)
        state = validated_session_state(state)

        saved_at = datetime.now(timezone.utc).isoformat()
        document = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "session_id": session_id,
            "saved_at": saved_at,
            "state": state,
        }
        encoded = json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(encoded) > self.max_bytes:
            raise ValueError("The analysis session is too large to save.")

        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(session_id)
        temporary_path = self.directory / f".{path.name}.{uuid.uuid4().hex}.tmp"
        try:
            with temporary_path.open("wb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

        return {
            "session_id": session_id,
            "saved_at": saved_at,
            "cache_file": str(path),
            "size_bytes": len(encoded),
        }


class SessionCacheManager:
    """Resolve persistent per-session folders and safely relocate cache files."""

    def __init__(self, default_directory=None, max_bytes=DEFAULT_MAX_SESSION_BYTES):
        self.default_directory = Path(
            default_directory or default_session_cache_directory()
        ).expanduser().resolve()
        self.directory = self.default_directory
        self.max_bytes = max(1024, int(max_bytes))
        self.registry_path = self.default_directory / ".session-locations.json"
        self.lock = threading.RLock()

    def _read_registry_locked(self):
        if not self.registry_path.is_file():
            return {}
        if self.registry_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("The session location registry is too large.")
        with self.registry_path.open("r", encoding="utf-8") as source:
            payload = json.load(source)
        if not isinstance(payload, dict):
            raise ValueError("The session location registry is invalid.")
        return {
            session_id: directory
            for session_id, directory in payload.items()
            if SESSION_ID_PATTERN.fullmatch(str(session_id)) and isinstance(directory, str)
        }

    def _write_registry_locked(self, registry):
        self.default_directory.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(
            registry,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        temporary_path = self.default_directory / f".{self.registry_path.name}.{uuid.uuid4().hex}.tmp"
        try:
            with temporary_path.open("wb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, self.registry_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @staticmethod
    def validate_directory(directory):
        value = str(directory or "").strip()
        if not value:
            raise ValueError("Enter a save folder.")
        path = Path(value).expanduser()
        if not path.is_absolute():
            raise ValueError("Save location must be an absolute path or start with ~.")
        path = path.resolve()
        if path == Path(path.anchor):
            raise ValueError("Choose a folder instead of the filesystem root.")
        if path.exists() and not path.is_dir():
            raise ValueError("The save location points to a file, not a folder.")
        return path

    def directory_for(self, session_id):
        session_id = validate_session_id(session_id)
        with self.lock:
            registry = self._read_registry_locked()
            configured = registry.get(session_id)
            if not configured:
                return self.default_directory
            try:
                return self.validate_directory(configured)
            except ValueError:
                return self.default_directory

    def cache_for(self, session_id):
        return SessionCache(self.directory_for(session_id), self.max_bytes)

    def path_for(self, session_id):
        return self.cache_for(session_id).path_for(session_id)

    def load(self, session_id):
        with self.lock:
            return self.cache_for(session_id).load(session_id)

    def save(self, session_id, state):
        with self.lock:
            saved = self.cache_for(session_id).save(session_id, state)
            return {
                **saved,
                "cache_directory": str(Path(saved["cache_file"]).parent),
            }

    def list_sessions(self):
        """Return every known cache without loading its potentially large JSON state."""
        with self.lock:
            registry = self._read_registry_locked()
            cache_paths = {}

            if self.default_directory.is_dir():
                for path in self.default_directory.glob("session-*.json"):
                    match = SESSION_FILENAME_PATTERN.fullmatch(path.name)
                    if match and path.is_file():
                        cache_paths[match.group(1)] = path

            # A registered custom location is authoritative for its session, even
            # if a stale copy still exists in the default directory.
            for session_id, directory in registry.items():
                try:
                    custom_directory = self.validate_directory(directory)
                    custom_path = SessionCache(custom_directory, self.max_bytes).path_for(session_id)
                except ValueError:
                    continue
                if custom_path.is_file():
                    cache_paths[session_id] = custom_path

            sessions = []
            for session_id, path in cache_paths.items():
                try:
                    stat = path.stat()
                except OSError:
                    continue
                sessions.append({
                    "session_id": session_id,
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime,
                        timezone.utc,
                    ).isoformat(),
                    "size_bytes": stat.st_size,
                    "cache_directory": str(path.parent),
                    "cache_file": str(path),
                    "loadable": stat.st_size <= self.max_bytes,
                })

            sessions.sort(key=lambda item: item["modified_at"], reverse=True)
            return sessions

    def relocate(self, session_id, directory):
        session_id = validate_session_id(session_id)
        new_directory = self.validate_directory(directory)
        with self.lock:
            old_directory = self.directory_for(session_id)
            old_path = SessionCache(old_directory, self.max_bytes).path_for(session_id)
            new_cache = SessionCache(new_directory, self.max_bytes)
            new_directory.mkdir(parents=True, exist_ok=True)
            new_path = new_cache.path_for(session_id)
            moved = old_path != new_path and old_path.is_file()

            if moved:
                if old_path.stat().st_size > self.max_bytes:
                    raise ValueError("The saved analysis session is too large to move safely.")
                encoded = old_path.read_bytes()
                temporary_path = new_directory / f".{new_path.name}.{uuid.uuid4().hex}.tmp"
                try:
                    with temporary_path.open("wb") as output:
                        output.write(encoded)
                        output.flush()
                        os.fsync(output.fileno())
                    os.replace(temporary_path, new_path)
                finally:
                    if temporary_path.exists():
                        temporary_path.unlink()

            registry = self._read_registry_locked()
            if new_directory == self.default_directory:
                registry.pop(session_id, None)
            else:
                registry[session_id] = str(new_directory)
            self._write_registry_locked(registry)

            if moved and old_path.exists():
                old_path.unlink()
            return {
                "session_id": session_id,
                "cache_directory": str(new_directory),
                "cache_file": str(new_path),
                "moved": moved,
            }
