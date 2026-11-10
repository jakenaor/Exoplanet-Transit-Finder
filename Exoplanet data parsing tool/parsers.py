#MARK: imports
import csv as Csv
import hashlib as Hashlib
import io as Io
import math as Math

import numpy as Np

try:
    from astropy.io import fits as Fits
except Exception:
    Fits = None


#MARK: curve columns
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
EXPOSURE_SECONDS_COLUMNS = ("exposure_seconds", "exposure_s", "exptime_seconds", "exptime_s")
EXPOSURE_DAYS_COLUMNS = ("exposure_days", "exposure_d", "exptime_days")


#MARK: cleaning the samples
def CleanLightCurveArrays(Times, Fluxes, Uncertainties=None, Quality=None,
                             ReturnMetadata=False, Cleaning=None, InputMetadata=None,
                             ExposureSeconds=None):
    """Keep the first finite sample at each timestamp, retaining aligned errors.

    Exclusion counts are disjoint: invalid numeric rows, nonfinite rows,
    nonzero-quality rows, and duplicate timestamps reconcile to retained rows.
    Missing/invalid optional uncertainties do not discard otherwise useful data.
    """
    #MARK: core stuffs
    Time = Np.asarray(Times, dtype=float)
    Flux = Np.asarray(Fluxes, dtype=float)
    if Time.ndim != 1 or Flux.ndim != 1 or len(Time) != len(Flux):
        raise ValueError("Time and flux must be equally sized one-dimensional arrays.")
    Report = dict(Cleaning or {})
    Report.setdefault("input_rows", len(Time))
    Report.setdefault("invalid_numeric_rows", 0)
    #MARK: core stuffs
    # count each rejected row once, even if more than one field is bad.
    FiniteMask = Np.isfinite(Time) & Np.isfinite(Flux)
    Report["nonfinite_rows"] = int(Np.count_nonzero(~FiniteMask))
    if Quality is not None:
        Quality = Np.asarray(Quality)
        if Quality.ndim != 1 or len(Quality) != len(Time):
            raise ValueError("Quality flags must align with time and flux.")
        RejectedQuality = FiniteMask & (Quality != 0)
        Report["quality_excluded_rows"] = int(Np.count_nonzero(RejectedQuality))
        FiniteMask &= Quality == 0
    else:
        Report["quality_excluded_rows"] = 0
    Error = None
    Exposure = None
    #MARK: form bits
    if ExposureSeconds is not None:
        Exposure = Np.asarray(ExposureSeconds, dtype=float)
        if Exposure.ndim == 0:
            Exposure = Np.full(len(Time), float(Exposure))
        if Exposure.ndim != 1 or len(Exposure) != len(Time):
            raise ValueError("Exposure durations must align with time and flux.")
        # zero exposure is valid. negative exposure is not.
        InvalidExposure = ~Np.isfinite(Exposure) | (Exposure < 0)
        Report["invalid_exposure_rows"] = int(Np.count_nonzero(InvalidExposure & FiniteMask))
        Exposure = Np.where(InvalidExposure, Np.nan, Exposure)[FiniteMask]
    if Uncertainties is not None:
        Error = Np.asarray(Uncertainties, dtype=float)
        if Error.ndim != 1 or len(Error) != len(Time):
            raise ValueError("Flux uncertainties must align with time and flux.")
        # missing error bars should not throw away a good flux sample.
        InvalidError = ~Np.isfinite(Error) | (Error <= 0)
        Report["invalid_uncertainty_rows"] = int(Np.count_nonzero(InvalidError & FiniteMask))
        Error = Np.where(InvalidError, Np.nan, Error)[FiniteMask]
    Time, Flux = Time[FiniteMask], Flux[FiniteMask]
    #MARK: core stuffs
    # stable sorting keeps the first usable row when timestamps repeat.
    Order = Np.argsort(Time, kind="stable")
    Report["sorting_applied"] = not Np.array_equal(Order, Np.arange(len(Time)))
    Time, Flux = Time[Order], Flux[Order]
    if Error is not None:
        Error = Error[Order]
    if Exposure is not None:
        Exposure = Exposure[Order]
    Unique = Np.r_[True, Np.diff(Time) > 0] if len(Time) else Np.asarray([], dtype=bool)
    Report["duplicate_rows"] = int(len(Time) - Np.count_nonzero(Unique))
    Report["duplicate_policy"] = "keep first finite quality-approved row at each exact timestamp"
    Time, Flux = Time[Unique], Flux[Unique]
    if Error is not None:
        Error = Error[Unique]
    if Exposure is not None:
        Exposure = Exposure[Unique]
    #MARK: checking what remains
    if len(Time) < 2 or Time[-1] <= Time[0]:
        raise ValueError("The light curve has zero time span; provide distinct observation times.")
    if len(Time) < 20:
        raise ValueError("Need at least 20 distinct finite time/flux rows after cleaning.")
    Report["retained_rows"] = int(len(Time))
    Report["excluded_rows"] = int(Report["input_rows"] - len(Time))
    Report["counts_reconcile"] = (Report["input_rows"] == sum(Report[K] for K in
        ("invalid_numeric_rows", "nonfinite_rows", "quality_excluded_rows", "duplicate_rows", "retained_rows")))
    if not Report["counts_reconcile"]:
        raise ValueError("Input cleaning counts do not reconcile.")
    Report["median_cadence_days"] = float(Np.median(Np.diff(Time)))
    Report["uncertainty_retained_rows"] = int(Np.count_nonzero(Np.isfinite(Error))) if Error is not None else 0
    #MARK: exposure model
    Metadata = dict(InputMetadata or {})
    KnownExposure = Np.isfinite(Exposure) if Exposure is not None else Np.zeros(len(Time), dtype=bool)
    Metadata["exposure"] = {**Metadata.get("exposure", {}), "unit": "seconds",
        "known_rows": int(Np.count_nonzero(KnownExposure)),
        "unknown_rows": int(len(Time) - Np.count_nonzero(KnownExposure)),
        "source": Metadata.get("exposure", {}).get("source", "unknown"),
        "cadence_is_exposure": False}
    if ReturnMetadata:
        return {"time": Time, "flux": Flux, "flux_uncertainty": Error,
                "exposure_seconds": Exposure, "cleaning": Report, "input_metadata": Metadata}
    return Time, Flux


