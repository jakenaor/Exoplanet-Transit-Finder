"""Short uploads stay inspectable without turning into search results."""
import copy as Copy
import io as Io
from pathlib import Path
import sys as Sys
import tempfile as Tempfile
from types import SimpleNamespace
import unittest as Unittest

import numpy as Np

APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
Sys.path.insert(0, str(APP_DIR))

from parsers import CleanLightCurveArrays, ParseCsvBytes, ParseFitsBytes, ReadCurveUpload
from session_cache import SessionCache, ValidateResult


def InspectionResult(Count=3):
    Times = list(range(Count))
    Flux = [10.0 + I for I in Times]
    return {
        "review_only": True, "analysis_mode": "inspection", "search_status": "not_run",
        "review_reason": "Too few samples for period search.",
        "search_reason": "Period search requires at least 50 samples.",
        "search_requirements": {"minimum_samples": 50, "usable_samples": Count},
        "total_points": Count, "time_reference": 2457000.0,
        "period": None, "transits": [], "signals": [],
        "predicted_windows": [], "observed_events": [], "exploratory_dips": [],
        "planet_assessment": None, "fit_quality": None, "diagnostics": None,
        "transit_model": None, "phase_folded": None, "transit_stack": None,
        "model_comparison": None, "periodogram": None,
        "plot": {"time": Times, "raw_flux": Flux, "smooth_flux": Flux.copy(),
                 "flux_uncertainty": [None] + [.1] * (Count - 1),
                 "exposure_seconds": [None] + [30.0] * (Count - 1)},
        "domain": {"time_min": 0, "time_max": max(Count - 1, 1)},
        "raw_domain": {"flux_min": 9.0, "flux_max": 10.0 + Count},
        "clean_domain": {"flux_min": 9.0, "flux_max": 10.0 + Count},
        "result_schema_version": 2, "analyzed_at": "2026-11-17T00:00:00+00:00",
        "provenance": {"result_schema_version": 2, "analysis_version": "test",
                       "app_version": "test", "analyzed_at": "2026-11-17T00:00:00+00:00",
                       "dependency_versions": {}, "effective_settings": {}},
    }


class ShortCurveParserTests(Unittest.TestCase):
    def testTwoThreeAndFortyNineRowsRetainOriginalSamplesAndMetadata(self):
        for Count in (2, 3, 49):
            with self.subTest(rows=Count):
                Rows = ["Time,Flux,flux_err,exposure_seconds,quality"]
                Rows += [f"{I * 60},{20 + I},{.1 + I / 1000},30,0" for I in reversed(range(Count))]
                Rows += ["0,999,9,99,0", "bad,1,.1,30,0", "nan,1,.1,30,0", "99999,1,.1,30,1"]
                Parsed = ParseCsvBytes("\n".join(Rows).encode(), ReturnMetadata=True,
                                       TimeFormat="relative", TimeUnit="seconds", TimeScale="unknown")
                Np.testing.assert_allclose(Parsed["time"], Np.arange(Count) / 1440)
                Np.testing.assert_equal(Parsed["flux"], 20 + Np.arange(Count))
                Np.testing.assert_allclose(Parsed["flux_uncertainty"], .1 + Np.arange(Count) / 1000)
                Np.testing.assert_equal(Parsed["exposure_seconds"], Np.full(Count, 30.0))
                Cleaning = Parsed["cleaning"]
                self.assertEqual(Cleaning["retained_rows"], Count)
                self.assertTrue(Cleaning["counts_reconcile"])
                self.assertTrue(Cleaning["sorting_applied"])
                for Key in ("duplicate_rows", "invalid_numeric_rows", "nonfinite_rows", "quality_excluded_rows"):
                    self.assertEqual(Cleaning[Key], 1)
                self.assertEqual(Parsed["input_metadata"]["time_unit"], "days")

    def testZeroOneDuplicateAndRejectedOnlyCurvesStillFail(self):
        for Times, Flux, Quality in (([], [], None), ([1], [1], None),
                                     ([1, 1], [1, 2], None), ([0, 1], [1, 1], [1, 1]),
                                     ([0, 1], [Np.nan, 1], None)):
            with self.subTest(times=Times, quality=Quality):
                with self.assertRaisesRegex(ValueError, "zero time span"):
                    CleanLightCurveArrays(Times, Flux, Quality=Quality)

    def testLegacyTupleReturnWorksForTwoSamples(self):
        Times, Flux = ParseCsvBytes(b"Time,Flux\n2,20\n1,10\n")
        Np.testing.assert_equal(Times, [1, 2])
        Np.testing.assert_equal(Flux, [10, 20])

    def testShortFitsTableAndExtensionlessUploadRemainSupported(self):
        from astropy.io import fits as Fits
        Columns = [Fits.Column(name="TIME", format="D", array=[2., 1., 0.]),
                   Fits.Column(name="FLUX", format="D", array=[12., 11., 10.]),
                   Fits.Column(name="QUALITY", format="J", array=[0, 0, 1]),
                   Fits.Column(name="FLUX_ERR", format="D", array=[.2, .1, .3]),
                   Fits.Column(name="exposure_seconds", format="D", array=[30., 30., 30.])]
        Output = Io.BytesIO()
        Fits.HDUList([Fits.PrimaryHDU(), Fits.BinTableHDU.from_columns(Columns)]).writeto(Output)
        Raw = Output.getvalue()
        for Parsed in (ParseFitsBytes(Raw, ReturnMetadata=True),
                       ReadCurveUpload(SimpleNamespace(filename="extensionless", file=Io.BytesIO(Raw)), ReturnMetadata=True)):
            Np.testing.assert_equal(Parsed["time"], [1, 2])
            Np.testing.assert_equal(Parsed["flux"], [11, 12])
            Np.testing.assert_equal(Parsed["flux_uncertainty"], [.1, .2])
            self.assertEqual(Parsed["cleaning"]["quality_excluded_rows"], 1)

    def testJsonSidecarUploadExplainsTheSupportedInputs(self):
        for Name in ("target.json", "target.JSON"):
            with self.subTest(filename=Name):
                Item = SimpleNamespace(filename=Name, file=Io.BytesIO(b'{"time_format":"relative"}'))
                with self.assertRaisesRegex(ValueError, "JSON sidecar.*CSV or FITS"):
                    ReadCurveUpload(Item)


