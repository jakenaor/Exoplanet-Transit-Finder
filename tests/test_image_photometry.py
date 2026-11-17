"""Small fake camera frames, so these checks do not need the private dataset."""
import base64 as Base64
import copy as Copy
import csv as Csv
import json as Json
from pathlib import Path
import sys as Sys
import tempfile as Tempfile
import threading as Threading
import unittest as Unittest
from unittest import mock as Mock

import numpy as Np
from astropy.io import fits as Fits
from astropy.time import Time

Sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"))
import image_photometry as Photo
from image_jobs import ImageJobManager


#MARK: fake star thingies
class ImageFixture(Unittest.TestCase):
    def setUp(self):
        self.Temp = Tempfile.TemporaryDirectory(prefix="image-test-")
        self.Root = Path(self.Temp.name)
        self.Y, self.X = Np.indices((128, 176))
        self.Header = {"EXPTIME": 10., "INSTRUME": "test-camera", "GAIN": 120, "EGAIN": 2., "OFFSET": 50,
                       "XBINNING": 1, "YBINNING": 1, "XORGSUBF": 0, "YORGSUBF": 0,
                       "READMODE": "normal", "READOUTM": "normal", "CCD-TEMP": -10.,
                       "OBJECT": "test-field", "FILTER": "R", "TIMESYS": "UTC", "IMAGETYP": "LIGHT"}
        self.Darks = [self.Write("dark" + str(I) + ".fits", Np.full(self.X.shape, 500.) + Np.random.default_rng(I).normal(0, .05, self.X.shape), IMAGETYP="DARK") for I in range(3)]
        self.Options = Photo.ValidateOptions({"stars": [[48, 50], [112, 70]], "radius": 8, "inner": 12, "outer": 20, "tracking": 8, "workers": 4}, self.Darks[0])

    def tearDown(self):
        self.Temp.cleanup()

    def Write(self, Name, Data, **Header):
        Hdu = Fits.PrimaryHDU(Np.asarray(Data, dtype=Np.float32))
        for Key, Value in {**self.Header, **Header}.items():
            if Value is not None:
                Hdu.header[Key] = Value
        PathThing = self.Root / Name
        Hdu.writeto(PathThing, overwrite=True)
        return Photo.ImageInfo(PathThing, Name)

    def Light(self, Index, Factor=1, Transparency=1, Comparison=True, **Header):
        Dx, Dy = Index * .23, Index * -.12
        Target = 1200 * Factor * Transparency * Np.exp(-((self.X - 48 - Dx) ** 2 + (self.Y - 50 - Dy) ** 2) / 8)
        Comp = 1700 * Transparency * Np.exp(-((self.X - 112 - Dx) ** 2 + (self.Y - 70 - Dy) ** 2) / 8) if Comparison else 0
        Data = 600 + Target + Comp + Np.random.default_rng(Index + 100).normal(0, .5, self.X.shape)
        return self.Write("light" + str(Index) + ".fits", Data, **{"DATE-OBS": f"2026-11-16T00:{Index:02d}:00", **Header})

    def Run(self, Frames, Options=None):
        return Photo.BuildLightCurve(Frames, self.Darks, Options or self.Options, self.Root / "output", lambda *Args: None)


