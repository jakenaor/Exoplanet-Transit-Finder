import csv
import io
import math

import numpy as np

try:
    from astropy.io import fits
except Exception:
    fits = None


MAX_CSV_UPLOAD_BYTES = 80 * 1024 * 1024
MAX_FITS_UPLOAD_BYTES = 200 * 1024 * 1024
TIME_COLUMN_CANDIDATES = ("time", "bjd", "btjd", "jd", "mjd")
FLUX_COLUMN_CANDIDATES = (
    "pdcsap_flux",
    "sap_flux",
    "flux",
    "kspsap_flux",
    "det_flux",
    "pdc_flux",
)
QUALITY_COLUMN_CANDIDATES = ("quality", "sap_quality", "data_quality")


def clean_light_curve_arrays(times, fluxes):
    if len(times) < 20:
        raise ValueError("Need at least 20 numeric rows to analyze a light curve.")

    time = np.asarray(times, dtype=float)
    flux = np.asarray(fluxes, dtype=float)
    finite_mask = np.isfinite(time) & np.isfinite(flux)
    time = time[finite_mask]
    flux = flux[finite_mask]
    if len(time) < 20:
        raise ValueError("Need at least 20 finite time/flux rows to analyze a light curve.")

    order = np.argsort(time)
    return time[order], flux[order]


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


def parse_csv_bytes(raw):
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("The CSV does not have a header row.")

    column_map = {name.strip().lower(): name for name in reader.fieldnames if name}
    if "time" not in column_map or "flux" not in column_map:
        raise ValueError('The CSV must contain columns named "Time" and "Flux".')

    times = []
    fluxes = []
    for row in reader:
        try:
            t = float(row[column_map["time"]])
            f = float(row[column_map["flux"]])
        except (TypeError, ValueError):
            continue
        if math.isfinite(t) and math.isfinite(f):
            times.append(t)
            fluxes.append(f)

    return clean_light_curve_arrays(times, fluxes)


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
    for header in headers:
        if not header:
            continue
        for whole_key, fraction_key in (("BJDREFI", "BJDREFF"), ("JDREFI", "JDREFF"), ("MJDREFI", "MJDREFF")):
            if whole_key in header or fraction_key in header:
                return float(header.get(whole_key, 0.0)) + float(header.get(fraction_key, 0.0)) + float(header.get("TIMEZERO", 0.0))
        for key in ("BJDREF", "JDREF", "MJDREF"):
            if key in header:
                return float(header.get(key, 0.0)) + float(header.get("TIMEZERO", 0.0))
        if "TIMEZERO" in header:
            return float(header.get("TIMEZERO", 0.0))
    return 0.0


def vector_column(data, column):
    values = np.asarray(data[column], dtype=float)
    if values.ndim > 1:
        values = np.squeeze(values)
    if values.ndim != 1:
        values = values.reshape(values.shape[0], -1)[:, 0]
    return values


def parse_fits_bytes(raw):
    if fits is None:
        raise ValueError("FITS uploads require astropy.io.fits, but astropy is not available.")

    with fits.open(io.BytesIO(raw), memmap=False) as hdul:
        primary_header = hdul[0].header if hdul else None
        for hdu in hdul:
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

            quality_column = find_column(names, QUALITY_COLUMN_CANDIDATES)
            mask = np.isfinite(time) & np.isfinite(flux)
            if quality_column is not None:
                quality = np.asarray(data[quality_column])
                if quality.ndim > 1:
                    quality = np.squeeze(quality)
                if quality.ndim == 1 and len(quality) == len(time):
                    mask &= quality == 0

            time = time[mask]
            flux = flux[mask]
            if time.size < 20:
                continue

            reference = fits_time_reference(getattr(hdu, "header", None), primary_header)
            if reference and np.nanmax(np.abs(time)) < 1000000:
                time = time + reference

            return clean_light_curve_arrays(time.tolist(), flux.tolist())

    raise ValueError(
        "The FITS file must contain a table with TIME and a flux column "
        "(PDCSAP_FLUX, SAP_FLUX, or FLUX)."
    )


def parse_light_curve_upload(file_item):
    filename = uploaded_filename(file_item)
    extension_is_fits = is_fits_filename(filename)
    max_bytes = MAX_FITS_UPLOAD_BYTES if extension_is_fits else MAX_CSV_UPLOAD_BYTES
    file_kind = "FITS" if extension_is_fits else "CSV"
    raw = read_upload_bytes(file_item, max_bytes, file_kind)
    is_fits = extension_is_fits or raw[:6] == b"SIMPLE"
    if is_fits:
        return parse_fits_bytes(raw)
    return parse_csv_bytes(raw)