#MARK: curve uploads
def UploadedFilename(FileItem):
    return str(getattr(FileItem, "filename", "") or "")


#MARK: fits rows
def IsFitsFilename(Filename):
    return Filename.lower().endswith((".fits", ".fit", ".fts"))


#MARK: curve uploads
def ReadUploadBytes(FileItem, MaxBytes, FileKind):
    # read one extra byte so an oversized upload is caught without reading it all.
    Raw = FileItem.file.read(MaxBytes + 1)
    if len(Raw) > MaxBytes:
        LimitMb = MaxBytes // (1024 * 1024)
        raise ValueError(f"{FileKind} file is too large for this local tool. Limit is {LimitMb} MB.")
    return Raw


#MARK: time units
def TimeUnitInDays(Unit):
    Value = str(Unit or "d").strip().lower()
    if Value in {"d", "day", "days"}:
        return 1.0
    if Value in {"s", "sec", "second", "seconds"}:
        return 1.0 / 86400.0
    if Value in {"h", "hr", "hour", "hours"}:
        return 1.0 / 24.0
    if Value in {"min", "minute", "minutes"}:
        return 1.0 / 1440.0
    raise ValueError("Unsupported time unit. Use days, hours, minutes, or seconds.")


#MARK: csv rows
def ParseCsvBytes(Raw, ReturnMetadata=False, TimeFormat=None, TimeScale=None, TimeUnit=None):
    Text = Raw.decode("utf-8-sig", errors="replace")
    Reader = Csv.DictReader(Io.StringIO(Text))
    if not Reader.fieldnames:
        raise ValueError("The CSV does not have a header row.")

    #MARK: csv rows
    ColumnMap = {Name.strip().lower(): Name for Name in Reader.fieldnames if Name}
    TimeColumn = FindColumn(Reader.fieldnames, TIME_COLUMN_CANDIDATES)
    FluxColumn = FindColumn(Reader.fieldnames, FLUX_COLUMN_CANDIDATES)
    if TimeColumn is None or FluxColumn is None:
        raise ValueError('The CSV must contain Time and Flux columns (or supported mission column names).')
    ErrorColumn = FindColumn(Reader.fieldnames, (str(FluxColumn).lower() + "_err",) + UNCERTAINTY_COLUMN_CANDIDATES)
    QualityColumn = FindColumn(Reader.fieldnames, QUALITY_COLUMN_CANDIDATES)
    ExposureColumn = FindColumn(Reader.fieldnames, EXPOSURE_SECONDS_COLUMNS + EXPOSURE_DAYS_COLUMNS)
    ExposureFactor = 86400.0 if str(ExposureColumn).strip().lower() in EXPOSURE_DAYS_COLUMNS else 1.0
    Times = []
    Fluxes = []
    Errors = [] if ErrorColumn else None
    Quality = [] if QualityColumn else None
    Exposures = [] if ExposureColumn else None
    InputRows = InvalidRows = 0
    #MARK: reading numeric rows
    for Row in Reader:
        InputRows += 1
        try:
            T = float(Row[TimeColumn])
            F = float(Row[FluxColumn])
        except (TypeError, ValueError):
            InvalidRows += 1
            continue
        Times.append(T)
        Fluxes.append(F)
        if Exposures is not None:
            try:
                Exposures.append(float(Row[ExposureColumn]) * ExposureFactor)
            except (TypeError, ValueError):
                Exposures.append(float("nan"))
        if Errors is not None:
            try:
                Errors.append(float(Row[ErrorColumn]))
            except (TypeError, ValueError):
                Errors.append(float("nan"))
        if Quality is not None:
            try:
                Quality.append(float(Row[QualityColumn]))
            except (TypeError, ValueError):
                Quality.append(float("nan"))
    #MARK: core stuffs
    DeclaredFormat = str(TimeFormat or "").strip().upper()
    InferredFormat = str(TimeColumn).strip().upper()
    # the default selector should not override a named bjd or mjd column.
    ExplicitFormat = DeclaredFormat if DeclaredFormat != "UNKNOWN" else ""
    FormatName = ExplicitFormat or (InferredFormat if InferredFormat in {"BJD", "BTJD", "BKJD", "JD", "MJD"} else "unknown")
    if DeclaredFormat and DeclaredFormat not in {"BJD", "BTJD", "BKJD", "JD", "MJD", "RELATIVE", "UNKNOWN"}:
        raise ValueError("Unsupported CSV time format. Use JD, BJD, MJD, BTJD, BKJD, or relative.")
    Scale = TimeUnitInDays(TimeUnit)
    Offset = {"BTJD": 2457000.0, "BKJD": 2454833.0, "MJD": 2400000.5}.get(FormatName, 0.0)
    ConvertedTime = Np.asarray(Times, dtype=float) * Scale + Offset
    #MARK: core stuffs
    # unknown time scales stay unknown; the filename is not evidence for one.
    Metadata = {"source_format": "CSV", "time_column": TimeColumn, "flux_column": FluxColumn,
                "uncertainty_column": ErrorColumn, "quality_column": QualityColumn,
                "time_format": "BJD" if FormatName in {"BTJD", "BKJD"} else ("JD" if FormatName == "MJD" else FormatName),
                "original_time_format": FormatName, "time_scale": str(TimeScale or "unknown").upper(),
                "time_unit": "days", "original_time_unit": TimeUnit or "unspecified (assumed days)",
                "time_reference_offset_days": Offset,
                "time_convention_ambiguous": FormatName in {"unknown", "UNKNOWN"} or str(TimeScale or "unknown").lower() == "unknown",
                "time_unit_assumed": not bool(TimeUnit), "flux_representation": "as supplied; normalized by analysis"}
    Metadata["exposure"] = {"source": "CSV column" if ExposureColumn else "unknown",
        "column": ExposureColumn, "original_unit": "days" if ExposureFactor == 86400.0 else "seconds"}
    return CleanLightCurveArrays(ConvertedTime, Fluxes, Errors, Quality, ReturnMetadata,
                {"input_rows": InputRows, "invalid_numeric_rows": InvalidRows}, Metadata,
                ExposureSeconds=Exposures)


