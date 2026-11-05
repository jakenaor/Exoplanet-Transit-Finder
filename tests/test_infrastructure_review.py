"""Input provenance, session compatibility, and background job contracts."""
import io
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest import mock

import numpy as np

APP_DIR = Path(__file__).resolve().parents[1] / "Exoplanet data parsing tool"
sys.path.insert(0, str(APP_DIR))

from analysis_jobs import AnalysisJobManager, annotate_analysis_result
from parsers import clean_light_curve_arrays, parse_csv_bytes, parse_fits_bytes, fits_time_reference
from session_cache import SessionCache
from main import TransitRequestHandler


def progress_runner(time_values, flux_values, options, progress_callback=None):
    progress_callback("tls_search", "Searching periods with TLS", {
        "completed_trials": 10, "total_trials": 100,
        "estimated_remaining_seconds": 12, "eta_lower_seconds": 8,
        "eta_upper_seconds": 20, "eta_scope": "search",
    })
    time.sleep(0.6)
    progress_callback("finalizing", "Preparing result")
    time.sleep(0.1)
    return {"finished": True}


def minimal_result():
    return {"period": 2.0, "plot": {"time": [0, 1, 2],
        "raw_flux": [1, .99, 1], "smooth_flux": [1, .99, 1]}, "transits": []}


def multiple_signal_runner(time_values, flux_values, options):
    result = minimal_result()
    result["effective_settings"] = {"tls_max_signals": 2}
    first = minimal_result()
    first["effective_settings"] = {"tls_max_signals": 2, "signal_index": 0}
    second = minimal_result()
    second["period"] = 3.0
    second["effective_settings"] = {"tls_max_signals": 1, "signal_index": 1}
    result["signals"] = [first, second]
    return result


class ParserReviewTests(unittest.TestCase):
    def test_csv_counts_reconcile_without_discarding_missing_errors(self):
        rows = ["Time,Flux,Flux_err,Quality"]
        rows += [f"{i},1,0.01,0" for i in range(30)]
        rows += ["1,0.5,0.02,0", "bad,1,0.01,0", "nan,1,0.01,0",
                 "31,1,0.01,1", "32,1,,0"]
        parsed = parse_csv_bytes("\n".join(rows).encode(), return_metadata=True)
        c = parsed["cleaning"]
        self.assertEqual(c["input_rows"], 35)
        self.assertEqual(c["retained_rows"], 31)
        for field in ("invalid_numeric_rows", "nonfinite_rows", "quality_excluded_rows", "duplicate_rows"):
            self.assertEqual(c[field], 1)
        self.assertTrue(c["counts_reconcile"])
        self.assertEqual(c["invalid_uncertainty_rows"], 1)
        self.assertTrue(np.isnan(parsed["flux_uncertainty"][-1]))
        self.assertEqual(parsed["flux"][1], 1)
        self.assertTrue(parsed["input_metadata"]["time_convention_ambiguous"])

    def test_sorting_duplicate_policy_and_errors_stay_aligned(self):
        time_values = list(range(29, -1, -1)) + [10]
        parsed = clean_light_curve_arrays(time_values,
            [1 + t / 100 for t in time_values[:-1]] + [9],
            [0.1 + t / 1000 for t in time_values[:-1]] + [9], return_metadata=True)
        np.testing.assert_equal(parsed["time"], np.arange(30))
        self.assertAlmostEqual(parsed["flux"][10], 1.1)
        self.assertAlmostEqual(parsed["flux_uncertainty"][10], .11)
        self.assertTrue(parsed["cleaning"]["sorting_applied"])
        self.assertEqual(parsed["cleaning"]["duplicate_rows"], 1)

    def test_declared_csv_time_conversion_is_explicit(self):
        csv_data = ("Time,Flux\n" + "\n".join(f"{i * 60},1" for i in range(30))).encode()
        parsed = parse_csv_bytes(csv_data, return_metadata=True,
                                 time_format="btjd", time_unit="seconds", time_scale="tdb")
        self.assertAlmostEqual(parsed["time"][0], 2457000)
        self.assertAlmostEqual(parsed["time"][1] - parsed["time"][0], 60 / 86400, places=8)
        self.assertEqual(parsed["input_metadata"]["time_format"], "BJD")
        self.assertEqual(parsed["input_metadata"]["time_scale"], "TDB")
        self.assertFalse(parsed["input_metadata"]["time_convention_ambiguous"])
        kepler = parse_csv_bytes(csv_data.replace(b"Time", b"BKJD"), return_metadata=True, time_unit="seconds")
        self.assertEqual(kepler["time"][0], 2454833)
        self.assertEqual(kepler["input_metadata"]["time_format"], "BJD")

    def test_csv_mjd_header_converts_to_jd_without_guessing_generic_time(self):
        csv_data = ("MJD,Flux\n" + "\n".join(f"{60000 + i / 10},1" for i in range(30))).encode()
        parsed = parse_csv_bytes(csv_data, return_metadata=True)
        self.assertEqual(parsed["time"][0], 2460000.5)
        self.assertEqual(parsed["input_metadata"]["original_time_format"], "MJD")
        # The UI's default "unknown" means no override, not discard the header.
        default_ui = parse_csv_bytes(csv_data, return_metadata=True, time_format="unknown")
        np.testing.assert_equal(default_ui["time"], parsed["time"])

    def test_zero_span_fails_before_cadence_can_be_infinite(self):
        with self.assertRaisesRegex(ValueError, "zero time span"):
            clean_light_curve_arrays(np.ones(30), np.ones(30))

    def test_split_fits_reference_uses_extension_and_primary_parts(self):
        self.assertEqual(fits_time_reference({"BJDREFF": .25}, {"BJDREFI": 2457000}), 2457000.25)

    def test_fits_seconds_reference_quality_errors_and_scale(self):
        from astropy.io import fits
        cols = [fits.Column(name="TIME", format="D", unit="s", array=np.arange(30) * 60),
                fits.Column(name="PDCSAP_FLUX", format="D", array=np.ones(30)),
                fits.Column(name="PDCSAP_FLUX_ERR", format="D", array=np.full(30, .01)),
                fits.Column(name="QUALITY", format="J", array=[1] + [0] * 29)]
        table = fits.BinTableHDU.from_columns(cols)
        table.header["MJDREFI"] = 60000
        table.header["MJDREFF"] = .25
        table.header["TIMEZERO"] = 30
        table.header["TIMESYS"] = "TDB"
        output = io.BytesIO()
        fits.HDUList([fits.PrimaryHDU(), table]).writeto(output)
        parsed = parse_fits_bytes(output.getvalue(), return_metadata=True)
        self.assertAlmostEqual(parsed["time"][0], 2460000.75 + 90 / 86400)
        self.assertEqual(parsed["cleaning"]["quality_excluded_rows"], 1)
        self.assertEqual(parsed["cleaning"]["retained_rows"], 29)
        self.assertEqual(parsed["input_metadata"]["time_scale"], "TDB")
        np.testing.assert_equal(parsed["flux_uncertainty"], np.full(29, .01))


