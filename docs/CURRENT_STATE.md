# Current State

Last updated: 2026-06-02

## Canonical Location

Use this repo as the source of truth:

```text
/Users/jakenaor/Documents/Coding Stuff/Space/Exoplanet-Transit-Finder
```

The app is currently nested at:

```text
Exoplanet data parsing tool/main.py
```

A similarly named non-repo folder and an earlier typo-named app folder were used by mistake:

```text
/Users/jakenaor/Documents/Coding Stuff/Space/Exoplaned data parsing tool
Exoplaned data parsing tool/
```

Future sessions should work in `Exoplanet-Transit-Finder` and the tracked `Exoplanet data parsing tool/` folder, not either typo path. See [Repo Map](REPO_MAP.md) for the local canonical file layout.

## Product Goal

Build a local Python web app for exoplanet transit analysis. The user uploads a CSV with two columns, `Time` and `Flux`. The app plots the light curve, detects transit-like dips, boxes transits, estimates orbital period, provides significance estimates, and supports exploration/editing/export.

The `Time` column is treated as continuous Julian dates. UI plots show days since the first observation for time-series views, while retaining the original JD reference in the Analysis panel and export data.

## Current Working Features

- Localhost app served by `python3 main.py` using only Python stdlib for HTTP serving.
- CSV upload with case-insensitive `Time`/`Flux` parsing.
- Large dataset handling with downsampling for plotting.
- Raw clipped, full cleaned, transit zoom, and phase-folded chart modes.
- Robust clipping and moving-average smoothing for visualization.
- Transit detection using scipy peak/prominence logic with fallback threshold detection.
- BLS orbital period estimate using `astropy.timeseries.BoxLeastSquares`.
- Binned-BLS fallback period estimate when `astropy` is unavailable or broken.
- Period displayed in Julian days.
- Period search controls:
  - Minimum period.
  - Maximum period.
  - Period candidate list with power/SDE values.
  - Period search bounds included in JSON export.
- Chi-squared p-value estimate for the fitted transit model, displayed as a percentage.
- Transit boxes drawn around the local transit curve instead of extending full chart height.
- Keyboard and mouse viewport controls:
  - Up arrow: zoom in around pointer.
  - Down arrow: zoom out around pointer.
  - Left arrow: expand sideways.
  - Right arrow: contract sideways.
  - Click/drag: pan viewport.
- Manual transit box editing:
  - Toggle `Edit boxes`.
  - Select a box.
  - Drag left/right edges to resize.
  - Drag inside a box to move it.
  - Table updates immediately.
  - Sidebar period and chi-squared p-value recalculate after manual edits.
- Detection sensitivity controls:
  - Strictness.
  - Smoothing.
  - Minimum depth.
  - Minimum duration.
  - Maximum duration.
  - Reset detection.
- Transit depth estimates:
  - Raw flux depth.
  - Depth fraction, percent, and ppm.
  - Radius-ratio estimate using `Rp/Rs = sqrt(depth fraction)`.
  - Flux near a positive baseline is treated as fractional flux; residual ppm-style flux is treated as ppm directly.
- False-positive and TLS-style diagnostics:
  - Warnings panel for low-SNR, few-transit, no-period, provisional-period, weak-significance, odd/even mismatch, inconsistent-depth, large-radius-ratio, and sparse-sampling cases.
  - Depth SNR, period SDE, and reduced chi-squared metrics in the Analysis panel.
  - Warning and diagnostic fields included in summary JSON exports.
- Export controls:
  - Transit CSV, including edited boxes and original JD columns.
  - Current graph PNG.
  - Summary JSON with metrics, detection options, and transits.

## Important Implementation Decisions