#MARK: curve columns
def NormalizedColumnMap(Names):
    return {
        str(Name).strip().lower(): Name
        for Name in Names
        if Name is not None
    }


#MARK: curve columns
def FindColumn(Names, Candidates, AllowContains=False):
    ColumnMap = NormalizedColumnMap(Names)
    for Candidate in Candidates:
        if Candidate in ColumnMap:
            return ColumnMap[Candidate]

    if not AllowContains:
        return None

    for Candidate in Candidates:
        for NormalizedName, OriginalName in ColumnMap.items():
            if Candidate in NormalizedName:
                return OriginalName
    return None


#MARK: fits rows
def FitsTimeReference(*Headers):
    Header = {}
    # extension values override primary values; split reference parts may live
    # in different headers and must be combined before converting the epoch.
    for Source in reversed(Headers):
        Header.update(dict(Source or {}))
    for WholeKey, FractionKey in (("BJDREFI", "BJDREFF"), ("JDREFI", "JDREFF"), ("MJDREFI", "MJDREFF")):
        if WholeKey in Header or FractionKey in Header:
            Reference = float(Header.get(WholeKey, 0.0)) + float(Header.get(FractionKey, 0.0))
            return Reference + (2400000.5 if WholeKey == "MJDREFI" else 0.0)
    for Key in ("BJDREF", "JDREF", "MJDREF"):
        if Key in Header:
            return float(Header.get(Key, 0.0)) + (2400000.5 if Key == "MJDREF" else 0.0)
    return 0.0


