"""Save and restore browser sessions as JSON files."""

#MARK: imports
from datetime import datetime as Datetime, timezone as Timezone
import copy as Copy
import json as Json
import math as Math
import os as Os
from pathlib import Path
import re as Re
import threading as Threading
import uuid as Uuid


#MARK: core stuffs
SESSION_SCHEMA_VERSION = 1
SESSION_CACHE_DIR_ENV = "TRANSIT_FINDER_SESSION_CACHE_DIR"
SESSION_CACHE_DIR_NAME = "Exoplanet Transit Finder Sessions"
DEFAULT_MAX_SESSION_BYTES = 250 * 1024 * 1024
SESSION_ID_PATTERN = Re.compile(r"^[a-zA-Z0-9_-]{8,80}$")
SESSION_FILENAME_PATTERN = Re.compile(r"^session-([a-zA-Z0-9_-]{8,80})\.json$")
CURRENT_RESULT_SCHEMA_VERSION = 2


#MARK: safe file writes
def _WriteAtomicBytes(FilePath, Encoded):
    """Finish writing the new file before replacing the old one."""
    TemporaryPath = FilePath.parent / f".{FilePath.name}.{Uuid.uuid4().hex}.tmp"
    try:
        with TemporaryPath.open("wb") as Output:
            Output.write(Encoded)
            Output.flush()
            Os.fsync(Output.fileno())
        Os.replace(TemporaryPath, FilePath)
    finally:
        if TemporaryPath.exists():
            TemporaryPath.unlink()


#MARK: cache files
def _FiniteNumber(Value):
    # bool is an int in python, but it is not a sample value.
    return isinstance(Value, (int, float)) and not isinstance(Value, bool) and Math.isfinite(Value)


#MARK: core stuffs
def _RejectNonfiniteJson(Value):
    raise ValueError(f"Nonfinite JSON value: {Value}")


#MARK: checking paired arrays
def _ValidateArrayGroup(Section, Keys, Label, AllowNull=False):
    Values = [Section.get(Key) for Key in Keys]
    if not any(Value is not None for Value in Values):
        return
    if any(not isinstance(Value, list) for Value in Values) or len({len(Value) for Value in Values}) != 1:
        raise ValueError(f"The saved result has mismatched {Label} arrays. The original cache is unchanged.")
    if any(not _FiniteNumber(Value) and not (AllowNull and Value is None) for Array in Values for Value in Array):
        raise ValueError(f"The saved result has invalid {Label} values. The original cache is unchanged.")


#MARK: core stuffs
def _ValidateResultMetadata(Result, FileName):
    Version = Result.get("result_schema_version", 1)
    if not isinstance(Version, int) or isinstance(Version, bool) or not 1 <= Version <= CURRENT_RESULT_SCHEMA_VERSION:
        raise ValueError(f"The saved result for {FileName} uses an unsupported result schema. The original cache is unchanged.")
    Provenance = Result.get("provenance")
    if Provenance is not None:
        if not isinstance(Provenance, dict):
            raise ValueError(f"The saved result for {FileName} has invalid provenance metadata.")
        ProvenanceVersion = Provenance.get("result_schema_version", Version)
        if not isinstance(ProvenanceVersion, int) or isinstance(ProvenanceVersion, bool) or ProvenanceVersion != Version:
            raise ValueError(f"The saved result for {FileName} has inconsistent provenance/result schemas.")
        for Key in ("analysis_version", "app_version"):
            if Key in Provenance and not isinstance(Provenance[Key], str):
                raise ValueError(f"The saved result for {FileName} has invalid {Key} metadata.")
        for Key in ("dependency_versions", "effective_settings"):
            if Key in Provenance and not isinstance(Provenance[Key], dict):
                raise ValueError(f"The saved result for {FileName} has invalid {Key} metadata.")
        if Result.get("analyzed_at") and Provenance.get("analyzed_at") and Result["analyzed_at"] != Provenance["analyzed_at"]:
            raise ValueError(f"The saved result for {FileName} has inconsistent analysis timestamps.")
    for AnalyzedAt in (Result.get("analyzed_at"), (Provenance or {}).get("analyzed_at")):
        if AnalyzedAt is not None:
            if not isinstance(AnalyzedAt, str):
                raise ValueError(f"The saved result for {FileName} has an invalid analysis timestamp.")
            try:
                ParsedAt = Datetime.fromisoformat(AnalyzedAt.replace("Z", "+00:00"))
            except ValueError as Exc:
                raise ValueError(f"The saved result for {FileName} has an invalid analysis timestamp.") from Exc
            if ParsedAt.tzinfo is None:
                raise ValueError(f"The saved result for {FileName} has an analysis timestamp without a time zone.")


