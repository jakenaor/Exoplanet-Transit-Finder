import csv
import hashlib
import io
import math

import numpy as np

try:
    from astropy.io import fits
except Exception:
    fits = None


MAX_CSV_UPLOAD_BYTES = 80 * 1024 * 1024
MAX_FITS_UPLOAD_BYTES = 200 * 1024 * 1024
TIME_COLUMN_CANDIDATES = ("time", "bjd", "btjd", "bkjd", "jd", "mjd")
FLUX_COLUMN_CANDIDATES = (
    "pdcsap_flux",
    "sap_flux",
    "flux",
    "kspsap_flux",
    "det_flux",
    "pdc_flux",
)
QUALITY_COLUMN_CANDIDATES = ("quality", "sap_quality", "data_quality")
UNCERTAINTY_COLUMN_CANDIDATES = ("flux_err", "flux_error", "flux_uncertainty", "error", "sigma")


def clean_light_curve_arrays(times, fluxes, uncertainties=None, quality=None,
                             return_metadata=False, cleaning=None, input_metadata=None):
    """Keep the first finite sample at each timestamp, retaining aligned errors.

    Exclusion counts are disjoint: invalid numeric rows, nonfinite rows,
    nonzero-quality rows, and duplicate timestamps reconcile to retained rows.
    Missing/invalid optional uncertainties do not discard otherwise useful data.
    """
    time = np.asarray(times, dtype=float)
    flux = np.asarray(fluxes, dtype=float)
    if time.ndim != 1 or flux.ndim != 1 or len(time) != len(flux):
        raise ValueError("Time and flux must be equally sized one-dimensional arrays.")
    report = dict(cleaning or {})
    report.setdefault("input_rows", len(time))
    report.setdefault("invalid_numeric_rows", 0)
    finite_mask = np.isfinite(time) & np.isfinite(flux)
    report["nonfinite_rows"] = int(np.count_nonzero(~finite_mask))
    if quality is not None:
        quality = np.asarray(quality)
        if quality.ndim != 1 or len(quality) != len(time):
            raise ValueError("Quality flags must align with time and flux.")
        rejected_quality = finite_mask & (quality != 0)
        report["quality_excluded_rows"] = int(np.count_nonzero(rejected_quality))
        finite_mask &= quality == 0
    else:
        report["quality_excluded_rows"] = 0
    error = None
    if uncertainties is not None:
        error = np.asarray(uncertainties, dtype=float)
        if error.ndim != 1 or len(error) != len(time):
            raise ValueError("Flux uncertainties must align with time and flux.")
        invalid_error = ~np.isfinite(error) | (error <= 0)
        report["invalid_uncertainty_rows"] = int(np.count_nonzero(invalid_error & finite_mask))
        error = np.where(invalid_error, np.nan, error)[finite_mask]
    time, flux = time[finite_mask], flux[finite_mask]
    order = np.argsort(time, kind="stable")
    report["sorting_applied"] = not np.array_equal(order, np.arange(len(time)))
    time, flux = time[order], flux[order]
    if error is not None:
        error = error[order]
    unique = np.r_[True, np.diff(time) > 0] if len(time) else np.asarray([], dtype=bool)
    report["duplicate_rows"] = int(len(time) - np.count_nonzero(unique))
    report["duplicate_policy"] = "keep first finite quality-approved row at each exact timestamp"
    time, flux = time[unique], flux[unique]
    if error is not None:
        error = error[unique]
    if len(time) < 2 or time[-1] <= time[0]:
        raise ValueError("The light curve has zero time span; provide distinct observation times.")
    if len(time) < 20:
        raise ValueError("Need at least 20 distinct finite time/flux rows after cleaning.")
    report["retained_rows"] = int(len(time))
    report["excluded_rows"] = int(report["input_rows"] - len(time))
    report["counts_reconcile"] = (report["input_rows"] == sum(report[k] for k in
        ("invalid_numeric_rows", "nonfinite_rows", "quality_excluded_rows", "duplicate_rows", "retained_rows")))
    if not report["counts_reconcile"]:
        raise ValueError("Input cleaning counts do not reconcile.")
    report["median_cadence_days"] = float(np.median(np.diff(time)))
    report["uncertainty_retained_rows"] = int(np.count_nonzero(np.isfinite(error))) if error is not None else 0
    if return_metadata:
        return {"time": time, "flux": flux, "flux_uncertainty": error,
                "cleaning": report, "input_metadata": dict(input_metadata or {})}
    return time, flux


def uploaded_filename(file_item):
    return str(getattr(file_item, "filename", "") or "")


def is_fits_filename(filename):
    return filename.lower().endswith((".fits", ".fit", ".fts"))


def read_upload_bytes(file_item, max_bytes, file_kind):
    raw = file_item.file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        limit_mb = max_bytes // (1024 * 1024)
        raise ValueError(f"{file_kind} file is too large for this local tool. Limit is {limit_mb} MB.")
    return raw


