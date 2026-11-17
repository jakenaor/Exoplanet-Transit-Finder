"""Real HTTP round trips for the image tab, using tiny fake camera files."""
import csv as Csv
import hashlib as Hashlib
from http.server import ThreadingHTTPServer
import io as Io
import json as Json
from pathlib import Path
import threading as Threading
import time as Clock
from urllib.error import HTTPError
from urllib.request import Request, urlopen as Urlopen

from test_http_integration import QuietHandler
from test_image_photometry import ImageFixture
from analysis_jobs import AnalysisJobManager
from image_jobs import ImageJobManager
from session_cache import SessionCacheManager


#MARK: own server and temp folder, leave the actual app alone
class ImageRouteTests(ImageFixture):
    def setUp(self):
        super().setUp()
        self.Server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        self.Server.ImageJobs = ImageJobManager(Directory=self.Root / "tables")
        self.Server.AnalysisJobs = AnalysisJobManager()
        self.Server.RunCache = SessionCacheManager(DefaultDirectory=self.Root / "sessions")
        self.Thread = Threading.Thread(target=self.Server.serve_forever, daemon=True)
        self.Thread.start()
        self.Base = f"http://127.0.0.1:{self.Server.server_port}"

    def tearDown(self):
        self.Server.shutdown()
        self.Server.ImageJobs.shutdown()
        self.Server.AnalysisJobs.shutdown()
        self.Server.server_close()
        self.Thread.join(timeout=3)
        super().tearDown()

    def Ask(self, Route, Method="GET", Data=None, Mime="application/json"):
        Query = Request(self.Base + Route, method=Method, data=Data, headers={"Content-Type": Mime})
        try:
            Reply = Urlopen(Query, timeout=20)
        except HTTPError as Exc:
            Reply = Exc
        with Reply:
            return Reply.status, Reply.read()

    def Upload(self, Id, Frame, Kind):
        Boundary = "tiny-camera-file-test"
        Raw = Path(Frame["path"]).read_bytes()
        Body = (f'--{Boundary}\r\nContent-Disposition: form-data; name="image"; filename="{Frame["name"]}"\r\n'
                'Content-Type: application/fits\r\n\r\n').encode() + Raw + f"\r\n--{Boundary}--\r\n".encode()
        Status, Reply = self.Ask("/image-runs/" + Id + "/frames?kind=" + Kind, "POST", Body, "multipart/form-data; boundary=" + Boundary)
        self.assertEqual(Status, 200, Reply)

    def WaitForTable(self, Route):
        Deadline = Clock.monotonic() + 10
        while Clock.monotonic() < Deadline:
            Status, Reply = self.Ask(Route)
            self.assertEqual(Status, 200, Reply)
            Run = Json.loads(Reply)
            if Run["status"] not in ("running", "cancelling"):
                self.assertEqual(Run["status"], "completed", Run)
                return Run["result"]
            Clock.sleep(.02)
        self.fail("tiny image run did not finish")

    def testUploadPreviewRemeasureAndImportKeepOutputsAndProvenance(self):
        self.assertEqual(self.Ask("/images")[0], 200)
        Frames = [self.Light(I, Factor=1 - .02 * I, Transparency=.8 + .1 * I) for I in range(3)]
        Originals = {F["path"]: Hashlib.sha256(Path(F["path"]).read_bytes()).hexdigest() for F in Frames + self.Darks}
        Status, Reply = self.Ask("/image-runs", "POST", b"{}")
        self.assertEqual(Status, 201, Reply)
        Id = Json.loads(Reply)["id"]
        Route = "/image-runs/" + Id
        for Kind, Collection in (("science", Frames), ("dark", self.Darks)):
            for Frame in Collection:
                self.Upload(Id, Frame, Kind)
        Status, Reply = self.Ask(Route + "/preview")
        self.assertEqual(Status, 200, Reply)
        Preview = Json.loads(Reply)
        self.assertTrue(Preview["png"].startswith("iVBOR"))
        self.assertEqual(Preview["image_width"], 176)
        Status, Reply = self.Ask(Route + "/process", "POST", Json.dumps(self.Options).encode())
        self.assertEqual(Status, 202, Reply)
        First = self.WaitForTable(Route)
        self.assertEqual(First["usable_frames"], 3)
        Status, CsvBytes = self.Ask(Route + "/lightcurve.csv")
        self.assertEqual(Status, 200, CsvBytes)
        Rows = list(Csv.DictReader(Io.StringIO(CsvBytes.decode())))
        self.assertEqual(len(Rows), 3)
        self.assertAlmostEqual(float(Rows[1]["Time"]), 1 / 1440, places=8)
        self.assertGreater(float(Rows[0]["Flux"]), float(Rows[-1]["Flux"]))
        Meta = Json.loads(self.Ask(Route + "/metadata.json")[1])
        self.assertEqual(Meta["workers"], 4)
        self.assertFalse(Meta["flat_field_applied"])
        self.assertEqual(Meta["sources"][0]["sha256"], Originals[Frames[0]["path"]])
        FirstPath = Path(First["output_directory"]) / "lightcurve.csv"
        Status, Reply = self.Ask(Route + "/process", "POST", Json.dumps(self.Options).encode())
        self.assertEqual(Status, 202, Reply)
        Second = self.WaitForTable(Route)
        self.assertNotEqual(First["output_directory"], Second["output_directory"])
        self.assertEqual(FirstPath.read_bytes(), CsvBytes)
        Sessions = []
        for _ in range(2):
            Status, Reply = self.Ask(Route + "/finder", "POST", b"{}")
            self.assertEqual(Status, 200, Reply)
            Url = Json.loads(Reply)["url"]
            Session = Url.split("session=")[1]
            Sessions.append(Session)
            Status, Reply = self.Ask("/analysis-sessions/" + Session)
            self.assertEqual(Status, 200, Reply)
            State = Json.loads(Reply)["state"]
            Result = State["results"][0]["result"]
            self.assertTrue(Result["review_only"])
            self.assertEqual(Result["input_metadata"]["time_format"].lower(), "relative")
            self.assertEqual(Result["input_metadata"]["photometry"]["image_run_id"], Id)
            self.assertFalse(Result["input_metadata"]["photometry"]["flat_field_applied"])
            self.assertIsNone(State["detection_options"]["exposureSeconds"])
        self.assertNotEqual(*Sessions)
        for FilePath, Digest in Originals.items():
            self.assertEqual(Hashlib.sha256(Path(FilePath).read_bytes()).hexdigest(), Digest)