- Keep the app as a single `main.py` for now. This keeps setup simple for the current local workflow.
- Use `numpy`, `scipy`, and `astropy` for numerical and astronomy-specific operations instead of hand-rolling everything.
- Use the repo-local `.venv` as the VS Code/Pylance interpreter. `.vscode/settings.json` points Pylance at `.venv/bin/python`.
- Treat `Time` as Julian dates and convert to relative days for graph readability.
- Use BLS for orbital period, because simple averaging of nearby detected boxes was badly wrong for this dataset.
- Treat broad automated period-search results as candidate rankings, not ground truth. The Kepler sample previously showed a strong alias around `294` days while a constrained `380-390` day search returned about `386.16` days.
- Use phase-folding as the primary validation view for repeated transit structure.
- Manual box edits are currently frontend-local. They update the displayed table and metrics but do not round-trip to the backend.
- Detection controls require clicking `Analyze CSV` again. They are not live-updated while dragging sliders.
- Chi-squared p-value is an approximate model-vs-flat significance metric, not a literal probability that a planet is real.
- `docs/CURRENT_STATE.md` and `docs/REPO_MAP.md` are intentionally ignored by git. They remain local working references, not tracked project files.

## Things That Worked

- BLS and the binned-BLS fallback replaced naive average-gap period estimation.
- Period min/max controls made period aliases visible and controllable; constraining the Kepler sample to `380-390` days previously returned about `386.16` days.
- A repo-local `.venv` fixed Pylance missing-import warnings for `numpy`, `scipy`, and `astropy`.
- Phase-folded view made the repeated transit visually obvious when centered on phase 0.
- Local curve-bounded boxes are much more readable than full-height boxes.
- Manual editing is useful for correcting imperfect automatic boxes.
- Detection strictness and smoothing controls actually affect candidate counts; for example, lowering strictness on the Kepler sample found more candidates than the default.
- Export JSON/CSV/PNG provides a clean way to take analysis results out of the app.

## Things That Did Not Work Or Needed Correction

- Initial Pylance reported missing `numpy`; this was fixed by creating `.venv`, installing `requirements.txt`, and adding `.vscode/settings.json`.
- An earlier global Python environment had a broken `astropy` import due to a dependency mismatch. The repo-local `.venv` imports `numpy`, `scipy`, and `astropy` successfully.
- Early plots were unreadable because the raw data had large outliers and too many points. Clipping, smoothing, and downsampling were added.
- Early transit detection found only one transit. Detection was broadened and later improved with prominence logic.
- Early box drawing covered too much vertical space. It now boxes the local transit curve region.
- Simple average of detected transit centers was not reliable for orbital period because the detector can find many local dips that are not consecutive orbital events. BLS is now preferred.
- The wrong local folder was used for several edits before copying the final app into the correct Git repo. The correct repo is now documented here.
- Binding localhost from the sandbox may fail with `Operation not permitted`; running `.venv/bin/python main.py` may need escalated execution in this environment.

## Current Verification Notes

Known sample file previously used during testing:

```text
/Users/jakenaor/Downloads/kepler_Kepler-452b_transit_data_20.csv
```

As of 2026-06-02, that sample file is not present at the old path, so it was not revalidated in this update.

Previous observed verification result at default detection settings:

- Total points: `71,963`
- Detected transits: `41`
- BLS period: about `294.471929` days
- Binned-BLS fallback period: about `294.363098` days
- With period bounds `380-390` days, binned-BLS fallback returned about `386.162403` days
- Phase-folded points: `12,000` plotted points
- Phase-folded bins: about `280` median bins
- Chi-squared p-value: extremely small, displayed as less than a tiny percentage in the UI

