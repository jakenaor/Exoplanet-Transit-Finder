"""Exercise the shipped executable from a fresh folder, without repo imports."""
import argparse as Argparse
import csv as Csv
import io as Io
import json as Json
import os as Os
from pathlib import Path
import queue as Queue
import re as Re
import signal as Signal
import subprocess as Subprocess
import tempfile as Tempfile
import threading as Threading
import time as Clock
from urllib.error import HTTPError
from urllib.request import Request, urlopen as Urlopen


#MARK: actual http, not an imported copy of the app
def Ask(Base, Route, Method="GET", Data=None, Mime="application/json"):
    Query = Request(Base + Route, data=Data, method=Method, headers={"Content-Type": Mime})
    try:
        Reply = Urlopen(Query, timeout=20)
    except HTTPError as ErrorThing:
        Reply = ErrorThing
    with Reply:
        Raw = Reply.read()
        if Reply.status >= 400:
            raise AssertionError((Route, Reply.status, Raw[:1000]))
        return Raw


def Multipart(Fields, Name, FilePath, Mime="text/csv"):
    Boundary = "packaged-transit-demo-test"
    Parts = []
    for Key, Value in Fields.items():
        Parts.append(f'--{Boundary}\r\nContent-Disposition: form-data; name="{Key}"\r\n\r\n{Value}\r\n'.encode())
    Parts.append((f'--{Boundary}\r\nContent-Disposition: form-data; name="{Name}"; filename="{FilePath.name}"\r\n'
                  f'Content-Type: {Mime}\r\n\r\n').encode())
    Parts += [FilePath.read_bytes(), f"\r\n--{Boundary}--\r\n".encode()]
    return b"".join(Parts), "multipart/form-data; boundary=" + Boundary


def WaitJob(Base, Route, Limit=180):
    End = Clock.monotonic() + Limit
    while Clock.monotonic() < End:
        Job = Json.loads(Ask(Base, Route))
        if Job["status"] in ("completed", "failed", "cancelled"):
            if Job["status"] != "completed":
                raise AssertionError(Job)
            return Job["result"]
        Clock.sleep(.15)
    raise AssertionError("packaged job timed out: " + Route)


#MARK: a real spawn, then a real tls pool, then the image thread pool
def CheckRoutes(Base, Samples):
    assert b"v69" in Ask(Base, "/")
    assert b"ScienceImages" in Ask(Base, "/images")
    ShortFields = {"inspectOnly": "true", "csvTimeFormat": "relative", "csvTimeScale": "unknown"}
    Body, Mime = Multipart(ShortFields, "datafile", Samples / "short_observation.csv")
    Job = Json.loads(Ask(Base, "/analysis-jobs", "POST", Body, Mime))
    Short = WaitJob(Base, "/analysis-jobs/" + Job["job_id"])
    assert Short["review_only"] and Short["cleaning"]["retained_rows"] == 90
    print("ok: spawned observation-viewer job", flush=True)

    Fields = {"searchMode": "tls", "minPeriod": "1.4", "maxPeriod": "3.5", "tlsOversampling": "2",
              "tlsThreads": "2", "csvTimeFormat": "relative", "csvTimeScale": "unknown"}
    Body, Mime = Multipart(Fields, "datafile", Samples / "synthetic_transit.csv")
    Job = Json.loads(Ask(Base, "/analysis-jobs", "POST", Body, Mime))
    Transit = WaitJob(Base, "/analysis-jobs/" + Job["job_id"])
    assert abs(Transit["period"] - 2.4) < .024, Transit["period"]
    Versions = Transit["provenance"]["dependency_versions"]
    assert all(Versions.get(Name) for Name in ("numpy", "scipy", "astropy", "transitleastsquares", "batman-package", "numba")), Versions
    print("ok: TLS with two nested workers, recovered period", Transit["period"], flush=True)

    Id = Json.loads(Ask(Base, "/image-runs", "POST", b"{}"))["id"]
    Route = "/image-runs/" + Id
    for Kind, Folder in (("science", "Science"), ("dark", "Darks")):
        for FilePath in sorted((Samples / "FITS Demo" / Folder).glob("*.fits")):
            Body, Mime = Multipart({}, "image", FilePath, "application/fits")
            Ask(Base, Route + "/frames?kind=" + Kind, "POST", Body, Mime)
    Preview = Json.loads(Ask(Base, Route + "/preview"))
    assert Preview["image_width"] == 192 and Preview["png"].startswith("iVBOR")
    Options = {"stars": [[48, 50], [136, 72]], "radius": 8, "inner": 12, "outer": 20, "tracking": 8, "workers": 4}
    Ask(Base, Route + "/process", "POST", Json.dumps(Options).encode())
    Images = WaitJob(Base, Route)
    assert Images["usable_frames"] == 12, Images
    Metadata = Json.loads(Ask(Base, Route + "/metadata.json"))
    assert Metadata["workers"] == 4 and not Metadata["flat_field_applied"]
    Rows = list(Csv.DictReader(Io.StringIO(Ask(Base, Route + "/lightcurve.csv").decode())))
    assert len(Rows) == 12 and all(int(Row["quality"]) == 0 for Row in Rows)
    Flux = [float(Row["Flux"]) for Row in Rows]
    Baseline = sum(Flux[:4] + Flux[8:]) / 8
    Dim = sum(Flux[4:8]) / 4
    assert abs(Dim / Baseline - .98) < .003, (Dim, Baseline)
    Session = Json.loads(Ask(Base, Route + "/finder", "POST", b"{}"))["url"].split("session=")[1]
    Saved = Json.loads(Ask(Base, "/analysis-sessions/" + Session))["state"]
    assert Saved["results"][0]["result"]["review_only"]
    print("ok: 12 FITS frames, four workers, 2% dimming, CSV and finder import", flush=True)
    return {"tls_period_days": Transit["period"], "tls_workers": 2, "fits_usable_frames": 12,
            "measured_dimming": 1 - Dim / Baseline, "dependency_versions": Versions}


