"""Disk-backed image uploads and bounded photometry jobs for the second tab."""
import cgi as Cgi
import hashlib as Hashlib
import json as Json
from pathlib import Path
import os as Os
import re as Re
import shutil as Shutil
import tempfile as Tempfile
import threading as Threading
import time as Clock
import uuid as Uuid
from urllib.parse import urlparse as Urlparse, parse_qs as ParseQs

from image_photometry import ImageInfo, MakePreview, ValidateOptions, BuildLightCurve


#MARK: uploaded images live on disk
class ImageJobManager:
    def __init__(self, Directory=None):
        self.Directory = Path(Directory or Os.environ.get("TRANSIT_FINDER_IMAGE_DIR") or Path.home() / "Desktop/Current/Exoplanet Transit Finder Stuff/Image Light Curves")
        if not self.Directory.is_absolute():
            raise ValueError("The image output folder must be an absolute path.")
        self.Scratch = Tempfile.TemporaryDirectory(prefix="transit-image-uploads-")
        self.Runs = {}
        self.Lock = Threading.RLock()
        self.WorkSlot = Threading.Lock()

    def create(self):
        with self.Lock:
            if len(self.Runs) >= 8:
                Old = next((Key for Key, Run in self.Runs.items() if Run["status"] not in ("running", "cancelling") and not Run["uploading"]), None)
                if Old is None:
                    raise ValueError("Finish or cancel an existing image run first.")
                Shutil.rmtree(self.Runs[Old]["folder"], ignore_errors=True)
                del self.Runs[Old]
            Id = Uuid.uuid4().hex
            Folder = Path(self.Scratch.name) / Id
            Folder.mkdir()
            self.Runs[Id] = {"id": Id, "folder": Folder, "science": [], "dark": [], "status": "uploading",
                             "uploading": 0, "bytes": 0, "completed": 0, "current_file": "", "error": None,
                             "result": None, "preview": None, "started": None, "finished": None, "thread": None, "stop": Threading.Event()}
            return self.public(self.Runs[Id])

    def get(self, Id):
        if not Re.fullmatch(r"[a-f0-9]{32}", Id or "") or Id not in self.Runs:
            raise ValueError("Image run expired or unavailable. Reselect the images; completed output tables stay on disk.")
        return self.Runs[Id]

    def public(self, Run):
        return {"id": Run["id"], "status": Run["status"], "science_count": len(Run["science"]),
                "dark_count": len(Run["dark"]), "uploaded_bytes": Run["bytes"], "completed": Run["completed"],
                "total": len(Run["science"]), "current_file": Run["current_file"], "error": Run["error"],
                "elapsed_seconds": round((Run["finished"] or Clock.monotonic()) - Run["started"], 1) if Run["started"] else 0,
                "result": Run["result"]}

    #MARK: one file at a time, no giant upload bundle
    def upload(self, Id, Kind, Item):
        if Kind not in ("science", "dark"):
            raise ValueError("Choose science or dark images.")
        Name = str(getattr(Item, "filename", "image.fits")).replace("\\", "/").split("/")[-1]
        if Path(Name).suffix.lower() not in (".fits", ".fit", ".fts"):
            raise ValueError("Upload individual .fits, .fit or .fts images, not ZIP archives.")
        with self.Lock:
            Run = self.get(Id)
            if Run["status"] != "uploading" or len(Run[Kind]) >= (128 if Kind == "dark" else 10000):
                raise ValueError("This run cannot accept more images (up to 128 darks and 10,000 science frames).")
            Run["uploading"] += 1
            Destination = Run["folder"] / (Uuid.uuid4().hex + ".fits")
        Size, Digest = 0, Hashlib.sha256()
        try:
            with Destination.open("wb") as File:
                while True:
                    Chunk = Item.file.read(1024 * 1024)
                    if not Chunk:
                        break
                    Size += len(Chunk)
                    if Size > 512 * 1024 ** 2 or Shutil.disk_usage(Run["folder"]).free < 512 * 1024 ** 2:
                        raise ValueError("Image is too large or the temporary disk has less than 512 MiB free.")
                    File.write(Chunk)
                    Digest.update(Chunk)
            Info = ImageInfo(Destination, Name)
            Info.update(sha256=Digest.hexdigest(), size_bytes=Size, uploaded_role=Kind)
            with self.Lock:
                if Run["status"] != "uploading" or sum(Value["bytes"] for Value in self.Runs.values()) + Size > 20 * 1024 ** 3:
                    raise ValueError("Upload cancelled or the 20 GiB staging limit was reached. Restart the app to clear staged copies.")
                Run[Kind].append(Info)
                Run["bytes"] += Size
            return self.public(Run)
        except BaseException:
            Destination.unlink(missing_ok=True)
            raise
        finally:
            with self.Lock:
                Run["uploading"] -= 1

    def preview(self, Id):
        with self.Lock:
            Run = self.get(Id)
            if not Run["science"]:
                raise ValueError("Upload a science image first.")
            Reference = Run["science"][0]
        if Run["preview"] is None:
            Run["preview"] = MakePreview(Reference)
        return Run["preview"]

    #MARK: four is the ceiling, even if several tabs are open
    def start(self, Id, Values):
        with self.Lock:
            Run = self.get(Id)
            if Run["status"] not in ("uploading", "completed", "failed", "cancelled") or Run["uploading"]:
                raise ValueError("Finish uploads before starting a new image run.")
            if not Run["science"] or not Run["dark"]:
                raise ValueError("Upload science images and dark frames first.")
            Options = ValidateOptions(Values, Run["science"][0])
            if not self.WorkSlot.acquire(blocking=False):
                raise ValueError("Another image run is processing. Wait or cancel it first.")
            Run["stop"].clear()
            Run.update(status="running", started=Clock.monotonic(), finished=None, completed=0, current_file="", result=None, error=None)
            Output = self.Directory / Id / Uuid.uuid4().hex[:12]
            def Progress(Done, Total, Name):
                with self.Lock:
                    Run.update(completed=Done, current_file=Name)
            def Work():
                try:
                    Result = BuildLightCurve(Run["science"], Run["dark"], Options, Output, Progress, Run["stop"])
                    with self.Lock:
                        Run.update(result=Result, status="completed")
                except InterruptedError:
                    with self.Lock:
                        Run.update(status="cancelled", error="Image processing cancelled.")
                except Exception as Exc:
                    with self.Lock:
                        Run.update(status="failed", error=str(Exc))
                finally:
                    with self.Lock:
                        Run["finished"] = Clock.monotonic()
                    self.WorkSlot.release()
            Run["thread"] = Threading.Thread(target=Work, daemon=True, name="image-photometry")
            try:
                Run["thread"].start()
            except BaseException:
                Run.update(status="failed", error="Could not start the image worker.", finished=Clock.monotonic(), thread=None)
                self.WorkSlot.release()
                raise
            return self.public(Run)

    def cancel(self, Id):
        with self.Lock:
            Run = self.get(Id)
            if Run["status"] in ("uploading", "running", "cancelling"):
                Run["stop"].set()
                Run["status"] = "cancelling" if Run["thread"] else "cancelled"
            return self.public(Run)

    def output(self, Id, Name):
        with self.Lock:
            Run = self.get(Id)
            if Run["status"] != "completed" or Name not in ("lightcurve.csv", "metadata.json"):
                raise ValueError("That output is not ready.")
            return Path(Run["result"]["output_directory"]) / Name

    def shutdown(self):
        for Run in list(self.Runs.values()):
            Run["stop"].set()
        for Run in list(self.Runs.values()):
            if Run["thread"]:
                Run["thread"].join(timeout=5)
        if not any(Run["thread"] and Run["thread"].is_alive() for Run in self.Runs.values()):
            self.Scratch.cleanup()


