"""Dark-matched aperture measurements for the image tab. No period search here."""
import base64 as Base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv as Csv
import io as Io
import json as Json
import math as Math
from pathlib import Path
import struct as Struct
import zlib as Zlib

import numpy as Np
from astropy.io import fits as Fits
from astropy.stats import sigma_clip
from astropy.time import Time
from scipy.ndimage import gaussian_filter


#MARK: image headers
MatchKeys = ("INSTRUME", "XBINNING", "YBINNING", "GAIN", "OFFSET", "READMODE", "READOUTM", "XORGSUBF", "YORGSUBF", "EGAIN")
HeaderKeys = MatchKeys + ("ROTATOR", "OBJECT", "FILTER", "EXPTIME", "EXPOSURE", "CCD-TEMP", "SET-TEMP", "EGAIN", "SATURATE", "DATE-OBS", "TIME-OBS", "DATE-AVG", "TIME-AVG", "CALSTAGE", "DARKCORR", "JD-OBS", "MJD-OBS", "TIMESYS", "IMAGETYP", "BAYERPAT", "BITPIX", "BSCALE", "BZERO", "BLANK")


def Number(Value):
    try:
        Value = float(Value)
        return Value if Math.isfinite(Value) else None
    except (TypeError, ValueError):
        return None


def ImageInfo(FilePath, Name=None):
    with Fits.open(FilePath, memmap=True, do_not_scale_image_data=True) as File:
        for Index, Hdu in enumerate(File):
            if isinstance(Hdu, (Fits.PrimaryHDU, Fits.ImageHDU, Fits.CompImageHDU)) and Hdu.header.get("NAXIS") == 2:
                Header = Hdu.header
                Stage = str(Header.get("CALSTAGE", File[0].header.get("CALSTAGE", ""))).casefold()
                Corrected = str(Header.get("DARKCORR", File[0].header.get("DARKCORR", ""))).casefold()
                if "dark" in Stage or Corrected in ("true", "t", "yes", "1", "complete", "done"):
                    raise ValueError("This image is already marked dark-corrected. Upload raw images to avoid subtracting darks twice.")
                Width, Height = int(Header["NAXIS1"]), int(Header["NAXIS2"])
                if min(Width, Height) < 8 or max(Width, Height) > 32768 or Width * Height > 80000000:
                    raise ValueError("Images must have 8–32768 pixels per side and at most 80 megapixels.")
                Values = {Key: Header.get(Key, File[0].header.get(Key)) for Key in HeaderKeys}
                for Key, Value in list(Values.items()):
                    if isinstance(Value, float) and not Math.isfinite(Value):
                        Values[Key] = None
                return {"path": str(FilePath), "name": Name or Path(FilePath).name,
                        "hdu": Index, "width": Width, "height": Height, "header": Values,
                        "exposure": Number(Values.get("EXPTIME") or Values.get("EXPOSURE"))}
    raise ValueError("This FITS contains no 2D image. Table light curves belong in the Transit Finder tab.")


#MARK: small pieces, not a whole camera frame
def ReadPatch(Frame, Bounds):
    X0, Y0, X1, Y1 = Bounds
    with Fits.open(Frame["path"], memmap=True, do_not_scale_image_data=True) as File:
        Raw = File[Frame["hdu"]].section[Y0:Y1, X0:X1]
        Data = Np.array(Raw, dtype=Np.float32, copy=True)
        Blank = Frame["header"].get("BLANK")
        if Blank is not None:
            Data[Raw == Blank] = Np.nan
        Data *= float(Frame["header"].get("BSCALE") or 1)
        Data += float(Frame["header"].get("BZERO") or 0)
        return Data


def CheckStop(Stop):
    if Stop is not None and Stop.is_set():
        raise InterruptedError("Image processing cancelled.")