def time_unit_in_days(unit):
    value = str(unit or "d").strip().lower()
    if value in {"d", "day", "days"}:
        return 1.0
    if value in {"s", "sec", "second", "seconds"}:
        return 1.0 / 86400.0
    if value in {"h", "hr", "hour", "hours"}:
        return 1.0 / 24.0
    if value in {"min", "minute", "minutes"}:
        return 1.0 / 1440.0
    raise ValueError("Unsupported time unit. Use days, hours, minutes, or seconds.")


def parse_csv_bytes(raw, return_metadata=False, time_format=None, time_scale=None, time_unit=None):
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("The CSV does not have a header row.")

    column_map = {name.strip().lower(): name for name in reader.fieldnames if name}
    time_column = find_column(reader.fieldnames, TIME_COLUMN_CANDIDATES)
    flux_column = find_column(reader.fieldnames, FLUX_COLUMN_CANDIDATES)
    if time_column is None or flux_column is None:
        raise ValueError('The CSV must contain Time and Flux columns (or supported mission column names).')
    error_column = find_column(reader.fieldnames, (str(flux_column).lower() + "_err",) + UNCERTAINTY_COLUMN_CANDIDATES)
    quality_column = find_column(reader.fieldnames, QUALITY_COLUMN_CANDIDATES)
    times = []
    fluxes = []
    errors = [] if error_column else None
    quality = [] if quality_column else None
    input_rows = invalid_rows = 0
    for row in reader:
        input_rows += 1
        try:
            t = float(row[time_column])
            f = float(row[flux_column])
        except (TypeError, ValueError):
            invalid_rows += 1
            continue
        times.append(t)
        fluxes.append(f)
        if errors is not None:
            try:
                errors.append(float(row[error_column]))
            except (TypeError, ValueError):
                errors.append(float("nan"))
        if quality is not None:
            try:
                quality.append(float(row[quality_column]))
            except (TypeError, ValueError):
                quality.append(float("nan"))
    declared_format = str(time_format or "").strip().upper()
    inferred_format = str(time_column).strip().upper()
    explicit_format = declared_format if declared_format != "UNKNOWN" else ""
    format_name = explicit_format or (inferred_format if inferred_format in {"BJD", "BTJD", "BKJD", "JD", "MJD"} else "unknown")
    if declared_format and declared_format not in {"BJD", "BTJD", "BKJD", "JD", "MJD", "RELATIVE", "UNKNOWN"}:
        raise ValueError("Unsupported CSV time format. Use JD, BJD, MJD, BTJD, BKJD, or relative.")
    scale = time_unit_in_days(time_unit)
    offset = {"BTJD": 2457000.0, "BKJD": 2454833.0, "MJD": 2400000.5}.get(format_name, 0.0)
    converted_time = np.asarray(times, dtype=float) * scale + offset
    metadata = {"source_format": "CSV", "time_column": time_column, "flux_column": flux_column,
                "uncertainty_column": error_column, "quality_column": quality_column,
                "time_format": "BJD" if format_name in {"BTJD", "BKJD"} else ("JD" if format_name == "MJD" else format_name),
                "original_time_format": format_name, "time_scale": str(time_scale or "unknown").upper(),
                "time_unit": "days", "original_time_unit": time_unit or "unspecified (assumed days)",
                "time_reference_offset_days": offset,
                "time_convention_ambiguous": format_name in {"unknown", "UNKNOWN"} or str(time_scale or "unknown").lower() == "unknown",
                "time_unit_assumed": not bool(time_unit), "flux_representation": "as supplied; normalized by analysis"}
    return clean_light_curve_arrays(converted_time, fluxes, errors, quality, return_metadata,
                {"input_rows": input_rows, "invalid_numeric_rows": invalid_rows}, metadata)


def normalized_column_map(names):
    return {
        str(name).strip().lower(): name
        for name in names
        if name is not None
    }


def find_column(names, candidates, allow_contains=False):
    column_map = normalized_column_map(names)
    for candidate in candidates:
        if candidate in column_map:
            return column_map[candidate]

    if not allow_contains:
        return None

    for candidate in candidates:
        for normalized_name, original_name in column_map.items():
            if candidate in normalized_name:
                return original_name
    return None


def fits_time_reference(*headers):
    header = {}
    # Extension values override primary values; split reference parts may live
    # in different headers and must be combined before converting the epoch.
    for source in reversed(headers):
        header.update(dict(source or {}))
    for whole_key, fraction_key in (("BJDREFI", "BJDREFF"), ("JDREFI", "JDREFF"), ("MJDREFI", "MJDREFF")):
        if whole_key in header or fraction_key in header:
            reference = float(header.get(whole_key, 0.0)) + float(header.get(fraction_key, 0.0))
            return reference + (2400000.5 if whole_key == "MJDREFI" else 0.0)
    for key in ("BJDREF", "JDREF", "MJDREF"):
        if key in header:
            return float(header.get(key, 0.0)) + (2400000.5 if key == "MJDREF" else 0.0)
    return 0.0