#MARK: image routes stay separate from period searches
ManagerLock = Threading.Lock()


def HandleImageRequest(Handler, Method):
    Parsed = Urlparse(Handler.path)
    if Parsed.path == "/images" and Method == "GET":
        Handler.WriteFile(Path(__file__).parent / "static/images.html", "text/html; charset=utf-8")
        return True
    if Parsed.path != "/image-runs" and not Parsed.path.startswith("/image-runs/"):
        return False
    try:
        with ManagerLock:
            if not hasattr(Handler.server, "ImageJobs"):
                Handler.server.ImageJobs = ImageJobManager()
        Manager = Handler.server.ImageJobs
        Parts = Parsed.path.strip("/").split("/")
        if len(Parts) == 1 and Method == "POST":
            Handler.ReadJsonRequest(1024)
            Handler.WriteJson(Manager.create(), Status=201)
            return True
        if len(Parts) < 2:
            raise ValueError("Choose an image run.")
        Id = Parts[1]
        if len(Parts) == 2 and Method == "GET":
            with Manager.Lock:
                Handler.WriteJson(Manager.public(Manager.get(Id)))
        elif len(Parts) == 2 and Method == "DELETE":
            Handler.WriteJson(Manager.cancel(Id))
        elif len(Parts) == 3 and Parts[2] == "frames" and Method == "POST":
            Length = int(Handler.headers.get("Content-Length", "0"))
            if not 0 < Length <= 513 * 1024 ** 2:
                raise ValueError("Upload one FITS image at a time, at most 512 MiB each.")
            Form = Cgi.FieldStorage(fp=Handler.rfile, headers=Handler.headers,
                environ={"REQUEST_METHOD": "POST", "CONTENT_TYPE": Handler.headers.get("Content-Type", ""), "CONTENT_LENGTH": str(Length)})
            Item = Form["image"] if "image" in Form else None
            if Item is None or not getattr(Item, "file", None) or isinstance(Item, list):
                raise ValueError("Choose one FITS image for this upload.")
            Kind = ParseQs(Parsed.query).get("kind", [""])[0]
            Handler.WriteJson(Manager.upload(Id, Kind, Item))
        elif len(Parts) == 3 and Parts[2] == "preview" and Method == "GET":
            Handler.WriteJson(Manager.preview(Id))
        elif len(Parts) == 3 and Parts[2] == "process" and Method == "POST":
            Handler.WriteJson(Manager.start(Id, Handler.ReadJsonRequest(16384)), Status=202)
        elif len(Parts) == 3 and Parts[2] in ("lightcurve.csv", "metadata.json") and Method == "GET":
            Handler.WriteFile(Manager.output(Id, Parts[2]), "text/csv; charset=utf-8" if Parts[2].endswith(".csv") else "application/json")
        elif len(Parts) == 3 and Parts[2] == "finder" and Method == "POST":
            # reset timing and exposure assumptions when importing the generated table.
            from analysis import RunCurve
            from analysis_jobs import AnnotateAnalysisResult
            from parsers import ParseCsvBytes
            # grab one finished generation. a remeasure can start during parsing.
            with Manager.Lock:
                FilePath = Manager.output(Id, "lightcurve.csv")
                MetadataPath = Manager.output(Id, "metadata.json")
                Provenance = dict(Manager.get(Id)["result"]["provenance"])
            Data = ParseCsvBytes(FilePath.read_bytes(), ReturnMetadata=True, TimeFormat="relative", TimeScale="unknown", TimeUnit="days")
            Digest = Hashlib.sha256()
            with MetadataPath.open("rb") as File:
                for Chunk in iter(lambda: File.read(1024 * 1024), b""):
                    Digest.update(Chunk)
            Data["input_metadata"].update(flux_unit="relative median-normalized flux", photometry={
                **Provenance, "image_run_id": Id, "metadata_file": str(MetadataPath), "metadata_sha256": Digest.hexdigest()})
            Options = {"inspection_only": True, "_input_metadata": Data["input_metadata"], "_cleaning_report": Data["cleaning"],
                       "_flux_uncertainty": Data["flux_uncertainty"], "_exposure_seconds": Data.get("exposure_seconds")}
            Result = AnnotateAnalysisResult(RunCurve(Data["time"], Data["flux"], Options), Options, "image-lightcurve.csv")
            Session = "images_" + Uuid.uuid4().hex
            State = {"ui_schema_version": 2, "results": [{"file_name": "image-lightcurve.csv", "result": Result}],
                     "current_view": "raw", "current_batch_index": 0,
                     "detection_options": {"inspectOnly": True, "csvTimeFormat": "relative", "csvTimeScale": "unknown", "csvTimeUnit": "days", "exposureSeconds": None}}
            Handler.server.RunCache.save(Session, State)
            Handler.WriteJson({"url": "/?session=" + Session})
        else:
            Handler.WriteJson({"error": "Image route not found."}, Status=404)
    except (BrokenPipeError, ConnectionResetError):
        pass
    except Exception as Exc:
        Handler.WriteJson({"error": str(Exc)}, Status=400)
    return True