#MARK: clean environment and a throwaway working directory
def Main():
    Parser = Argparse.ArgumentParser(description=__doc__)
    Parser.add_argument("app", type=Path)
    Parser.add_argument("--launcher", action="store_true", help="start the native window and read its server log")
    Args = Parser.parse_args()
    App = Args.app.resolve()
    Resources = App / "Contents/Resources"
    Samples = Resources / "Samples"
    with Tempfile.TemporaryDirectory(prefix="transit-packaged-test-") as Temp:
        Folder = Path(Temp)
        Environment = {Key: Value for Key, Value in Os.environ.items()
                       if Key not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
        Environment.update({"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "TRANSIT_FINDER_NO_BROWSER": "1",
                            "TRANSIT_FINDER_SESSION_CACHE_DIR": str(Folder / "Sessions"),
                            "TRANSIT_FINDER_IMAGE_DIR": str(Folder / "Images"),
                            "TRANSIT_FINDER_CACHE_DIR": str(Folder / "Cache"),
                            "TRANSIT_FINDER_LAUNCHER_NO_BROWSER": "1",
                            "TRANSIT_FINDER_LAUNCHER_DATA_DIR": str(Folder / "Launcher")})
        Executable = App / "Contents/MacOS/TransitFinderLauncher" if Args.launcher else Resources / "Server/TransitFinderServer"
        Messages = Queue.Queue()
        Output = []
        Process = Subprocess.Popen([str(Executable)], cwd=Folder, env=Environment,
                                   stdout=Subprocess.PIPE, stderr=Subprocess.STDOUT, text=True)
        def ReadLines():
            for Line in Process.stdout:
                Output.append(Line)
                Messages.put(Line)
        Threading.Thread(target=ReadLines, daemon=True).start()
        Base = None
        try:
            End = Clock.monotonic() + 90
            while Clock.monotonic() < End and Base is None:
                if Args.launcher:
                    FilePath = Folder / "Launcher/launcher.log"
                    Text = FilePath.read_text(errors="replace") if FilePath.exists() else ""
                else:
                    try:
                        Messages.get(timeout=.2)
                    except Queue.Empty:
                        pass
                    Text = "".join(Output)
                Match = Re.search(r"Transit Finder running at (http://127\.0\.0\.1:\d+/)", Text)
                if Match:
                    Base = Match[1].rstrip("/")
                    break
                if Process.poll() is not None:
                    raise AssertionError("packaged app exited: " + Text[-5000:])
                Clock.sleep(.1)
            if Base is None:
                raise AssertionError("packaged app never became ready: " + "".join(Output)[-5000:])
            Report = CheckRoutes(Base, Samples)
            print(Json.dumps(Report, indent=2), flush=True)
        finally:
            if Process.poll() is None:
                Process.send_signal(Signal.SIGTERM if Args.launcher else Signal.SIGINT)
                try:
                    Process.wait(timeout=15)
                except Subprocess.TimeoutExpired:
                    Process.kill()
                    Process.wait()
                    raise AssertionError("packaged app did not stop cleanly")
            if Base:
                try:
                    Urlopen(Base, timeout=.5)
                except Exception:
                    print("ok: local server stopped", flush=True)
                else:
                    raise AssertionError("packaged server was left running")
        assert Process.returncode == 0, (Process.returncode, "".join(Output)[-5000:])


if __name__ == "__main__":
    Main()