def vector_column(data, column):
    values = np.asarray(data[column], dtype=float)
    if values.ndim > 1:
        values = np.squeeze(values)
    if values.ndim != 1:
        values = values.reshape(values.shape[0], -1)[:, 0]
    return values


def parse_fits_bytes(raw, return_metadata=False):
    if fits is None:
        raise ValueError("FITS uploads require astropy.io.fits, but astropy is not available.")

    with fits.open(io.BytesIO(raw), memmap=False) as hdul:
        primary_header = hdul[0].header if hdul else None
        for hdu_index, hdu in enumerate(hdul):
            data = getattr(hdu, "data", None)
            columns = getattr(hdu, "columns", None)
            names = list(getattr(columns, "names", []) or [])
            if data is None or not names:
                continue

            time_column = find_column(names, TIME_COLUMN_CANDIDATES)
            flux_column = find_column(names, FLUX_COLUMN_CANDIDATES, allow_contains=True)
            if time_column is None or flux_column is None:
                continue

            time = vector_column(data, time_column)
            flux = vector_column(data, flux_column)
            if len(time) != len(flux):
                continue

            header = getattr(hdu, "header", {})
            quality_column = find_column(names, QUALITY_COLUMN_CANDIDATES)
            error_column = find_column(names, (str(flux_column).lower() + "_err",) + UNCERTAINTY_COLUMN_CANDIDATES)
            quality = vector_column(data, quality_column) if quality_column else None
            errors = vector_column(data, error_column) if error_column else None
            unit = getattr(columns[time_column], "unit", None) or header.get("TIMEUNIT") or (primary_header or {}).get("TIMEUNIT")
            factor = time_unit_in_days(unit)
            reference = fits_time_reference(header, primary_header)
            timezero = header.get("TIMEZERO", (primary_header or {}).get("TIMEZERO", 0.0))
            time = (time + float(timezero)) * factor
            # Reference epochs are in days; TIME and TIMEZERO use the column unit.
            if reference:
                time = time + reference
            elif str(time_column).strip().lower() == "mjd":
                time = time + 2400000.5
            elif str(time_column).strip().lower() == "btjd":
                time = time + 2457000.0
            elif str(time_column).strip().lower() == "bkjd":
                time = time + 2454833.0
            combined = {**dict(primary_header or {}), **dict(header)}
            has_bjd_ref = any(k in combined for k in ("BJDREF", "BJDREFI", "BJDREFF"))
            format_name = "BJD" if has_bjd_ref or str(time_column).lower() in {"bjd", "btjd", "bkjd"} else ("JD" if reference or str(time_column).lower() in {"jd", "mjd"} else "unknown")
            metadata = {"source_format": "FITS", "hdu_index": hdu_index,
                        "time_column": time_column, "flux_column": flux_column,
                        "uncertainty_column": error_column, "quality_column": quality_column,
                        "time_format": format_name, "time_scale": str(combined.get("TIMESYS", "unknown")).upper(),
                        "time_unit": "days", "original_time_unit": unit or "unspecified (assumed days)",
                        "time_reference_offset_days": reference, "timezero": float(timezero),
                        "time_unit_assumed": not bool(unit), "time_convention_ambiguous": format_name == "unknown" or str(combined.get("TIMESYS", "unknown")).lower() == "unknown",
                        "mission": combined.get("MISSION", combined.get("TELESCOP")),
                        "target_identifier": combined.get("OBJECT", combined.get("TICID")),
                        "flux_representation": "as supplied; normalized by analysis"}
            return clean_light_curve_arrays(time, flux, errors, quality, return_metadata,
                                           {"input_rows": len(time), "invalid_numeric_rows": 0}, metadata)

    raise ValueError(
        "The FITS file must contain a table with TIME and a flux column "
        "(PDCSAP_FLUX, SAP_FLUX, or FLUX)."
    )


def parse_light_curve_upload(file_item, return_metadata=False, **metadata_options):
    filename = uploaded_filename(file_item)
    extension_is_fits = is_fits_filename(filename)
    max_bytes = MAX_FITS_UPLOAD_BYTES if extension_is_fits else MAX_CSV_UPLOAD_BYTES
    file_kind = "FITS" if extension_is_fits else "CSV"
    raw = read_upload_bytes(file_item, max_bytes, file_kind)
    is_fits = extension_is_fits or raw[:6] == b"SIMPLE"
    if is_fits:
        result = parse_fits_bytes(raw, return_metadata=return_metadata)
    else:
        result = parse_csv_bytes(raw, return_metadata=return_metadata, **metadata_options)
    if return_metadata:
        result["input_metadata"].update({"source_file": filename,
            "source_bytes": len(raw), "source_sha256": hashlib.sha256(raw).hexdigest()})
    return result