#MARK: fits rows
def VectorColumn(Data, Column):
    Values = Np.asarray(Data[Column], dtype=float)
    if Values.ndim > 1:
        Values = Np.squeeze(Values)
    if Values.ndim != 1:
        Values = Values.reshape(Values.shape[0], -1)[:, 0]
    return Values


#MARK: fits rows
def ParseFitsBytes(Raw, ReturnMetadata=False):
    if Fits is None:
        raise ValueError("FITS uploads require astropy.io.fits, but astropy is not available.")

    with Fits.open(Io.BytesIO(Raw), memmap=False) as Hdul:
        PrimaryHeader = Hdul[0].header if Hdul else None
        #MARK: core stuffs
        for HduIndex, Hdu in enumerate(Hdul):
            Data = getattr(Hdu, "data", None)
            Columns = getattr(Hdu, "columns", None)
            Names = list(getattr(Columns, "names", []) or [])
            if Data is None or not Names:
                continue

            TimeColumn = FindColumn(Names, TIME_COLUMN_CANDIDATES)
            FluxColumn = FindColumn(Names, FLUX_COLUMN_CANDIDATES, AllowContains=True)
            if TimeColumn is None or FluxColumn is None:
                continue

            Time = VectorColumn(Data, TimeColumn)
            Flux = VectorColumn(Data, FluxColumn)
            if len(Time) != len(Flux):
                continue

            #MARK: flux errors
            Header = getattr(Hdu, "header", {})
            QualityColumn = FindColumn(Names, QUALITY_COLUMN_CANDIDATES)
            ErrorColumn = FindColumn(Names, (str(FluxColumn).lower() + "_err",) + UNCERTAINTY_COLUMN_CANDIDATES)
            Quality = VectorColumn(Data, QualityColumn) if QualityColumn else None
            Errors = VectorColumn(Data, ErrorColumn) if ErrorColumn else None
            #MARK: fits rows
            Unit = getattr(Columns[TimeColumn], "unit", None) or Header.get("TIMEUNIT") or (PrimaryHeader or {}).get("TIMEUNIT")
            Factor = TimeUnitInDays(Unit)
            Reference = FitsTimeReference(Header, PrimaryHeader)
            Timezero = Header.get("TIMEZERO", (PrimaryHeader or {}).get("TIMEZERO", 0.0))
            Time = (Time + float(Timezero)) * Factor
            # reference epochs are in days; time and timezero use the column unit.
            if Reference:
                Time = Time + Reference
            elif str(TimeColumn).strip().lower() == "mjd":
                Time = Time + 2400000.5
            elif str(TimeColumn).strip().lower() == "btjd":
                Time = Time + 2457000.0
            elif str(TimeColumn).strip().lower() == "bkjd":
                Time = Time + 2454833.0
            Combined = {**dict(PrimaryHeader or {}), **dict(Header)}
            HasBjdRef = any(K in Combined for K in ("BJDREF", "BJDREFI", "BJDREFF"))
            FormatName = "BJD" if HasBjdRef or str(TimeColumn).lower() in {"bjd", "btjd", "bkjd"} else ("JD" if Reference or str(TimeColumn).lower() in {"jd", "mjd"} else "unknown")
            #MARK: run progress
            Metadata = {"source_format": "FITS", "hdu_index": HduIndex,
                        "time_column": TimeColumn, "flux_column": FluxColumn,
                        "uncertainty_column": ErrorColumn, "quality_column": QualityColumn,
                        "time_format": FormatName, "time_scale": str(Combined.get("TIMESYS", "unknown")).upper(),
                        "time_unit": "days", "original_time_unit": Unit or "unspecified (assumed days)",
                        "time_reference_offset_days": Reference, "timezero": float(Timezero),
                        "time_unit_assumed": not bool(Unit), "time_convention_ambiguous": FormatName == "unknown" or str(Combined.get("TIMESYS", "unknown")).lower() == "unknown",
                        "mission": Combined.get("MISSION", Combined.get("TELESCOP")),
                        "target_identifier": Combined.get("OBJECT", Combined.get("TICID")),
                        "flux_representation": "as supplied; normalized by analysis"}
            #MARK: exposure times
            ExposureColumn = FindColumn(Names, EXPOSURE_SECONDS_COLUMNS + EXPOSURE_DAYS_COLUMNS + ("exptime", "exposure"))
            Exposures = None
            ExposureUnit = None
            if ExposureColumn:
                NormalizedName = str(ExposureColumn).strip().lower()
                ExposureUnit = (getattr(Columns[ExposureColumn], "unit", None)
                    or ("s" if NormalizedName in EXPOSURE_SECONDS_COLUMNS else
                        "d" if NormalizedName in EXPOSURE_DAYS_COLUMNS else None))
                if ExposureUnit:
                    Exposures = VectorColumn(Data, ExposureColumn) * TimeUnitInDays(ExposureUnit) * 86400.0
            #MARK: exposure times
            # timedel may describe timestamp precision, and a header exptime
            # may be total exposure over a whole table. neither establishes
            # the physical integration time of each sample without provenance.
            Candidates = {}
            for Key in ("TIMEDEL", "EXPTIME", "XPOSURE", "EXPOSURE"):
                try:
                    Value = float(Combined[Key])
                except (KeyError, TypeError, ValueError):
                    continue
                if Math.isfinite(Value) and Value >= 0:
                    Candidates[Key] = {"value": Value,
                        "unit": "seconds" if Key in {"EXPTIME", "EXPOSURE"} else Combined.get("TIMEUNIT", "unknown"),
                        "used_as_sample_exposure": False}
            Metadata["exposure"] = {"source": "FITS per-row column" if Exposures is not None else "unknown",
                "column": ExposureColumn, "original_unit": ExposureUnit,
                "header_candidates": Candidates,
                "note": "Header duration/resolution values require a verified per-sample meaning; use an explicit exposure override when known."}
            return CleanLightCurveArrays(Time, Flux, Errors, Quality, ReturnMetadata,
                                           {"input_rows": len(Time), "invalid_numeric_rows": 0}, Metadata,
                                           ExposureSeconds=Exposures)

    raise ValueError(
        "The FITS file must contain a table with TIME and a flux column "
        "(PDCSAP_FLUX, SAP_FLUX, or FLUX)."
    )


