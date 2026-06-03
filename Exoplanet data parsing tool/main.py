from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import cgi
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from analysis import analyze, parse_detection_options
from parsers import parse_light_curve_upload


HOST = "127.0.0.1"
DEFAULT_PORT = 8000
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
INDEX_PATH = STATIC_DIR / "index.html"


def read_static_file(path):
    return path.read_bytes()


class TransitRequestHandler(BaseHTTPRequestHandler):
    server_version = "TransitFinder/1.0"

    def do_GET(self):
        path = urlparse(self.path).path
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
        if path != "/analyze":
            self.send_error(404)
            return

        try:
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
            time, flux = parse_light_curve_upload(file_item)
            options = parse_detection_options(form)
            payload = analyze(time, flux, options)
            self.write_json(payload, status=200)
        except Exception as exc:
            self.write_json({"error": str(exc)}, status=400)

    def write_file(self, path, content_type):
        body = read_static_file(path)
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def write_json(self, payload, status=200):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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

    print(f"Transit Finder running at http://{HOST}:{server.server_port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
