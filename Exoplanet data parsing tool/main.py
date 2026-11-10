#------------------------------------------------------------------#
# exoplanet transit finder                                         #
# app by Jnaor                                                     #
# discord: jake_5101 :D                                            #
#                                                                  #
# search: TLS by Michael Hippke + René Heller                      #
# transit models: batman by Laura Kreidberg                        #
# also uses NumPy, SciPy, Astropy, Numba + tqdm                    #
# full credits + paper references: ../CREDITS.md                   #
#------------------------------------------------------------------#

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cgi as Cgi
import json as Json
import mimetypes as Mimetypes
import os as Os
from pathlib import Path
import threading as Threading
import time as Time
from urllib.parse import parse_qs as ParseQs, unquote as Unquote, urlparse as Urlparse
import webbrowser as Webbrowser

from analysis import RunCurve, ParseDetectionOptions
from analysis_jobs import AnalysisJobManager, AnnotateAnalysisResult
from parsers import ReadCurveUpload
from session_cache import DEFAULT_MAX_SESSION_BYTES, SessionCacheManager, ValidateSessionId


#MARK: core stuffs
HOST = "127.0.0.1"
DEFAULT_PORT = 8000
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_PATH = STATIC_DIR / "index.html"
BROWSER_OPT_OUT_ENV = "TRANSIT_FINDER_NO_BROWSER"
MAX_JOBS_ENV = "TRANSIT_FINDER_MAX_JOBS"
CLIENT_DISCONNECT_ERRORS = (
    BrokenPipeError,
    ConnectionAbortedError,
    ConnectionResetError,
)


#MARK: start the app
def RunApp():
    Os.environ.setdefault("MPLCONFIGDIR", Os.path.join(Os.getcwd(), ".matplotlib-cache"))
    Server = None
    for Port in range(DEFAULT_PORT, DEFAULT_PORT + 11):
        try:
            # try the next port if another local app is already using this one.
            Server = ThreadingHTTPServer((HOST, Port), TransitRequestHandler)
            break
        except OSError:
            continue
    if Server is None:
        raise OSError(f"Could not bind to any port from {DEFAULT_PORT} to {DEFAULT_PORT + 10}.")

    try:
        MaxJobs = max(1, int(Os.environ.get(MAX_JOBS_ENV, "1")))
    except ValueError:
        MaxJobs = 1
    Server.AnalysisJobs = AnalysisJobManager(MaxRunning=MaxJobs)
    Server.RunCache = SessionCacheManager()

    Url = f"http://{HOST}:{Server.server_port}/"
    print(f"Transit Finder running at {Url}")
    print(f"Default session cache location: {Server.RunCache.DefaultDirectory}")
    print("Press Ctrl+C to stop.")
    OpenBrowserSoon(Url)
    try:
        Server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        Server.AnalysisJobs.shutdown()
        Server.server_close()



#MARK: core stuffs
def ReadStaticFile(FilePath):
    return FilePath.read_bytes()


#MARK: open browser soon
def OpenBrowserSoon(Url):
    if Os.environ.get(BROWSER_OPT_OUT_ENV):
        return

    def OpenBrowser():
        # give the server a moment before opening the page.
        Time.sleep(0.4)
        try:
            Webbrowser.open(Url, new=2)
        except Exception as Exc:
            print(f"Could not open browser automatically: {Exc}")

    Threading.Thread(target=OpenBrowser, daemon=True).start()


#MARK: worker stuffs
def FormatAnalysisJobPoll(JobId, Job):
    Timestamp = Time.strftime("%Y-%m-%d %H:%M:%S")
    ShortId = str(JobId)[:8]
    if Job is None:
        return f"[{Timestamp}] [analysis poll] job={ShortId} status=not-found"

    Status = str(Job.get("status") or "unknown")
    Elapsed = max(0.0, float(Job.get("elapsed_seconds") or 0.0))
    SourceFile = Json.dumps(str(Job.get("source_file") or "unknown"))
    Details = [
        f"[{Timestamp}] [analysis poll]",
        f"job={ShortId}",
        f"file={SourceFile}",
        f"status={Status}",
        f"elapsed={Elapsed:.1f}s",
    ]
    QueuePosition = Job.get("queue_position")
    if QueuePosition is not None:
        Details.append(f"queue={QueuePosition}")
    if Job.get("stage_label"):
        Details.append(f"stage={Json.dumps(str(Job['stage_label']))}")
    if Status == "failed" and Job.get("error"):
        Details.append(f"error={Json.dumps(str(Job['error']))}")
    return " ".join(Details)