#MARK: a small preview that still keeps faint stars
def MakePreview(Frame):
    Width, Height = Frame["width"], Frame["height"]
    Factor = max(1, int(Math.ceil(max(Width, Height) / 1000)))
    W, H = int(Math.ceil(Width / Factor)), int(Math.ceil(Height / Factor))
    Binned = Np.empty((H, W), dtype=Np.float32)
    BlockRows = max(1, min(24, 2000000 // (Width * Factor)))
    for Y0 in range(0, Height, Factor * BlockRows):
        Patch = ReadPatch(Frame, (0, Y0, Width, min(Height, Y0 + Factor * BlockRows)))
        Rows = int(Math.ceil(len(Patch) / Factor))
        Pad = Np.full((Rows * Factor, W * Factor), Np.nan, dtype=Np.float32)
        Pad[:Patch.shape[0], :Width] = Patch
        Binned[Y0 // Factor:Y0 // Factor + Rows] = Np.nanmean(Pad.reshape(Rows, Factor, W, Factor), axis=(1, 3))
    Finite = Binned[Np.isfinite(Binned)]
    if not len(Finite):
        raise ValueError("The reference image contains no finite pixels.")
    Low, High = Np.percentile(Finite, [5, 99.9])
    High = max(High, Low + 1)
    Pixels = Np.arcsinh(10 * Np.clip((Np.nan_to_num(Binned, nan=Low) - Low) / (High - Low), 0, 1)) / Np.arcsinh(10)
    Pixels = (Pixels * 255).astype(Np.uint8)
    def Chunk(Name, Data):
        return Struct.pack(">I", len(Data)) + Name + Data + Struct.pack(">I", Zlib.crc32(Name + Data) & 0xffffffff)
    Raw = b"".join(b"\0" + Row.tobytes() for Row in Pixels)
    Png = b"\x89PNG\r\n\x1a\n" + Chunk(b"IHDR", Struct.pack(">IIBBBBB", W, H, 8, 0, 0, 0, 0)) + Chunk(b"IDAT", Zlib.compress(Raw)) + Chunk(b"IEND", b"")
    return {"width": W, "height": H, "image_width": Width, "image_height": Height,
            "factor": Factor, "png": Base64.b64encode(Png).decode(), "name": Frame["name"],
            "header": Frame["header"], "note": "Raw, block-averaged preview; photometry uses original pixels."}


#MARK: dark frames must actually match
def SameSetting(A, B):
    X, Y = Number(A), Number(B)
    return Math.isclose(X, Y, rel_tol=1e-8, abs_tol=1e-8) if X is not None and Y is not None else str(A).strip().casefold() == str(B).strip().casefold()


def MatchingDarks(Frame, Darks):
    # shitty idea: scale a raw dark to fit another exposure.
    # Dark *= LightExposure / DarkExposure
    # that scales the bias too. just use matching darks.
    Matched = []
    for Dark in Darks:
        if (Frame["width"], Frame["height"]) != (Dark["width"], Dark["height"]):
            continue
        if Frame["exposure"] is None or Dark["exposure"] is None or Frame["exposure"] <= 0 or Dark["exposure"] <= 0 or not Math.isclose(Frame["exposure"], Dark["exposure"], rel_tol=1e-5, abs_tol=1e-8):
            continue
        if any(Frame["header"].get(Key) is not None and Dark["header"].get(Key) is not None and not SameSetting(Frame["header"][Key], Dark["header"][Key]) for Key in MatchKeys):
            continue
        A, B = Number(Frame["header"].get("CCD-TEMP")), Number(Dark["header"].get("CCD-TEMP"))
        if A is not None and B is not None and abs(A - B) > 1:
            continue
        Matched.append(Dark)
    return Matched


def DarkPatch(Darks, Bounds, Stop):
    X0, Y0, X1, Y1 = Bounds
    Shape = (Y1 - Y0, X1 - X0)
    Median, Variance = Np.empty(Shape, dtype=Np.float32), Np.zeros(Shape, dtype=Np.float32)
    # even a large dark pool stays in small row tiles.
    Tile = max(1, 8000000 // (4 * len(Darks) * Shape[1]))
    for Y in range(Y0, Y1, Tile):
        CheckStop(Stop)
        Stack = Np.stack([ReadPatch(Dark, (X0, Y, X1, min(Y1, Y + Tile))) for Dark in Darks])
        Mid = Np.median(Stack, axis=0)
        Median[Y - Y0:Y - Y0 + len(Mid)] = Mid
        if len(Darks) > 1:
            Scatter = 1.4826 * Np.median(Np.abs(Stack - Mid), axis=0)
            Variance[Y - Y0:Y - Y0 + len(Mid)] = (Math.pi / 2) * Scatter ** 2 / len(Darks)
    return Median, Variance


#MARK: aperture and sky thingies
def MeasureStar(Frame, Darks, Position, Options, Stop=None):
    Radius, Inner, Outer, Search = (Options[Key] for Key in ("radius", "inner", "outer", "tracking"))
    X, Y = Position
    Half = int(Math.ceil(Outer + Search + 4))
    X0, Y0 = max(0, int(X) - Half), max(0, int(Y) - Half)
    X1, Y1 = min(Frame["width"], int(X) + Half + 1), min(Frame["height"], int(Y) + Half + 1)
    Bounds = (X0, Y0, X1, Y1)
    Raw = ReadPatch(Frame, Bounds)
    Dark, DarkVariance = DarkPatch(Darks, Bounds, Stop)
    Data = Raw - Dark
    if not Np.all(Np.isfinite(Data)):
        raise ValueError("NONFINITE_APERTURE_PATCH")
    YY, XX = Np.indices(Data.shape, dtype=float)
    Sky = float(Np.median(Data))
    Noise = max(1e-6, 1.4826 * float(Np.median(Np.abs(Data - Sky))))
    SearchMask = (XX + X0 - X) ** 2 + (YY + Y0 - Y) ** 2 <= Search ** 2
    Smoothed = gaussian_filter(Data - Sky, 1)
    Peak = Np.unravel_index(Np.argmax(Np.where(SearchMask, Smoothed, -Np.inf)), Data.shape)
    if Smoothed[Peak] < 3 * Noise:
        raise ValueError("STAR_NOT_FOUND")
    Core = (XX - Peak[1]) ** 2 + (YY - Peak[0]) ** 2 <= max(2, Radius * .7) ** 2
    Weights = Np.where(Core, Np.maximum(Data - Sky, 0), 0)
    Total = float(Weights.sum())
    if Total <= 0 or Np.count_nonzero(Core & (Data - Sky > 3 * Noise)) < 3:
        raise ValueError("STAR_NOT_FOUND")
    Cx, Cy = float((Weights * XX).sum() / Total), float((Weights * YY).sum() / Total)
    if Math.hypot(Cx + X0 - X, Cy + Y0 - Y) > Search:
        raise ValueError("TRACKING_LIMIT")
    if min(Cx + X0, Cy + Y0, Frame["width"] - 1 - Cx - X0, Frame["height"] - 1 - Cy - Y0) < Outer:
        raise ValueError("APERTURE_AT_EDGE")
    R2 = (XX - Cx) ** 2 + (YY - Cy) ** 2
    SkyPixels = Data[(R2 >= Inner ** 2) & (R2 <= Outer ** 2)]
    Clean = sigma_clip(SkyPixels, sigma=3, maxiters=5, cenfunc="median", stdfunc="mad_std").compressed()
    if len(Clean) < 30:
        raise ValueError("NOT_ENOUGH_SKY")
    Background = float(Np.median(Clean))
    Sigma = max(1e-6, float(Np.std(Clean, ddof=1)))
    # checking every empty sky pixel 64 times is fucking idiocy.
    # Aperture += ((XX + Dx - Cx) ** 2 + (YY + Dy - Cy) ** 2 <= Radius ** 2) / 64
    # only the circle edge needs the subpixel thingy.
    Edge = (R2 >= (Radius - .71) ** 2) & (R2 <= (Radius + .71) ** 2)
    Aperture = (R2 < (Radius - .71) ** 2).astype(float)
    EdgeX, EdgeY = XX[Edge], YY[Edge]
    EdgeWeights = Np.zeros(len(EdgeX))
    for Dy in (Np.arange(8) + .5) / 8 - .5:
        for Dx in (Np.arange(8) + .5) / 8 - .5:
            EdgeWeights += ((EdgeX + Dx - Cx) ** 2 + (EdgeY + Dy - Cy) ** 2 <= Radius ** 2) / 64
    Aperture[Edge] = EdgeWeights
    Area = float(Aperture.sum())
    Flux = float(Np.sum(Aperture * (Data - Background)))
    # what the fuck even is this i need to stop drinking so much coffee
    # sky noise + dark noise + the uncertainty in the sky level.
    Var = float(Np.sum(Aperture ** 2 * (Sigma ** 2 + DarkVariance)) + Area ** 2 * (Math.pi / 2) * Sigma ** 2 / len(Clean))
    Gain = Number(Frame["header"].get("EGAIN"))
    if Gain is not None and Gain > 0:
        Var += float(Np.sum(Aperture ** 2 * Np.maximum(Data - Background, 0) / Gain))
    Saturation = Number(Frame["header"].get("SATURATE"))
    Bits = Number(Frame["header"].get("BITPIX"))
    if Saturation is None and Bits in (8, 16, 32):
        Saturation = ((255 if Bits == 8 else 2 ** (Bits - 1) - 1)) * float(Frame["header"].get("BSCALE") or 1) + float(Frame["header"].get("BZERO") or 0)
    if Saturation is not None and Np.any((Raw >= Saturation) & (Aperture > 0)):
        raise ValueError("SATURATED_STAR")
    if not Math.isfinite(Flux) or not Math.isfinite(Var):
        raise ValueError("NONFINITE_PHOTOMETRY")
    if Flux <= 0:
        raise ValueError("NONPOSITIVE_STAR_FLUX")
    Error = Math.sqrt(max(Var, 1e-12))
    if Flux / Error < 5:
        raise ValueError("LOW_STAR_SNR")
    return {"flux": Flux, "error": Error, "rate": Flux / Frame["exposure"],
            "rate_error": Error / Frame["exposure"], "x": Cx + X0, "y": Cy + Y0,
            "sky": Background, "area": Area}


#MARK: clock thingy
def FrameClock(Frame, Meaning):
    Header = Frame["header"]
    Scale = str(Header.get("TIMESYS") or "utc").strip().lower()
    Scale = "utc" if Scale == "ut" else Scale
    if Scale not in ("utc", "tai", "tt", "tdb", "tcg", "tcb", "ut1"):
        raise ValueError("UNSUPPORTED_TIME_SCALE")
    if Scale == "ut1":
        raise ValueError("UT1_TIMING_REQUIRES_EXTERNAL_EARTH_ROTATION_DATA")
    def Calendar(Value, ClockKey):
        Text = str(Value).strip().removesuffix("Z")
        if len(Text) == 10:
            if not Header.get(ClockKey):
                raise ValueError("DATE_WITHOUT_TIME")
            Text += "T" + str(Header[ClockKey]).strip()
        return float(Time(Text, scale=Scale).utc.jd)
    if Header.get("DATE-AVG"):
        return Calendar(Header["DATE-AVG"], "TIME-AVG"), "DATE-AVG midpoint"
    if Header.get("DATE-OBS"):
        Value, Source = Calendar(Header["DATE-OBS"], "TIME-OBS"), "DATE-OBS"
    elif Number(Header.get("JD-OBS")) is not None:
        Value, Source = float(Time(Number(Header["JD-OBS"]), format="jd", scale=Scale).utc.jd), "JD-OBS"
    elif Number(Header.get("MJD-OBS")) is not None:
        Value, Source = float(Time(Number(Header["MJD-OBS"]), format="mjd", scale=Scale).utc.jd), "MJD-OBS"
    else:
        raise ValueError("MISSING_TIMESTAMP")
    if Meaning == "start":
        Value += Frame["exposure"] / 172800
    return Value, Source + (" assumed exposure-start" if Meaning == "start" else " declared midpoint")


#MARK: making the light curve
def ValidateOptions(Values, Reference):
    Options = {}
    for Key, Default, Low, High in (("radius", 8, 2, 128), ("inner", 12, 3, 192), ("outer", 20, 5, 256), ("tracking", 12, 1, 64), ("workers", 4, 1, 4)):
        Value = Number(Values.get(Key, Default))
        if Value is None or not Low <= Value <= High or (Key == "workers" and Value != int(Value)):
            raise ValueError(f"{Key} must be between {Low} and {High}.")
        Options[Key] = int(Value) if Key == "workers" else Value
    if not Options["radius"] < Options["inner"] < Options["outer"]:
        raise ValueError("Choose aperture radius < sky inner radius < sky outer radius.")
    Stars = Values.get("stars")
    if not isinstance(Stars, list) or not 1 <= len(Stars) <= 9:
        raise ValueError("Select one target and up to eight comparison stars in the preview.")
    Points = []
    for Star in Stars:
        if not isinstance(Star, list) or len(Star) != 2 or any(Number(V) is None for V in Star):
            raise ValueError("Invalid star coordinates.")
        X, Y = map(float, Star)
        if not 0 <= X < Reference["width"] or not 0 <= Y < Reference["height"]:
            raise ValueError("A selected star is outside the image.")
        if any(Math.hypot(X - A, Y - B) < 2 * Options["radius"] for A, B in Points):
            raise ValueError("Selected star apertures overlap. Choose separate stars.")
        Points.append([X, Y])
    Options["stars"] = Points
    Options["timestamp"] = Values.get("timestamp", "start")
    if Options["timestamp"] not in ("start", "midpoint"):
        raise ValueError("Choose exposure-start or midpoint timestamps.")
    return Options


def BuildLightCurve(Science, Darks, Options, Output, Progress, Stop=None):
    if not Science or not Darks:
        raise ValueError("Upload both science images and dark frames.")
    for Key in ("OBJECT", "FILTER", "ROTATOR") + MatchKeys:
        Values = [Frame["header"][Key] for Frame in Science if Frame["header"].get(Key) is not None]
        if Values and any(not SameSetting(Values[0], Value) for Value in Values[1:]):
            raise ValueError(f"Science images have mixed {Key} values. Process one target field, filter and camera setup per run.")
    if any((Frame["width"], Frame["height"]) != (Science[0]["width"], Science[0]["height"]) for Frame in Science):
        raise ValueError("Science image dimensions differ. Process each camera setup separately.")
    Pools = [MatchingDarks(Frame, Darks) for Frame in Science]
    Rows = []
    def One(Item):
        Index, Frame = Item
        Row = {"source_file": Frame["name"], "quality": 0, "qc_flags": "", "Time": None, "Flux": None, "flux_err": None,
               "exposure_seconds": Frame["exposure"], "clock_jd_nominal": None, "target_rate": None, "comparison_rate": None,
               "date_obs": Frame["header"].get("DATE-OBS"), "dark_count": len(Pools[Index]), "stars": []}
        try:
            CheckStop(Stop)
            if Frame["exposure"] is None or Frame["exposure"] <= 0:
                raise ValueError("MISSING_EXPOSURE")
            Row["clock_jd_nominal"], Row["clock_source"] = FrameClock(Frame, Options["timestamp"])
            if not Pools[Index]:
                raise ValueError("NO_MATCHING_DARKS")
            Target = MeasureStar(Frame, Pools[Index], Options["stars"][0], Options, Stop)
            Measurements = [Target]
            Row["stars"] = Measurements
            Row["target_rate"], Row["target_rate_error"] = Target["rate"], Target["rate_error"]
            for Star in Options["stars"][1:]:
                Measurements.append(MeasureStar(Frame, Pools[Index], Star, Options, Stop))
            Shifts = Np.array([[Star["x"] - Position[0], Star["y"] - Position[1]] for Star, Position in zip(Measurements, Options["stars"])])
            if len(Shifts) > 1 and Np.max(Np.linalg.norm(Shifts - Np.median(Shifts, axis=0), axis=1)) > max(3, Options["radius"] / 2):
                raise ValueError("INCONSISTENT_STAR_TRACKING")
            Value, Error = Target["rate"], Target["rate_error"]
            if len(Measurements) > 1:
                Comparison = sum(Star["rate"] for Star in Measurements[1:])
                ComparisonError = Math.sqrt(sum(Star["rate_error"] ** 2 for Star in Measurements[1:]))
                Row["comparison_rate"] = Comparison
                Value = Target["rate"] / Comparison
                Error = Math.sqrt((Target["rate_error"] / Comparison) ** 2 + (Target["rate"] * ComparisonError / Comparison ** 2) ** 2)
            Row["Flux"], Row["flux_err"] = Value, Error
        except InterruptedError:
            raise
        except Exception as Exc:
            Row["quality"], Row["qc_flags"] = 1, str(Exc)[:240]
        return Row
    with ThreadPoolExecutor(max_workers=Options["workers"]) as Pool:
        Futures = [Pool.submit(One, Item) for Item in enumerate(Science)]
        for Future in as_completed(Futures):
            try:
                CheckStop(Stop)
                Rows.append(Future.result())
                Progress(len(Rows), len(Science), Rows[-1]["source_file"])
            except BaseException:
                for Pending in Futures:
                    Pending.cancel()
                raise
    Rows.sort(key=lambda Row: (Row["clock_jd_nominal"] is None, Row["clock_jd_nominal"] or 0, Row["source_file"]))
    Timed = [Row["clock_jd_nominal"] for Row in Rows if Row["clock_jd_nominal"] is not None]
    Origin = min(Timed) if Timed else None
    Seen = set()
    for Row in Rows:
        Clock = Row["clock_jd_nominal"]
        if Clock is not None:
            Row["Time"] = Clock - Origin
            if Row["quality"] == 0:
                if Clock in Seen:
                    Row["quality"], Row["qc_flags"] = 1, "DUPLICATE_TIMESTAMP"
                else:
                    Seen.add(Clock)
    Good = [Row for Row in Rows if Row["quality"] == 0]
    Scale = float(Np.median([Row["Flux"] for Row in Good])) if Good else None
    for Row in Rows:
        if Row["quality"] == 0:
            Row["Flux"] /= Scale
            Row["flux_err"] /= Scale
        else:
            Row["Flux"], Row["flux_err"] = None, None
    Warnings = ["Dark-only reduction: no flat-field correction.", "Relative midpoint days from the nominal input clock; no barycentric correction. Clock accuracy and time scale are unverified.",
                "Flux is divided by the median of accepted measurements, not a fitted out-of-transit baseline.", "Errors omit scintillation, flat-field and registration systematics; shared dark/reference correlations are not modeled.",
                "Local centroid tracking only: split meridian flips, rotations and different fields into separate runs."]
    if len(Options["stars"]) == 1:
        Warnings.append("Target-only photometry: no comparison-star correction. Atmospheric transparency and instrumental trends remain in the light curve.")
    if any((Number(Frame["header"].get("EGAIN")) or 0) <= 0 for Frame in Science):
        Warnings.append("Electron/ADU gain unavailable for some frames: their errors include empirical sky and dark uncertainty but omit source shot noise. Camera GAIN is not substituted.")
    if any(len(Pool) == 1 for Pool in Pools):
        Warnings.append("Some frames have only one matching dark; master-dark random uncertainty is unavailable there.")
    if any(Frame["header"].get("CCD-TEMP") is None or any(Frame["header"].get(Key) is None for Key in MatchKeys) for Frame in Science + Darks):
        Warnings.append("Some camera/temperature fields are missing. Known mismatches are rejected; missing values cannot verify a complete calibration match.")
    if any(Frame["header"].get("BAYERPAT") for Frame in Science):
        Warnings.append("Bayer mosaic detected: apertures sum the original mosaic without demosaicing or color calibration.")
    if any("dark" not in str(Frame["header"].get("IMAGETYP", "")).casefold() for Frame in Darks):
        Warnings.append("Some uploaded darks have missing or different IMAGETYP labels; their user-selected dark role is recorded.")
    Metadata = {"method": "matched median-dark subtraction on original-pixel cutouts; fractional circular aperture; clipped annulus; " + ("fixed comparison ensemble" if len(Options["stars"]) > 1 else "target-only photometry"),
                "time_format": "relative", "time_scale": "unknown", "time_unit": "days", "time_origin_jd_nominal": Origin,
                "timestamp_policy": Options["timestamp"], "normalization_median": Scale, "flat_field_applied": False,
                "dark_scaling_applied": False, "workers": Options["workers"], "options": Options,
                "total_frames": len(Rows), "usable_frames": len(Good), "warnings": Warnings,
                "sources": [{Key: Value for Key, Value in Frame.items() if Key != "path"} for Frame in Science],
                "darks": [{Key: Value for Key, Value in Frame.items() if Key != "path"} for Frame in Darks], "measurements": Rows}
    CheckStop(Stop)
    Output = Path(Output)
    Output.mkdir(parents=True, exist_ok=True)
    Keys = ("Time", "Flux", "flux_err", "exposure_seconds", "quality", "qc_flags", "source_file", "target_rate", "target_rate_error", "comparison_rate", "date_obs", "clock_jd_nominal", "dark_count")
    Buffer = Io.StringIO()
    Writer = Csv.DictWriter(Buffer, fieldnames=Keys, extrasaction="ignore")
    Writer.writeheader()
    Writer.writerows(Rows)
    (Output / "lightcurve.csv").write_text(Buffer.getvalue(), encoding="utf-8")
    (Output / "metadata.json").write_text(Json.dumps(Metadata, indent=2, allow_nan=False), encoding="utf-8")
    Provenance = {Key: Metadata[Key] for Key in ("method", "time_format", "time_scale", "time_unit", "time_origin_jd_nominal", "timestamp_policy", "normalization_median", "flat_field_applied", "dark_scaling_applied", "workers", "options", "warnings")}
    return {"provenance": Provenance, "total_frames": len(Rows), "usable_frames": len(Good), "warnings": Warnings,
            "output_directory": str(Output), "preview": [{Key: Row[Key] for Key in ("Time", "Flux", "flux_err", "quality", "qc_flags")} for Row in Rows[::max(1, len(Rows) // 2000)]]}

