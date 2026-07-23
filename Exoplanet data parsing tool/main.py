from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cgi
import json
import mimetypes
import os
from pathlib import Path
import threading
import time
from urllib.parse import unquote, urlparse
import webbrowser

from analysis import analyze, parse_detection_options
from analysis_jobs import AnalysisJobManager
from parsers import parse_light_curve_upload


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


def read_static_file(path):
    return path.read_bytes()


def open_browser_soon(url):
    if os.environ.get(BROWSER_OPT_OUT_ENV):
        return

    def open_browser():
        time.sleep(0.4)
        try:
            webbrowser.open(url, new=2)
        except Exception as exc:
            print(f"Could not open browser automatically: {exc}")

    threading.Thread(target=open_browser, daemon=True).start()


class TransitRequestHandler(BaseHTTPRequestHandler):
    server_version = "TransitFinder/1.0"

    def do_GET(self):
        path = urlparse(self.path).path
        job_id = self.analysis_job_id(path)
        if job_id is not None:
            job = self.server.analysis_jobs.get(job_id)
            if job is None:
                self.write_json({"error": "Analysis job not found."}, status=404)
            else:
                self.write_json(job, status=200)
            return
        if path == "/":
            self.write_file(INDEX_PATH, "text/html; charset=utf-8")
            return
        if path.startswith("/static/"):
            relative_path = unquote(path.removeprefix("/static/"))
            requested_path = (STATIC_DIR / relative_path).resolve()
            try:
                requested_path.relative_to(STATIC_DIR.resolve())
            except ValueError:
                self.send_error(404)
                return
            if not requested_path.is_file():
                self.send_error(404)
                return
            content_type = mimetypes.guess_type(str(requested_path))[0] or "application/octet-stream"
            if requested_path.suffix == ".js":
                content_type = "application/javascript; charset=utf-8"
            elif requested_path.suffix == ".css":
                content_type = "text/css; charset=utf-8"
            self.write_file(requested_path, content_type)
            return
        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in {"/analyze", "/analysis-jobs"}:
            self.send_error(404)
            return

        try:
            time_values, flux_values, options, source_file = self.parse_analysis_request()
            if path == "/analysis-jobs":
                job = self.server.analysis_jobs.submit(
                    time_values,
                    flux_values,
                    options,
                    source_file=source_file,
                )
                self.write_json(job, status=202)
            else:
                # Preserve the original synchronous endpoint for API compatibility.
                payload = analyze(time_values, flux_values, options)
                self.write_json(payload, status=200)
        except CLIENT_DISCONNECT_ERRORS:
            self.log_client_disconnect()
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=400)

    def do_DELETE(self):
        path = urlparse(self.path).path
        job_id = self.analysis_job_id(path)
        if job_id is None:
            self.send_error(404)
            return
        job = self.server.analysis_jobs.cancel(job_id)
        if job is None:
            self.write_json({"error": "Analysis job not found."}, status=404)
        else:
            self.write_json(job, status=200)

    def parse_analysis_request(self):
        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type", ""),
                "CONTENT_LENGTH": self.headers.get("Content-Length", "0"),
            },
        )
        file_item = form["datafile"] if "datafile" in form else (form["csv"] if "csv" in form else None)
        if file_item is None or not getattr(file_item, "file", None):
            raise ValueError("No CSV or FITS file was uploaded.")
        time_values, flux_values = parse_light_curve_upload(file_item)
        options = parse_detection_options(form)
        source_file = getattr(file_item, "filename", None)
        return time_values, flux_values, options, source_file

    @staticmethod
    def analysis_job_id(path):
        prefix = "/analysis-jobs/"
        if not path.startswith(prefix):
            return None
        job_id = path[len(prefix):]
        if not job_id or "/" in job_id:
            return None
        return job_id

    def write_file(self, path, content_type):
        body = read_static_file(path)
        try:
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return True
        except CLIENT_DISCONNECT_ERRORS:
            self.log_client_disconnect()
            return False

    def write_json(self, payload, status=200):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        try:
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return True
        except CLIENT_DISCONNECT_ERRORS:
            self.log_client_disconnect()
            return False

    def log_client_disconnect(self):
        client = self.client_address[0] if self.client_address else "client"
        print(f"{client} - connection closed before the response was delivered")

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args))


def main():
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(os.getcwd(), ".matplotlib-cache"))
    server = None
    for port in range(DEFAULT_PORT, DEFAULT_PORT + 11):
        try:
            server = ThreadingHTTPServer((HOST, port), TransitRequestHandler)
            break
        except OSError:
            continue
    if server is None:
        raise OSError(f"Could not bind to any port from {DEFAULT_PORT} to {DEFAULT_PORT + 10}.")

    try:
        max_jobs = max(1, int(os.environ.get(MAX_JOBS_ENV, "1")))
    except ValueError:
        max_jobs = 1
    server.analysis_jobs = AnalysisJobManager(max_running=max_jobs)

    url = f"http://{HOST}:{server.server_port}/"
    print(f"Transit Finder running at {url}")
    print("Press Ctrl+C to stop.")
    open_browser_soon(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.analysis_jobs.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