#MARK: core stuffs
def ReadCurveUpload(FileItem, ReturnMetadata=False, **MetadataOptions):
    #MARK: old calls
    # translate old callers here so the file readers use one set of names.
    for OldName, NewName in (("time_format", "TimeFormat"), ("time_scale", "TimeScale"), ("time_unit", "TimeUnit")):
        if OldName in MetadataOptions:
            MetadataOptions[NewName] = MetadataOptions.pop(OldName)
    #MARK: curve uploads
    Filename = UploadedFilename(FileItem)
    ExtensionIsFits = IsFitsFilename(Filename)
    MaxBytes = MAX_FITS_UPLOAD_BYTES if ExtensionIsFits else MAX_CSV_UPLOAD_BYTES
    FileKind = "FITS" if ExtensionIsFits else "CSV"
    Raw = ReadUploadBytes(FileItem, MaxBytes, FileKind)
    # the fits signature also handles a file with the wrong extension.
    IsFits = ExtensionIsFits or Raw[:6] == b"SIMPLE"
    if IsFits:
        Result = ParseFitsBytes(Raw, ReturnMetadata=ReturnMetadata)
    else:
        Result = ParseCsvBytes(Raw, ReturnMetadata=ReturnMetadata, **MetadataOptions)
    #MARK: core stuffs
    if ReturnMetadata:
        Result["input_metadata"].update({"source_file": Filename,
            "source_bytes": len(Raw), "source_sha256": Hashlib.sha256(Raw).hexdigest()})
    return Result


#MARK: old calls
# keep these entry points for the older validation scripts.
def parse_csv_bytes(raw, return_metadata=False, time_format=None, time_scale=None, time_unit=None):
    return ParseCsvBytes(raw, ReturnMetadata=return_metadata, TimeFormat=time_format,
                         TimeScale=time_scale, TimeUnit=time_unit)


def parse_fits_bytes(raw, return_metadata=False):
    return ParseFitsBytes(raw, ReturnMetadata=return_metadata)


def parse_light_curve_upload(file_item, return_metadata=False, **metadata_options):
    return ReadCurveUpload(file_item, ReturnMetadata=return_metadata, **metadata_options)
