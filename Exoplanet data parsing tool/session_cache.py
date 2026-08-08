"""Disk-backed browser session caches for completed transit analyses."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import uuid


SESSION_SCHEMA_VERSION = 1
SESSION_CACHE_DIR_ENV = "TRANSIT_FINDER_SESSION_CACHE_DIR"
SESSION_CACHE_DIR_NAME = "Exoplanet Transit Finder Sessions"
DEFAULT_MAX_SESSION_BYTES = 250 * 1024 * 1024
SESSION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,80}$")


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