class CacheReviewTests(unittest.TestCase):
    def test_legacy_restore_is_explicit_and_leaves_original_file_untouched(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = SessionCache(folder)
            document = {"schema_version": 1, "session_id": "legacy_12345678",
                        "saved_at": "2020-01-01", "state": {"results": [{"file_name": "old.csv", "result": minimal_result()}]}}
            path = cache.path_for(document["session_id"])
            path.write_text(json.dumps(document))
            before = path.read_bytes()
            restored = cache.load(document["session_id"])
            result = restored["state"]["results"][0]["result"]
            self.assertEqual(result["provenance"]["analysis_version"], "unknown")
            self.assertIsNone(result["analyzed_at"])
            self.assertEqual(path.read_bytes(), before)

    def test_resaving_keeps_analysis_date_and_effective_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = SessionCache(folder)
            r = annotate_analysis_result(minimal_result(), {"stellar_mass": .1})
            state = {"results": [{"file_name": "new.csv", "result": r}],
                     "active_job_id": "abcdef123", "active_file_index": 0,
                     "pending_files": [{"file_name": "next.csv"}]}
            original_date = r["analyzed_at"]
            cache.save("current_12345678", state)
            loaded = cache.load("current_12345678")["state"]
            loaded["current_view"] = "stack"
            cache.save("current_12345678", loaded)
            final = cache.load("current_12345678")["state"]["results"][0]["result"]
            self.assertEqual(final["analyzed_at"], original_date)
            self.assertEqual(final["provenance"]["effective_settings"], {"stellar_mass": .1})

    def test_malformed_cache_reports_error_and_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = SessionCache(folder)
            bad = minimal_result()
            bad["plot"]["raw_flux"] = [1]
            doc = {"schema_version": 1, "session_id": "broken_12345678", "state": {"results": [{"result": bad}]}}
            path = cache.path_for(doc["session_id"])
            path.write_text(json.dumps(doc))
            before = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "mismatched plot arrays"):
                cache.load(doc["session_id"])
            self.assertEqual(path.read_bytes(), before)

    def test_future_schema_is_not_silently_loaded(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = SessionCache(folder)
            doc = {"schema_version": 999, "session_id": "future_12345678", "state": {"results": []}}
            cache.path_for(doc["session_id"]).write_text(json.dumps(doc))
            with self.assertRaisesRegex(ValueError, "unsupported cache schema"):
                cache.load(doc["session_id"])

    def test_future_provenance_schema_and_mismatched_folded_arrays_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = SessionCache(folder)
            r = annotate_analysis_result(minimal_result())
            r["provenance"]["result_schema_version"] = 999
            with self.assertRaisesRegex(ValueError, "inconsistent provenance/result schemas"):
                cache.save("metadata_12345678", {"results": [{"result": r}]})
            r = minimal_result()
            r["transit_model"] = {"time": [], "flux": [], "folded_phase_days": [0, 1], "folded_flux": [1]}
            with self.assertRaisesRegex(ValueError, "mismatched folded model"):
                cache.save("metadata_12345678", {"results": [{"result": r}]})

    def test_active_job_without_a_matching_file_is_recoverably_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = SessionCache(folder)
            with self.assertRaisesRegex(ValueError, "no matching file entry"):
                cache.save("active_12345678", {"results": [], "active_job_id": "abc123"})


class JobReviewTests(unittest.TestCase):
    def test_multisignal_worker_result_round_trips_cache_with_own_settings(self):
        manager = AnalysisJobManager(runner=multiple_signal_runner)
        self.addCleanup(manager.shutdown)
        submitted = manager.submit(np.arange(30), np.ones(30), {}, source_file="two.csv")
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            job = manager.get(submitted["job_id"])
            if job["status"] in {"completed", "failed"}:
                break
            time.sleep(.03)
        self.assertEqual(job["status"], "completed", job.get("error"))
        with tempfile.TemporaryDirectory() as folder:
            cache = SessionCache(folder)
            cache.save("multiple_12345678", {"results": [{"file_name": "two.csv", "result": job["result"]}]})
            restored = cache.load("multiple_12345678")["state"]["results"][0]["result"]
        for index, signal_result in enumerate(restored["signals"]):
            self.assertEqual(signal_result["result_schema_version"], 2)
            self.assertEqual(signal_result["provenance"]["result_schema_version"], 2)
            self.assertEqual(signal_result["provenance"]["effective_settings"]["signal_index"], index)
            self.assertEqual(signal_result["provenance"]["analyzed_at"], signal_result["analyzed_at"])
            self.assertEqual(signal_result["provenance"]["source_file"], "two.csv")

    def test_submission_lookup_http_route_decodes_token_and_returns_existing_job(self):
        handler = object.__new__(TransitRequestHandler)
        handler.path = "/analysis-jobs?request_id=batch-example%3A0"
        handler.server = mock.Mock()
        handler.server.analysis_jobs.find_by_request_id.return_value = {"job_id": "abc123", "status": "running"}
        handler.write_json = mock.Mock()
        handler.do_GET()
        handler.server.analysis_jobs.find_by_request_id.assert_called_once_with("batch-example:0")
        handler.write_json.assert_called_once_with({"job_id": "abc123", "status": "running"}, status=200)

    def test_progress_is_measured_and_terminal_eta_clears(self):
        manager = AnalysisJobManager(runner=progress_runner)
        self.addCleanup(manager.shutdown)
        first = manager.submit(np.arange(30), np.ones(30), {})
        saw_progress = None
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            snapshot = manager.get(first["job_id"])
            if snapshot.get("completed_trials") == 10:
                saw_progress = snapshot
            if snapshot["status"] in {"completed", "failed"}:
                break
            time.sleep(.03)
        self.assertIsNotNone(saw_progress)
        self.assertEqual(saw_progress["total_trials"], 100)
        self.assertEqual(saw_progress["eta_scope"], "search")
        self.assertEqual(snapshot["status"], "completed", snapshot.get("error"))
        self.assertIsNone(snapshot["estimated_remaining_seconds"])
        self.assertEqual(snapshot["result"]["result_schema_version"], 2)

    def test_repeated_submission_token_does_not_launch_a_second_job(self):
        manager = AnalysisJobManager(runner=progress_runner)
        self.addCleanup(manager.shutdown)
        options = {"_request_id": "batch-example:0", "_batch_id": "batch-example"}
        first = manager.submit(np.arange(30), np.ones(30), options, "same.csv")
        repeated = manager.submit(np.arange(30), np.ones(30), options, "same.csv")
        self.assertEqual(first["job_id"], repeated["job_id"])
        self.assertEqual(len(manager.jobs), 1)
        found = manager.find_by_request_id(options["_request_id"])
        self.assertEqual(found["job_id"], first["job_id"])
        self.assertIsNone(manager.find_by_request_id("unknown-submission"))
        with self.assertRaisesRegex(ValueError, "different analysis inputs"):
            manager.submit(np.arange(30), np.zeros(30), options, "same.csv")

    def test_nonfinite_result_is_rejected_before_transport(self):
        with self.assertRaisesRegex(ValueError, "nonfinite or unsupported"):
            annotate_analysis_result({"diagnostics": {"invalid": float("nan")}})


if __name__ == "__main__":
    unittest.main()
