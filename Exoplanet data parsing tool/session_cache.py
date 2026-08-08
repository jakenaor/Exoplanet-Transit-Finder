"""Disk-backed browser session caches for completed transit analyses."""

from datetime import datetime, timezone
import json
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
        with path.open("r", encoding="utf-8") as source:
            document = json.load(source)
        if not isinstance(document, dict) or document.get("session_id") != session_id:
            raise ValueError("The saved analysis session is invalid.")
        state = document.get("state")
        if not isinstance(state, dict):
            raise ValueError("The saved analysis session has no usable state.")
        return document

    def save(self, session_id, state):
        session_id = validate_session_id(session_id)
        if not isinstance(state, dict):
            raise ValueError("Analysis session state must be a JSON object.")
        results = state.get("results", [])
        if not isinstance(results, list) or len(results) > 100:
            raise ValueError("Analysis session results must contain at most 100 files.")

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