Commands used for basic checks:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/transit-pycache .venv/bin/python -m py_compile "Exoplanet data parsing tool/main.py"
.venv/bin/python "Exoplanet data parsing tool/main.py"
```

Browser JavaScript has also been syntax-checked with macOS `osascript -l JavaScript` when Node was unavailable.

## Known Limitations

- Single-file app is growing large; future work may benefit from splitting Python analysis, HTML template, CSS, and JavaScript.
- Manual box edits are not persisted after re-analysis or page reload.
- The p-value recomputed after manual edits uses frontend plotted/smoothed data, not the full backend dataset. This is useful for feedback but less rigorous than a backend recompute.
- Exports are client-side downloads.
- False-positive warnings are heuristic and advisory; they do not prove or disprove that a candidate is planetary.
- Top period candidates are exposed, but harmonics/aliases are not yet analyzed deeply.
- Broad automated period search can still prefer aliases. Use period min/max controls when a target period range is known.

## TLS Parity Roadmap

This project is intended to become a more user-friendly version of Transit Least Squares (TLS). Missing TLS-inspired capabilities to add after the current feature sequence:

- Transit-shaped model fitting:
  - Add an optional TLS-style search mode using limb-darkened transit templates instead of only BLS boxes/local dip boxes.
  - Show model overlays in time view and phase-folded view.
  - Support trapezoid/grazing-transit templates for V-shaped or box-like events.
- Stellar parameter priors:
  - Let users enter or import stellar radius, stellar mass/density, and limb-darkening coefficients.
  - Use stellar priors to constrain physically plausible period and duration grids.
  - Surface missing/invalid stellar-prior warnings clearly.
- Search controls:
  - Period minimum/maximum controls are implemented.
  - Add duration minimum/maximum controls tied to physically plausible ranges.
  - Period search bounds are exported in JSON; full period/duration grid visualization is still pending.
  - Add quick-look binning/resampling controls for large or short-cadence datasets.
- Detection statistics:
  - Show SDE and raw SDE.
  - Show false alarm probability estimates and explain white-noise vs red-noise caveats.
  - Show chi-squared and reduced chi-squared for the best model.
  - Show period uncertainty, epoch/T0, duration, depth, mean depth uncertainty, SNR, and per-transit SNR.
  - Show odd/even transit depth mismatch as an eclipsing-binary warning.
  - Show transit count, distinct transit count, empty transit count, per-transit point counts, and before/in/after-transit phase-bin counts.
  - Show individual transit depths and depth uncertainties.
- Transit masks and iterative searches:
  - Generate an in-transit mask for the best candidate.
  - Let users hide, highlight, or export in-transit/out-of-transit points.
  - Add "cleanse detected signal and search again" for multi-planet systems.
- Data cleaning and uncertainties:
  - Accept an optional flux uncertainty column.
  - Clean NaN, None, infinite, masked, and invalid flux/error values with a user-visible report.
  - Preserve a reversible cleaning log for exports.
- Power-spectrum inspection:
  - Add a periodogram/SDE-ogram view.
  - Expose top candidate periods, harmonics, aliases, and the median-smoothed vs raw power spectrum.
  - Flag edge-effect or phase-wrapping artifacts where relevant.
- Performance/user feedback:
  - Add progress reporting for long searches.
  - Add a fast preview mode before full-resolution search.
  - Consider installing `transitleastsquares` as an optional backend dependency once the UI has a stable search workflow.

## Planned Feature Order

The user asked to proceed through features 1 through 8. Current status:

1. Phase-folded light curve: done.
2. Manual transit box editing: done.
3. Detection sensitivity controls: done.
4. Export results: done.
5. Transit depth in percent/ppm and radius-ratio estimate: done.
6. False-positive warnings: done.
7. Data cleaning panel: next.
8. Reset/home view button: pending.

Additional useful future features after step 8:

- Transit prediction from period and epoch.
- Better candidate-period ranking with explicit harmonic/alias grouping.
- Periodogram/SDE-ogram view with top candidate periods, aliases, and raw vs smoothed power.
- TLS-style transit model overlay on phase-folded and time-series views.
- User-entered stellar priors and limb-darkening coefficients.
- SDE, FAP, SNR, period uncertainty, reduced chi-squared, and odd/even mismatch statistics.
- Transit masks, signal cleansing, and iterative multi-planet search.
- Optional uncertainty-column support.
- Search progress reporting and quick-look binning/resampling.
- Save/load edited sessions.
- A real test suite for analysis functions.
- Refactor into modules once behavior stabilizes.

## Current Git State Expectations

The main branch should contain this documentation and the current app implementation. The canonical remote is:

```text
https://github.com/jakenaor/Exoplanet-Transit-Finder.git
```

Before future work, run:

```bash
git status --short --branch
```

and confirm you are in:

```text
/Users/jakenaor/Documents/Coding Stuff/Space/Exoplanet-Transit-Finder
```