#MARK: save runs
def ValidateResult(Result, FileName="saved file"):
    """Check the metadata and arrays before the browser uses a saved result."""
    if not isinstance(Result, dict):
        raise ValueError(f"The saved result for {FileName} is not a result object.")
    _ValidateResultMetadata(Result, FileName)
    #MARK: plot stuffs
    Plot = Result.get("plot")
    if not isinstance(Plot, dict):
        raise ValueError(f"The saved result for {FileName} has no usable plot arrays. The original cache is unchanged.")
    Arrays = [Plot.get(Key) for Key in ("time", "raw_flux", "smooth_flux")]
    if any(not isinstance(A, list) or not A for A in Arrays) or len({len(A) for A in Arrays}) != 1:
        raise ValueError(f"The saved result for {FileName} has mismatched plot arrays. The original cache is unchanged.")
    if any(not _FiniteNumber(V) for A in Arrays for V in A):
        raise ValueError(f"The saved result for {FileName} contains nonfinite plot values. The original cache is unchanged.")
    if any(Right < Left for Left, Right in zip(Arrays[0], Arrays[0][1:])):
        raise ValueError(f"The saved result for {FileName} has unsorted plot times.")
    Period = Result.get("period")
    if Period is not None and (not _FiniteNumber(Period) or Period <= 0):
        raise ValueError(f"The saved result for {FileName} has an invalid period.")
    #MARK: transit windows
    Transits = Result.get("transits", [])
    if not isinstance(Transits, list):
        raise ValueError(f"The saved result for {FileName} has invalid transit windows.")
    for Transit in Transits:
        if (not isinstance(Transit, dict)
            or not all(_FiniteNumber(Transit.get(Key)) for Key in ("start", "end"))
            or Transit["end"] < Transit["start"]
            or (Transit.get("center") is not None and not _FiniteNumber(Transit["center"]))):
            raise ValueError(f"The saved result for {FileName} has an invalid transit window.")
    #MARK: core stuffs
    for Name, Keys in (("phase_folded", ("phase", "raw_flux", "smooth_flux")),
                       ("transit_model", ("time", "flux"))):
        Section = Result.get(Name)
        if Section is None:
            continue
        if not isinstance(Section, dict):
            raise ValueError(f"The saved result for {FileName} has invalid {Name} data.")
        Values = [Section.get(Key) for Key in Keys]
        if any(Value is not None for Value in Values):
            if any(not isinstance(Value, list) for Value in Values) or len({len(Value) for Value in Values}) != 1:
                raise ValueError(f"The saved result for {FileName} has mismatched {Name} arrays.")
            if any(not _FiniteNumber(V) for A in Values for V in A):
                raise ValueError(f"The saved result for {FileName} has nonfinite {Name} values.")
    Phase = Result.get("phase_folded") or {}
    _ValidateArrayGroup(Phase, ("binned_phase", "binned_flux"), "binned phase")
    _ValidateArrayGroup(Result.get("transit_model") or {}, ("folded_phase_days", "folded_flux"), "folded model")
    #MARK: transit stack
    Comparison = Result.get("model_comparison")
    if Comparison is not None:
        if not isinstance(Comparison, dict):
            raise ValueError("The saved result has invalid model comparison data.")
        _ValidateArrayGroup(Comparison, ("time", "search_flux", "model_flux", "residual_flux"), "model comparison")
    Stack = Result.get("transit_stack")
    if Stack is not None:
        if not isinstance(Stack, dict) or not isinstance(Stack.get("traces", []), list):
            raise ValueError("The saved result has invalid transit stack data.")
        _ValidateArrayGroup(Stack, ("median_phase_days", "median_flux"), "transit stack median")
        for Trace in Stack.get("traces", []):
            if not isinstance(Trace, dict):
                raise ValueError("The saved result has an invalid transit stack trace.")
            _ValidateArrayGroup(Trace, ("phase_days", "flux"), "transit stack trace")
    #MARK: flux errors
    # missing errors are allowed; present errors must be positive and aligned.
    Errors = Plot.get("flux_uncertainty")
    if Errors is not None and (not isinstance(Errors, list) or len(Errors) != len(Arrays[0])
            or any(Value is not None and (not _FiniteNumber(Value) or Value <= 0) for Value in Errors)):
        raise ValueError("The saved result has invalid flux uncertainty samples.")
    return Result