#MARK: actual flux changes should survive the pipeline
class PhotometryTests(ImageFixture):
    def testDriftingStarsAndTransparencyKeepKnownRelativeFlux(self):
        Values = Np.array([1., .98, .96, 1.02, 1.01, .99])
        Frames = [self.Light(I, Factor=Value, Transparency=.8 + I * .07) for I, Value in enumerate(Values)]
        Result = self.Run(Frames)
        self.assertEqual(Result["usable_frames"], len(Values))
        Np.testing.assert_allclose([R["Flux"] for R in Result["preview"]], Values / Np.median(Values), atol=.002)
        self.assertEqual(Result["provenance"]["workers"], 4)
        with (self.Root / "output/lightcurve.csv").open() as File:
            Rows = list(Csv.DictReader(File))
        self.assertEqual(len(Rows), len(Frames))
        self.assertTrue(all(float(R["flux_err"]) > 0 for R in Rows))
        self.assertAlmostEqual(float(Rows[1]["Time"]), 1 / 1440, places=8)
        Meta = Json.loads((self.Root / "output/metadata.json").read_text())
        self.assertFalse(Meta["flat_field_applied"])
        self.assertFalse(Meta["dark_scaling_applied"])
        self.assertEqual(Meta["time_scale"], "unknown")
        self.assertIn("fixed comparison ensemble", Meta["method"])
        self.assertTrue(all(len(R["stars"]) == 2 for R in Meta["measurements"]))

    def testTargetOnlyKeepsTransparencyAndLabelsTheMissingCorrection(self):
        Options = {**self.Options, "stars": [self.Options["stars"][0]]}
        Frames = [self.Light(I, Transparency=.8 + I * .1) for I in range(5)]
        Result = self.Run(Frames, Options)
        self.assertEqual(Result["usable_frames"], 5)
        self.assertGreater(Np.ptp([Row["Flux"] for Row in Result["preview"]]), .35)
        self.assertIn("target-only", Result["provenance"]["method"])
        self.assertTrue(any("no comparison-star correction" in W for W in Result["warnings"]))
        Meta = Json.loads((self.Root / "output/metadata.json").read_text())
        self.assertEqual(Meta["method"], Result["provenance"]["method"])
        self.assertTrue(all(Row["comparison_rate"] is None for Row in Meta["measurements"]))

    def testKnownRotationChangeNeedsASeparateRun(self):
        Frames = [self.Light(0, ROTATOR=0), self.Light(1, ROTATOR=180)]
        with self.assertRaisesRegex(ValueError, "mixed ROTATOR"):
            self.Run(Frames)
        self.assertEqual(len(Photo.MatchingDarks(Frames[0], self.Darks)), 3)
        Large = Photo.ValidateOptions({"stars": [[500, 500]], "radius": 89, "inner": 130, "outer": 180}, {"width": 1000, "height": 1000})
        self.assertEqual(Large["radius"], 89)

    def testFinderImportKeepsOneOutputGeneration(self):
        import hashlib as Hashlib
        from types import SimpleNamespace
        from image_jobs import HandleImageRequest
        from parsers import ParseCsvBytes
        Manager = ImageJobManager(Directory=self.Root / "jobs")
        try:
            Id = Manager.create()["id"]
            Run = Manager.get(Id)
            First, Second = self.Root / "first", self.Root / "second"
            for Folder in (First, Second):
                Folder.mkdir()
                (Folder / "lightcurve.csv").write_text("Time,Flux\n0,1\n.01,.9\n.02,1\n")
                (Folder / "metadata.json").write_text(Json.dumps({"generation": Folder.name}))
            Run.update(status="completed", result={"output_directory": str(First), "provenance": {"generation": "first"}})
            def ParseAndRemeasure(*Args, **Kwargs):
                Data = ParseCsvBytes(*Args, **Kwargs)
                Run["result"] = {"output_directory": str(Second), "provenance": {"generation": "second"}}
                return Data
            Cache = Mock.Mock()
            Handler = SimpleNamespace(path="/image-runs/" + Id + "/finder",
                                      server=SimpleNamespace(ImageJobs=Manager, RunCache=Cache), WriteJson=Mock.Mock())
            def Inspect(TimeThing, FluxThing, Options):
                return {"input_metadata": Options["_input_metadata"], "flux": list(FluxThing)}
            with Mock.patch("parsers.ParseCsvBytes", side_effect=ParseAndRemeasure), Mock.patch("analysis.RunCurve", side_effect=Inspect), Mock.patch("analysis_jobs.AnnotateAnalysisResult", side_effect=lambda Result, *Args: Result):
                self.assertTrue(HandleImageRequest(Handler, "POST"))
            State = Cache.save.call_args.args[1]
            Result = State["results"][0]["result"]
            self.assertEqual(Result["flux"], [1., .9, 1.])
            Provenance = Result["input_metadata"]["photometry"]
            self.assertEqual(Provenance["generation"], "first")
            self.assertEqual(Provenance["metadata_file"], str(First / "metadata.json"))
            self.assertEqual(Provenance["metadata_sha256"], Hashlib.sha256((First / "metadata.json").read_bytes()).hexdigest())
            Run.update(started=10., finished=20.)
            with Mock.patch("image_jobs.Clock.monotonic", return_value=100.):
                self.assertEqual(Manager.public(Run)["elapsed_seconds"], 10.)
        finally:
            Manager.shutdown()

    def testLostComparisonRejectsRatioButKeepsTargetMeasurement(self):
        Result = self.Run([self.Light(0, Comparison=False)])
        self.assertEqual(Result["usable_frames"], 0)
        Meta = Json.loads((self.Root / "output/metadata.json").read_text())
        Row = Meta["measurements"][0]
        self.assertIsNone(Row["Flux"])
        self.assertEqual(Row["quality"], 1)
        self.assertGreater(Row["target_rate"], 0)
        self.assertGreater(Row["target_rate_error"], 0)
        self.assertTrue(Row["qc_flags"])

    def testDarksMatchShortExposuresAndNumericCameraSettings(self):
        Frame, Dark = Copy.deepcopy(self.Darks[0]), Copy.deepcopy(self.Darks[1])
        Frame["exposure"] = .001
        Dark["exposure"] = .00100000005
        Dark["header"]["GAIN"] = 120.0
        self.assertEqual(len(Photo.MatchingDarks(Frame, [Dark])), 1)
        for Exposure in (.002, .0001, 0):
            Dark["exposure"] = Exposure
            self.assertEqual(Photo.MatchingDarks(Frame, [Dark]), [])
        Dark["exposure"] = .001
        Dark["header"]["READOUTM"] = "different"
        self.assertEqual(Photo.MatchingDarks(Frame, [Dark]), [])

    def testClockOptionsAndSeparateDateTimeHeaders(self):
        Frame = self.Light(0)
        Start, _ = Photo.FrameClock(Frame, "start")
        Mid, _ = Photo.FrameClock(Frame, "midpoint")
        self.assertAlmostEqual((Start - Mid) * 86400, 5, delta=.0001)
        Frame["header"]["DATE-OBS"] = "2026-11-16"
        with self.assertRaisesRegex(ValueError, "DATE_WITHOUT_TIME"):
            Photo.FrameClock(Frame, "start")
        Frame["header"]["TIME-OBS"] = "00:00:00"
        self.assertAlmostEqual(Photo.FrameClock(Frame, "start")[0], Start)
        Frame["header"]["TIMESYS"] = "TAI"
        Expected = float(Time("2026-11-16T00:00:00", scale="tai").utc.jd) + 5 / 86400
        self.assertAlmostEqual(Photo.FrameClock(Frame, "start")[0], Expected)
        Frame["header"]["DATE-AVG"] = "2026-11-16T00:00:07"
        self.assertEqual(Photo.FrameClock(Frame, "start"), Photo.FrameClock(Frame, "midpoint"))

    def testFailedDuplicateDoesNotStealTheValidTimestamp(self):
        Bad = self.Write("a_bad.fits", Np.full(self.X.shape, 600.), **{"DATE-OBS": "2026-11-16T00:00:00"})
        Result = self.Run([Bad, self.Light(0), self.Light(1)])
        self.assertEqual(Result["usable_frames"], 2)
        self.assertEqual(sum(R["quality"] for R in Result["preview"]), 1)

    def testMissingGainIsNotInventedAndKnownSetupChangesFail(self):
        Frames = [self.Light(0, EGAIN=None), self.Light(1, EGAIN=None)]
        Result = self.Run(Frames)
        self.assertTrue(any("shot noise" in Warning for Warning in Result["warnings"]))
        Changed = Copy.deepcopy(Frames[1])
        Changed["header"]["GAIN"] = 121
        with self.assertRaisesRegex(ValueError, "mixed GAIN"):
            self.Run([Frames[0], Changed])

    def testUnsignedPreviewAndTableAndCorrectedImageGuards(self):
        Data = (Np.arange(32 * 48).reshape(32, 48) + 33000).astype(Np.uint16)
        FilePath = self.Root / "unsigned.fits"
        Fits.PrimaryHDU(Data).writeto(FilePath)
        Info = Photo.ImageInfo(FilePath)
        Np.testing.assert_equal(Photo.ReadPatch(Info, (0, 0, 48, 32)), Data)
        Preview = Photo.MakePreview(Info)
        self.assertTrue(Base64.b64decode(Preview["png"]).startswith(b"\x89PNG"))
        Fits.HDUList([Fits.PrimaryHDU(), Fits.BinTableHDU.from_columns([Fits.Column(name="TIME", format="D", array=[1., 2.])])]).writeto(self.Root / "table.fits")
        with self.assertRaisesRegex(ValueError, "no 2D image"):
            Photo.ImageInfo(self.Root / "table.fits")
        with self.assertRaisesRegex(ValueError, "already marked"):
            self.Write("corrected.fits", Data, CALSTAGE="DARK_ONLY")

    def testEightBitRailAndCancelledWork(self):
        Frame = self.Light(0)
        FilePath = self.Root / "eight.fits"
        Y, X = Np.indices((128, 176))
        Data = (15 + 100 * Np.exp(-((X - 48) ** 2 + (Y - 50) ** 2) / 8)).astype(Np.uint8)
        Hdu = Fits.PrimaryHDU(Data)
        Hdu.header["EXPTIME"] = 10
        Hdu.writeto(FilePath)
        Eight = Photo.ImageInfo(FilePath)
        DarkFile = self.Root / "eight-dark.fits"
        Hdu = Fits.PrimaryHDU(Np.full(Data.shape, 5, dtype=Np.uint8))
        Hdu.header["EXPTIME"] = 10
        Hdu.writeto(DarkFile)
        Photo.MeasureStar(Eight, [Photo.ImageInfo(DarkFile)], (48, 50), self.Options)
        Stop = Threading.Event()
        Stop.set()
        with self.assertRaises(InterruptedError):
            Photo.BuildLightCurve([Frame], self.Darks, self.Options, self.Root / "cancelled", lambda *Args: None, Stop)

    def testOptionBoundsAndThreadStartFailureDoNotLockTheQueue(self):
        for Changes in ({"workers": 5}, {"radius": 12, "inner": 8}, {"stars": [[48, 50], [48, 50]]}):
            with self.assertRaises(ValueError):
                Photo.ValidateOptions({"stars": [[48, 50]], **Changes}, self.Darks[0])
        Manager = ImageJobManager(Directory=self.Root / "jobs")
        try:
            Job = Manager.create()
            Run = Manager.get(Job["id"])
            Run["science"], Run["dark"] = [self.Light(0)], self.Darks
            with Mock.patch("image_jobs.Threading.Thread.start", side_effect=RuntimeError("thread unavailable")):
                with self.assertRaises(RuntimeError):
                    Manager.start(Job["id"], self.Options)
            self.assertTrue(Manager.WorkSlot.acquire(blocking=False))
            Manager.WorkSlot.release()
        finally:
            Manager.shutdown()


if __name__ == "__main__":
    Unittest.main()
