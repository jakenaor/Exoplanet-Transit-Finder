"""Small synthetic examples for the download. No private telescope data."""
import csv as Csv
import json as Json
from pathlib import Path

import batman as Batman
import numpy as Np
from astropy.io import fits as Fits


#MARK: a fake planet with a known period
def MakeDemo(Folder):
    Folder = Path(Folder)
    Folder.mkdir(parents=True, exist_ok=True)
    Rng = Np.random.default_rng(20261117)
    Times = Np.linspace(0, 12, 1200)
    Params = Batman.TransitParams()
    Params.t0, Params.per, Params.rp, Params.a = .7, 2.4, .09, 7.5
    Params.inc, Params.ecc, Params.w = 89.2, 0., 90.
    Params.u, Params.limb_dark = [.4804, .1867], "quadratic"
    Flux = Batman.TransitModel(Params, Times).light_curve(Params)
    Flux += Rng.normal(0, .0008, len(Times))
    with (Folder / "synthetic_transit.csv").open("w", newline="") as File:
        Writer = Csv.writer(File)
        Writer.writerow(["Time", "Flux", "flux_err", "exposure_seconds"])
        Writer.writerows(zip(Times, Flux, Np.full(len(Times), .0008), Np.zeros(len(Times))))

    #MARK: short data for the observation viewer
    Times = Np.arange(90) * 120 / 86400
    Flux = 1 + .003 * Np.sin(Np.arange(90) / 11) + Rng.normal(0, .0004, 90)
    with (Folder / "short_observation.csv").open("w", newline="") as File:
        Writer = Csv.writer(File)
        Writer.writerow(["Time", "Flux", "flux_err", "exposure_seconds"])
        Writer.writerows(zip(Times, Flux, Np.full(90, .0004), Np.full(90, 120)))

    #MARK: tiny raw camera thingies, so the fits tab can be tried too
    Header = {"EXPTIME": 10., "INSTRUME": "synthetic-demo", "GAIN": 120, "EGAIN": 2.,
              "OFFSET": 50, "XBINNING": 1, "YBINNING": 1, "XORGSUBF": 0, "YORGSUBF": 0,
              "READMODE": "normal", "READOUTM": "normal", "CCD-TEMP": -10.,
              "OBJECT": "synthetic-field", "FILTER": "R", "TIMESYS": "UTC"}
    Y, X = Np.indices((128, 192))
    def Write(Kind, Name, Data, Extra):
        Output = Folder / "FITS Demo" / Kind
        Output.mkdir(parents=True, exist_ok=True)
        Hdu = Fits.PrimaryHDU(Np.asarray(Data, dtype=Np.float32))
        for Key, Value in {**Header, **Extra}.items():
            Hdu.header[Key] = Value
        Hdu.writeto(Output / Name, overwrite=True)
    for Index in range(3):
        Write("Darks", f"dark_{Index + 1:02d}.fits", 500 + Rng.normal(0, .05, X.shape), {"IMAGETYP": "DARK"})
    for Index in range(12):
        Dx, Dy = Index * .08, Index * -.05
        Transparency = .8 + .02 * Index
        Depth = .98 if 4 <= Index <= 7 else 1.
        Target = 1500 * Transparency * Depth * Np.exp(-((X - 48 - Dx) ** 2 + (Y - 50 - Dy) ** 2) / 8)
        Comp = 1800 * Transparency * Np.exp(-((X - 136 - Dx) ** 2 + (Y - 72 - Dy) ** 2) / 8)
        Write("Science", f"science_{Index + 1:02d}.fits", 600 + Target + Comp + Rng.normal(0, .5, X.shape),
              {"IMAGETYP": "LIGHT", "DATE-OBS": f"2026-01-01T00:{Index:02d}:00"})
    Truth = {"synthetic_data": True, "transit_period_days": 2.4, "transit_epoch_days": .7,
             "radius_ratio": .09, "csv_time_format": "relative", "csv_time_scale": "unknown",
             "fits_target_xy": [48, 50], "fits_comparison_xy": [136, 72],
             "fits_aperture_radius": 8, "fits_sky_inner": 12, "fits_sky_outer": 20,
             "fits_injected_relative_dimming": .02, "fits_dim_frames": [5, 6, 7, 8],
             "note": "Generated examples, not observations of a real planet. FITS example spans 11 minutes and cannot establish a period."}
    (Folder / "expected.json").write_text(Json.dumps(Truth, indent=2) + "\n", encoding="utf-8")