#MARK: cache files
def ValidatedSessionState(State):
    if not isinstance(State, dict):
        raise ValueError("Analysis session state must be a JSON object.")
    Results = State.get("results", [])
    if not isinstance(Results, list) or len(Results) > 100:
        raise ValueError("Analysis session results must contain at most 100 files.")
    UiVersion = State.get("ui_schema_version", 1)
    if not isinstance(UiVersion, int) or isinstance(UiVersion, bool) or not 1 <= UiVersion <= 2:
        raise ValueError("This saved session uses an unsupported interface schema. The original cache is unchanged.")
    #MARK: old calls
    # add legacy labels to a copy, leaving the caller's result untouched.
    State = Copy.deepcopy(State)
    Notices = []
    for Item in State.get("results", []):
        if not isinstance(Item, dict):
            raise ValueError("A saved file entry is not an object.")
        Result = Item.get("result")
        if Result is None:
            continue
        ValidateResult(Result, str(Item.get("file_name") or "saved file"))
        Provenance = Result.get("provenance")
        if not isinstance(Provenance, dict) or not Provenance.get("analysis_version"):
            Result.setdefault("result_schema_version", 1)
            Result.setdefault("analyzed_at", None)
            Result["provenance"] = {"analysis_version": "unknown", "app_version": "unknown",
                "result_schema_version": Result["result_schema_version"],
                "analyzed_at": Result["analyzed_at"], "dependency_versions": {},
                "legacy": True, "compatibility_notice": "Legacy result: analysis version unknown; retained without rescoring."}
            Notices.append(str(Item.get("file_name") or "saved file"))
        #MARK: extra signals
        Signals = Result.get("signals")
        if Signals is not None:
            if not isinstance(Signals, list) or len(Signals) > 10:
                raise ValueError("A saved result has invalid signal entries.")
            # each signal needs enough data to open in the result viewer.
            for Signal in Signals:
                if not isinstance(Signal, dict):
                    raise ValueError("A saved signal is not an object.")
                ValidateResult(Signal, str(Item.get("file_name") or "saved signal"))
    #MARK: save runs
    ActiveJob = State.get("active_job_id")
    if ActiveJob is not None and (not isinstance(ActiveJob, str) or not Re.fullmatch(r"[a-zA-Z0-9_-]{1,160}", ActiveJob)):
        raise ValueError("The saved active job ID is invalid.")
    ActiveRequest = State.get("active_request_id")
    if ActiveRequest is not None and (not isinstance(ActiveRequest, str) or not Re.fullmatch(r"[a-zA-Z0-9_.:-]{1,160}", ActiveRequest)):
        raise ValueError("The saved active submission ID is invalid.")
    # a saved job needs a file entry to reconnect the right progress row.
    if ActiveJob or ActiveRequest:
        Index = State.get("active_file_index")
        if not isinstance(Index, int) or isinstance(Index, bool) or not 0 <= Index < len(Results):
            raise ValueError("The saved active job has no matching file entry. The original cache is unchanged.")
    Pending = State.get("pending_files", [])
    if not isinstance(Pending, list) or len(Pending) > 100 or any(not isinstance(Item, dict) for Item in Pending):
        raise ValueError("The saved session has invalid pending file entries.")
    if Notices:
        State["cache_compatibility"] = {"legacy_results": Notices,
            "notice": "Legacy results retain their saved measurements and assessment. Analysis version unknown."}
    return State


#MARK: cache folders
def DefaultSessionCacheDirectory():
    Configured = Os.environ.get(SESSION_CACHE_DIR_ENV)
    if Configured:
        return Path(Configured).expanduser().resolve()
    return (Path.home() / "Desktop" / SESSION_CACHE_DIR_NAME).resolve()


#MARK: cache files
def ValidateSessionId(SessionId):
    Value = str(SessionId or "")
    if not SESSION_ID_PATTERN.fullmatch(Value):
        raise ValueError("Invalid analysis session ID.")
    return Value