#MARK: web stuffs
class TransitRequestHandler(BaseHTTPRequestHandler):
    server_version = "TransitFinder/1.0"

    #MARK: do get
    def do_GET(self):
        FilePath = Urlparse(self.path).path
        if FilePath == "/analysis-jobs":
            RequestId = ParseQs(Urlparse(self.path).query).get("request_id", [""])[0]
            Job = self.server.AnalysisJobs.FindByRequestId(RequestId)
            self.WriteJson(Job if Job else {"error": "Analysis submission not found."}, Status=200 if Job else 404)
            return
        if FilePath == "/analysis-sessions":
            try:
                self.WriteJson({
                    "sessions": self.server.RunCache.ListSessions(),
                    "default_directory": str(self.server.RunCache.DefaultDirectory),
                })
            except Exception as Exc:
                self.WriteJson({"error": str(Exc)}, Status=400)
            return
        SessionId = self.AnalysisSessionId(FilePath)
        if SessionId is not None:
            try:
                Document = self.server.RunCache.load(SessionId)
                if Document is None:
                    self.WriteJson({
                        "exists": False,
                        "session_id": SessionId,
                        "cache_directory": str(self.server.RunCache.DirectoryFor(SessionId)),
                        "cache_file": str(self.server.RunCache.PathFor(SessionId)),
                    })
                else:
                    self.WriteJson({
                        "exists": True,
                        "cache_directory": str(self.server.RunCache.DirectoryFor(SessionId)),
                        "cache_file": str(self.server.RunCache.PathFor(SessionId)),
                        **Document,
                    })
            except Exception as Exc:
                self.WriteJson({"error": str(Exc)}, Status=400)
            return
        JobId = self.AnalysisJobId(FilePath)
        if JobId is not None:
            Job = self.server.AnalysisJobs.get(JobId)
            print(FormatAnalysisJobPoll(JobId, Job), flush=True)
            if Job is None:
                self.WriteJson({"error": "Analysis job not found."}, Status=404)
            else:
                self.WriteJson(Job, Status=200)
            return
        if FilePath == "/":
            self.WriteFile(INDEX_PATH, "text/html; charset=utf-8")
            return
        if FilePath.startswith("/static/"):
            RelativePath = Unquote(FilePath.removeprefix("/static/"))
            RequestedPath = (STATIC_DIR / RelativePath).resolve()
            try:
                RequestedPath.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self.send_error(404)
                return
            if not RequestedPath.is_file():
                self.send_error(404)
                return
            ContentType = Mimetypes.guess_type(str(RequestedPath))[0] or "application/octet-stream"
            if RequestedPath.suffix == ".js":
                ContentType = "application/javascript; charset=utf-8"
            elif RequestedPath.suffix == ".css":
                ContentType = "text/css; charset=utf-8"
            self.WriteFile(RequestedPath, ContentType)
            return
        self.send_error(404)

    #MARK: do post
    def do_POST(self):
        FilePath = Urlparse(self.path).path
        LocationSessionId = self.AnalysisSessionLocationId(FilePath)
        if LocationSessionId is not None:
            try:
                Payload = self.ReadJsonRequest(16 * 1024)
                Relocated = self.server.RunCache.relocate(
                    LocationSessionId,
                    Payload.get("directory"),
                )
                print(
                    f"[session cache] session={LocationSessionId[:8]} location="
                    f"{Json.dumps(Relocated['cache_directory'])} moved={Relocated['moved']}",
                    flush=True,
                )
                self.WriteJson({"updated": True, **Relocated})
            except CLIENT_DISCONNECT_ERRORS:
                self.LogClientDisconnect()
            except Exception as Exc:
                self.WriteJson({"error": str(Exc)}, Status=400)
            return
        SessionId = self.AnalysisSessionId(FilePath)
        if SessionId is not None:
            try:
                State = self.ReadJsonRequest(DEFAULT_MAX_SESSION_BYTES)
                Saved = self.server.RunCache.save(SessionId, State)
                print(
                    f"[session cache] session={SessionId[:8]} saved={Saved['size_bytes']}B "
                    f"path={Json.dumps(Saved['cache_file'])}",
                    flush=True,
                )
                self.WriteJson({
                    "saved": True,
                    **Saved,
                })
            except CLIENT_DISCONNECT_ERRORS:
                self.LogClientDisconnect()
            except Exception as Exc:
                self.WriteJson({"error": str(Exc)}, Status=400)
            return
        if FilePath not in {"/analyze", "/analysis-jobs"}:
            self.send_error(404)
            return

        try:
            TimeValues, FluxValues, Options, SourceFile = self.ParseAnalysisRequest()
            if FilePath == "/analysis-jobs":
                Job = self.server.AnalysisJobs.submit(
                    TimeValues,
                    FluxValues,
                    Options,
                    SourceFile=SourceFile,
                )
                self.WriteJson(Job, Status=202)
            else:
                # older clients can still use the direct analysis route.
                Payload = RunCurve(TimeValues, FluxValues, Options)
                Payload = AnnotateAnalysisResult(Payload, Options, SourceFile)
                self.WriteJson(Payload, Status=200)
        except CLIENT_DISCONNECT_ERRORS:
            self.LogClientDisconnect()
        except Exception as Exc:
            self.WriteJson({"error": str(Exc)}, Status=400)

    #MARK: do delete
    def do_DELETE(self):
        FilePath = Urlparse(self.path).path
        JobId = self.AnalysisJobId(FilePath)
        if JobId is None:
            self.send_error(404)
            return
        Job = self.server.AnalysisJobs.cancel(JobId)
        if Job is None:
            self.WriteJson({"error": "Analysis job not found."}, Status=404)
        else:
            self.WriteJson(Job, Status=200)

    #MARK: curve uploads
    def ParseAnalysisRequest(self):
        Form = Cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )
        FileItem = Form["datafile"] if "datafile" in Form else (Form["csv"] if "csv" in Form else None)
        if FileItem is None or not getattr(FileItem, "file", None):
            raise ValueError("No CSV or FITS file was uploaded.")
        Parsed = ReadCurveUpload(FileItem, ReturnMetadata=True,
            TimeFormat=Form.getfirst("csvTimeFormat") or None,
            TimeScale=Form.getfirst("csvTimeScale") or None,
            TimeUnit=Form.getfirst("csvTimeUnit") or None)
        TimeValues, FluxValues = Parsed["time"], Parsed["flux"]
        Options = ParseDetectionOptions(Form)
        Options["_input_metadata"] = Parsed["input_metadata"]
        Options["_cleaning_report"] = Parsed["cleaning"]
        # missing optional values stay null when sent to a worker.
        if Parsed["flux_uncertainty"] is not None:
            Options["_flux_uncertainty"] = [float(V) if V == V else None for V in Parsed["flux_uncertainty"]]
        if Parsed.get("exposure_seconds") is not None:
            Options["_exposure_seconds"] = [float(V) if V == V else None for V in Parsed["exposure_seconds"]]
        for Field, Key in (("batchId", "_batch_id"), ("analysisRequestId", "_request_id")):
            Value = str(Form.getfirst(Field) or "").strip()
            if Value:
                if len(Value) > 160 or not all(C.isalnum() or C in "_:-." for C in Value):
                    raise ValueError(f"Invalid {Field}.")
                Options[Key] = Value
        SourceFile = getattr(FileItem, "filename", None)
        return TimeValues, FluxValues, Options, SourceFile

    #MARK: read requests
    def ReadJsonRequest(self, MaxBytes):
        try:
            ContentLength = int(self.headers.get("Content-Length", "0"))
        except ValueError as Exc:
            raise ValueError("Invalid session cache request length.") from Exc
        if ContentLength <= 0:
            raise ValueError("Analysis session state is empty.")
        if ContentLength > MaxBytes:
            raise ValueError("The analysis session is too large to save.")
        try:
            Payload = Json.loads(self.rfile.read(ContentLength).decode("utf-8"))
        except (UnicodeDecodeError, Json.JSONDecodeError) as Exc:
            raise ValueError("Analysis session state is not valid JSON.") from Exc
        if not isinstance(Payload, dict):
            raise ValueError("Analysis session state must be a JSON object.")
        return Payload

    #MARK: worker stuffs
    @staticmethod
    def AnalysisJobId(FilePath):
        Prefix = "/analysis-jobs/"
        if not FilePath.startswith(Prefix):
            return None
        JobId = FilePath[len(Prefix):]
        if not JobId or "/" in JobId:
            return None
        return JobId

    #MARK: cache files
    @staticmethod
    def AnalysisSessionId(FilePath):
        Prefix = "/analysis-sessions/"
        if not FilePath.startswith(Prefix):
            return None
        SessionId = FilePath[len(Prefix):]
        if not SessionId or "/" in SessionId:
            return None
        try:
            return ValidateSessionId(SessionId)
        except ValueError:
            return None

    #MARK: cache folders
    @staticmethod
    def AnalysisSessionLocationId(FilePath):
        Prefix = "/analysis-sessions/"
        Suffix = "/location"
        if not FilePath.startswith(Prefix) or not FilePath.endswith(Suffix):
            return None
        SessionId = FilePath[len(Prefix):-len(Suffix)]
        if not SessionId or "/" in SessionId:
            return None
        try:
            return ValidateSessionId(SessionId)
        except ValueError:
            return None

    #MARK: send responses
    def WriteResponse(self, Body, Status, ContentType):
        try:
            self.send_response(Status)
            self.send_header("Content-Type", ContentType)
            self.send_header("Content-Length", str(len(Body)))
            self.end_headers()
            self.wfile.write(Body)
            return True
        except CLIENT_DISCONNECT_ERRORS:
            self.LogClientDisconnect()
            return False

    #MARK: send replies
    def WriteFile(self, FilePath, ContentType):
        return self.WriteResponse(ReadStaticFile(FilePath), 200, ContentType)

    #MARK: send replies
    def WriteJson(self, Payload, Status=200):
        Body = Json.dumps(Payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return self.WriteResponse(Body, Status, "application/json; charset=utf-8")

    #MARK: log client disconnect
    def LogClientDisconnect(self):
        Client = self.client_address[0] if self.client_address else "client"
        print(f"{Client} - connection closed before the response was delivered")

    #MARK: log message
    def log_message(self, Fmt, *Args):
        print("%s - %s" % (self.address_string(), Fmt % Args))




if __name__ == "__main__":
    RunApp()