class InspectionCacheTests(Unittest.TestCase):
    def testShortInspectionRoundTripsWithoutAddingScientificFindings(self):
        with Tempfile.TemporaryDirectory() as Folder:
            Cache = SessionCache(Folder)
            for Count in (2, 3, 49):
                with self.subTest(rows=Count):
                    Result = InspectionResult(Count)
                    State = {"results": [{"file_name": "short.csv", "result": Result}]}
                    Cache.save("inspection_12345678", State)
                    Loaded = Cache.load("inspection_12345678")["state"]["results"][0]["result"]
                    self.assertEqual(Loaded, Result)
                    self.assertIsNone(Loaded["planet_assessment"])
                    self.assertEqual(Loaded["transits"], [])

    def testInspectionCannotCarryPeriodsEventsModelsOrPlanetAssessments(self):
        Cases = {"period": 2.0, "transits": [{"start": 0, "end": 1}],
                 "signals": [{"period": 2}], "predicted_windows": [{"start": 0}],
                 "observed_events": [{"center": 1}], "exploratory_dips": [{"center": 1}],
                 "planet_assessment": {"score": 75}, "assessment": {"score": 75},
                 "fit_quality": {"status": "good"}, "diagnostics": {"p_value": .01},
                 "transit_model": {"time": [0], "flux": [1]},
                 "phase_folded": {"phase": [0], "raw_flux": [1], "smooth_flux": [1]},
                 "periodogram": {"period": [1], "power": [4]}, "period_sde": 8.0}
        for Key, Value in Cases.items():
            with self.subTest(field=Key):
                Result = InspectionResult()
                Result[Key] = Value
                with self.assertRaises(ValueError):
                    ValidateResult(Result)

    def testInspectionMarkerReasonsAndCountsMustBeExplicit(self):
        Cases = [("review_only", 1), ("review_only", "true"), ("analysis_mode", "search"),
                 ("search_status", "completed"), ("review_reason", ""), ("search_reason", None),
                 ("search_requirements", {"minimum_samples": 49, "usable_samples": 3}),
                 ("search_requirements", {"minimum_samples": 50, "usable_samples": True}),
                 ("search_requirements", {"minimum_samples": 50, "usable_samples": 2}),
                 ("total_points", 2)]
        for Key, Value in Cases:
            with self.subTest(field=Key, value=Value):
                Result = InspectionResult()
                Result[Key] = Value
                with self.assertRaises(ValueError):
                    ValidateResult(Result)

    def testInspectionRejectsSingleSamplesDuplicateTimesAndAlteredFlux(self):
        Single = InspectionResult(1)
        Duplicate = InspectionResult()
        Duplicate["plot"]["time"] = [0, 0, 2]
        Altered = InspectionResult()
        Altered["plot"]["smooth_flux"][1] = 1.0
        for Result in (Single, Duplicate, Altered):
            with self.assertRaises(ValueError):
                ValidateResult(Result)

    def testInspectionErrorsExposuresAndDomainsRemainValidated(self):
        for Field, Value in (("flux_uncertainty", [.1]), ("flux_uncertainty", [.1, 0, .1]),
                             ("flux_uncertainty", [.1, float("nan"), .1]),
                             ("exposure_seconds", [30]), ("exposure_seconds", [30, -1, 30])):
            with self.subTest(field=Field, value=Value):
                Result = InspectionResult()
                Result["plot"][Field] = Value
                with self.assertRaises(ValueError):
                    ValidateResult(Result)
        Result = InspectionResult()
        Result["domain"] = {"time_min": 0, "time_max": 0}
        with self.assertRaises(ValueError):
            ValidateResult(Result)

    def testInvalidInspectionDoesNotOverwriteAnExistingCache(self):
        with Tempfile.TemporaryDirectory() as Folder:
            Cache = SessionCache(Folder)
            Result = InspectionResult()
            State = {"results": [{"result": Result}]}
            Cache.save("inspection_12345678", State)
            FilePath = Cache.PathFor("inspection_12345678")
            Before = FilePath.read_bytes()
            Result["planet_assessment"] = {"score": 100}
            with self.assertRaises(ValueError):
                Cache.save("inspection_12345678", State)
            self.assertEqual(FilePath.read_bytes(), Before)

    def testInspectionRequiresTheCountsAndDomainsUsedByTheViewer(self):
        with Tempfile.TemporaryDirectory() as Folder:
            Cache = SessionCache(Folder)
            State = {"results": [{"result": InspectionResult()}]}
            Cache.save("inspection_12345678", State)
            FilePath = Cache.PathFor("inspection_12345678")
            Before = FilePath.read_bytes()
            for Key in ("total_points", "time_reference", "domain", "raw_domain", "clean_domain"):
                with self.subTest(missing=Key):
                    Bad = Copy.deepcopy(State)
                    del Bad["results"][0]["result"][Key]
                    with self.assertRaises(ValueError):
                        Cache.save("inspection_12345678", Bad)
                    self.assertEqual(FilePath.read_bytes(), Before)
            for Key in ("domain", "raw_domain", "clean_domain"):
                for Value in (None, {}, {"time_min": 0}, {"flux_min": 0, "flux_max": float("nan")}):
                    with self.subTest(domain=Key, value=Value):
                        Bad = InspectionResult()
                        Bad[Key] = Value
                        with self.assertRaises(ValueError):
                            ValidateResult(Bad)
            for Value in (None, True, "2457000", float("nan"), float("inf"), -float("inf")):
                with self.subTest(time_reference=Value):
                    Bad = InspectionResult()
                    Bad["time_reference"] = Value
                    with self.assertRaises(ValueError):
                        ValidateResult(Bad)

    def testFullResultsKeepTheirExistingValidationRules(self):
        Result = {"period": 2.0, "transits": [{"start": 0, "end": 1}],
                  "plot": {"time": [0, 1, 2], "raw_flux": [1, .9, 1], "smooth_flux": [1, .95, 1]},
                  "planet_assessment": {"score": 65}}
        self.assertIs(ValidateResult(Result), Result)
        Bad = Copy.deepcopy(Result)
        Bad["plot"]["raw_flux"] = [1]
        with self.assertRaisesRegex(ValueError, "mismatched plot arrays"):
            ValidateResult(Bad)
        Bad = Copy.deepcopy(Result)
        Bad["period"] = 0
        with self.assertRaisesRegex(ValueError, "invalid period"):
            ValidateResult(Bad)


if __name__ == "__main__":
    Unittest.main()