#MARK: cache files
class SessionCache:
    """Keep one JSON file for each browser session."""

    #MARK: cache files
    def __init__(self, Directory=None, MaxBytes=DEFAULT_MAX_SESSION_BYTES, **LegacyOptions):
        # older scripts use max_bytes. other extra keywords are still errors.
        MaxBytes = LegacyOptions.pop("max_bytes", MaxBytes)
        if LegacyOptions:
            raise TypeError(f"Unknown cache options: {', '.join(LegacyOptions)}")
        self.Directory = Path(Directory or DefaultSessionCacheDirectory()).expanduser().resolve()
        self.MaxBytes = max(1024, int(MaxBytes))

    #MARK: cache files
    def PathFor(self, SessionId):
        SessionId = ValidateSessionId(SessionId)
        return self.Directory / f"session-{SessionId}.json"

    #MARK: cache files
    def load(self, SessionId):
        FilePath = self.PathFor(SessionId)
        if not FilePath.is_file():
            return None
        if FilePath.stat().st_size > self.MaxBytes:
            raise ValueError("The saved analysis session is too large to load safely.")
        # validate the file before handing any of its arrays to the browser.
        try:
            with FilePath.open("r", encoding="utf-8") as Source:
                Document = Json.load(Source, parse_constant=_RejectNonfiniteJson)
        except (Json.JSONDecodeError, ValueError) as Exc:
            raise ValueError("The saved analysis session contains invalid JSON. The original cache is unchanged.") from Exc
        if not isinstance(Document, dict) or Document.get("session_id") != SessionId:
            raise ValueError("The saved analysis session is invalid.")
        Version = Document.get("schema_version", 1)
        if not isinstance(Version, int) or isinstance(Version, bool) or not 1 <= Version <= SESSION_SCHEMA_VERSION:
            raise ValueError("This saved session uses an unsupported cache schema. The original cache is unchanged.")
        Document["state"] = ValidatedSessionState(Document.get("state"))
        return Document

    #MARK: cache files
    def save(self, SessionId, State):
        SessionId = ValidateSessionId(SessionId)
        State = ValidatedSessionState(State)

        # this is the save time, not a new analysis date.
        SavedAt = Datetime.now(Timezone.utc).isoformat()
        Document = {
            "schema_version": SESSION_SCHEMA_VERSION,
            "session_id": SessionId,
            "saved_at": SavedAt,
            "state": State,
        }
        Encoded = Json.dumps(
            Document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(Encoded) > self.MaxBytes:
            raise ValueError("The analysis session is too large to save.")

        self.Directory.mkdir(parents=True, exist_ok=True)
        FilePath = self.PathFor(SessionId)
        _WriteAtomicBytes(FilePath, Encoded)

        return {
            "session_id": SessionId,
            "saved_at": SavedAt,
            "cache_file": str(FilePath),
            "size_bytes": len(Encoded),
        }


#MARK: old calls
class SessionCacheManager:
    """Track where sessions are saved and move them when the folder changes."""

    #MARK: old calls
    def __init__(self, DefaultDirectory=None, MaxBytes=DEFAULT_MAX_SESSION_BYTES, **LegacyOptions):
        # keep existing callers working while the internal names use camelcase.
        DefaultDirectory = LegacyOptions.pop("default_directory", DefaultDirectory)
        MaxBytes = LegacyOptions.pop("max_bytes", MaxBytes)
        if LegacyOptions:
            raise TypeError(f"Unknown cache options: {', '.join(LegacyOptions)}")
        self.DefaultDirectory = Path(
            DefaultDirectory or DefaultSessionCacheDirectory()
        ).expanduser().resolve()
        self.Directory = self.DefaultDirectory
        self.MaxBytes = max(1024, int(MaxBytes))
        self.RegistryPath = self.DefaultDirectory / ".session-locations.json"
        self.Lock = Threading.RLock()

    #MARK: cache folders
    def _ReadRegistryLocked(self):
        if not self.RegistryPath.is_file():
            return {}
        if self.RegistryPath.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("The session location registry is too large.")
        with self.RegistryPath.open("r", encoding="utf-8") as Source:
            Payload = Json.load(Source)
        if not isinstance(Payload, dict):
            raise ValueError("The session location registry is invalid.")
        return {
            SessionId: Directory
            for SessionId, Directory in Payload.items()
            if SESSION_ID_PATTERN.fullmatch(str(SessionId)) and isinstance(Directory, str)
        }

    #MARK: cache folders
    def _WriteRegistryLocked(self, Registry):
        self.DefaultDirectory.mkdir(parents=True, exist_ok=True)
        Encoded = Json.dumps(
            Registry,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        _WriteAtomicBytes(self.RegistryPath, Encoded)

    #MARK: old calls
    @staticmethod
    def ValidateDirectory(Directory):
        Value = str(Directory or "").strip()
        if not Value:
            raise ValueError("Enter a save folder.")
        FilePath = Path(Value).expanduser()
        if not FilePath.is_absolute():
            raise ValueError("Save location must be an absolute path or start with ~.")
        FilePath = FilePath.resolve()
        if FilePath == Path(FilePath.anchor):
            raise ValueError("Choose a folder instead of the filesystem root.")
        if FilePath.exists() and not FilePath.is_dir():
            raise ValueError("The save location points to a file, not a folder.")
        return FilePath

    #MARK: old calls
    def DirectoryFor(self, SessionId):
        SessionId = ValidateSessionId(SessionId)
        with self.Lock:
            Registry = self._ReadRegistryLocked()
            Configured = Registry.get(SessionId)
            if not Configured:
                return self.DefaultDirectory
            try:
                return self.ValidateDirectory(Configured)
            except ValueError:
                return self.DefaultDirectory

    #MARK: cache files
    def CacheFor(self, SessionId):
        return SessionCache(self.DirectoryFor(SessionId), self.MaxBytes)

    def PathFor(self, SessionId):
        return self.CacheFor(SessionId).PathFor(SessionId)

    def load(self, SessionId):
        with self.Lock:
            return self.CacheFor(SessionId).load(SessionId)

    def save(self, SessionId, State):
        with self.Lock:
            Saved = self.CacheFor(SessionId).save(SessionId, State)
            return {
                **Saved,
                "cache_directory": str(Path(Saved["cache_file"]).parent),
            }

    #MARK: save runs
    def ListSessions(self):
        """List saved sessions without reading all their result data."""
        with self.Lock:
            Registry = self._ReadRegistryLocked()
            CachePaths = {}

            #MARK: old calls
            if self.DefaultDirectory.is_dir():
                for FilePath in self.DefaultDirectory.glob("session-*.json"):
                    Match = SESSION_FILENAME_PATTERN.fullmatch(FilePath.name)
                    if Match and FilePath.is_file():
                        CachePaths[Match.group(1)] = FilePath

            #MARK: old calls
            # use the chosen folder even if an old copy remains in the default one.
            for SessionId, Directory in Registry.items():
                try:
                    CustomDirectory = self.ValidateDirectory(Directory)
                    CustomPath = SessionCache(CustomDirectory, self.MaxBytes).PathFor(SessionId)
                except ValueError:
                    continue
                if CustomPath.is_file():
                    CachePaths[SessionId] = CustomPath

            #MARK: cache files
            Sessions = []
            for SessionId, FilePath in CachePaths.items():
                try:
                    Stat = FilePath.stat()
                except OSError:
                    continue
                Sessions.append({
                    "session_id": SessionId,
                    "modified_at": Datetime.fromtimestamp(
                        Stat.st_mtime,
                        Timezone.utc,
                    ).isoformat(),
                    "size_bytes": Stat.st_size,
                    "cache_directory": str(FilePath.parent),
                    "cache_file": str(FilePath),
                    "loadable": Stat.st_size <= self.MaxBytes,
                })

            Sessions.sort(key=lambda Item: Item["modified_at"], reverse=True)
            return Sessions

    #MARK: cache files
    def relocate(self, SessionId, Directory):
        SessionId = ValidateSessionId(SessionId)
        NewDirectory = self.ValidateDirectory(Directory)
        with self.Lock:
            OldDirectory = self.DirectoryFor(SessionId)
            OldPath = SessionCache(OldDirectory, self.MaxBytes).PathFor(SessionId)
            NewCache = SessionCache(NewDirectory, self.MaxBytes)
            NewDirectory.mkdir(parents=True, exist_ok=True)
            NewPath = NewCache.PathFor(SessionId)
            Moved = OldPath != NewPath and OldPath.is_file()

            #MARK: cache files
            if Moved:
                if OldPath.stat().st_size > self.MaxBytes:
                    raise ValueError("The saved analysis session is too large to move safely.")
                Encoded = OldPath.read_bytes()
                _WriteAtomicBytes(NewPath, Encoded)

            #MARK: cache folders
            Registry = self._ReadRegistryLocked()
            if NewDirectory == self.DefaultDirectory:
                Registry.pop(SessionId, None)
            else:
                Registry[SessionId] = str(NewDirectory)
            # update the location record before removing the old copy.
            self._WriteRegistryLocked(Registry)

            #MARK: core stuffs
            if Moved and OldPath.exists():
                OldPath.unlink()
            return {
                "session_id": SessionId,
                "cache_directory": str(NewDirectory),
                "cache_file": str(NewPath),
                "moved": Moved,
            }
