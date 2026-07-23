# Current State

Last updated: 2026-07-22

## Canonical Location

Use this repo as the source of truth:

```text
/Users/jakenaor/Documents/Coding Stuff/Space/Exoplanet-Transit-Finder
```

The app is currently nested at:

```text
Exoplanet data parsing tool/
```

The active app files are:

```text
Exoplanet data parsing tool/main.py
Exoplanet data parsing tool/analysis_jobs.py
Exoplanet data parsing tool/analysis.py
Exoplanet data parsing tool/parsers.py
Exoplanet data parsing tool/tls_search.py
Exoplanet data parsing tool/static/index.html
Exoplanet data parsing tool/static/styles.css
Exoplanet data parsing tool/static/app.js
```

A similarly named non-repo folder and an earlier typo-named app folder were used by mistake:

```text
/Users/jakenaor/Documents/Coding Stuff/Space/Exoplaned data parsing tool
Exoplaned data parsing tool/
```

Future sessions should work in `Exoplanet-Transit-Finder` and the tracked `Exoplanet data parsing tool/` folder, not either typo path. See [Repo Map](REPO_MAP.md) for the local canonical file layout.

## Product Goal

Build a local Python web app for exoplanet transit analysis. The user uploads one or more CSV/FITS light curves, the app plots the light curve, detects transit-like dips, boxes transits, estimates orbital period, provides significance estimates, supports manual exploration/editing, and exports the results.

For CSV input, the app expects `Time` and `Flux` columns. For FITS input, it accepts common time and flux columns such as `TIME`, `BJD`, `BTJD`, `JD`, `MJD`, `PDCSAP_FLUX`, `SAP_FLUX`, and `FLUX`.

The `Time` column is treated as continuous Julian days. UI plots show days since the first observation for time-series views, while retaining the original JD reference in the Analysis panel and export data. FITS relative time columns are shifted by available BJD/JD/MJD reference header values when present.

## Current Working Features

- Localhost app served by `python3 main.py` using Python stdlib HTTP serving.
- Running `python3 main.py` automatically opens the local app URL in the default browser unless `TRANSIT_FINDER_NO_BROWSER` is set.
- `requirements.txt` pins `numpy>=1.26,<2`, `scipy>=1.13,<2`, `astropy>=6,<7`, and `transitleastsquares>=1.32,<2` so both Astropy BLS and the physical TLS engine work on the current Python 3.9 setup.
- Frontend uses a full-window app shell with an independently scrolling sidebar, flexible chart canvas, and scrollable transit table.
- Sidebar panels are native accordion sections with smooth folding animations and CSS-drawn right/down arrows for closed/open states.
- Run Status is its own accordion panel and auto-opens/expands to show all per-file progress bars when they are rendered or updated.
- Long analyses run in isolated background processes. Uploads return immediately with a job ID, the frontend polls short-lived status requests, and completed results remain available even if an earlier poll disconnects.
- Run Status reports queued/running state and honest elapsed time instead of a synthetic completion percentage.
- The visible Cancel analysis control terminates the active analysis process and its TLS worker-process group without stopping the web server.
- Sidebar width expands from selected/progress filenames, and progress filenames wrap to two lines before truncating.
- Batch Results uses a custom styled picker with two-line filenames and compact verdict/transit badges instead of the native OS dropdown.
- Batch Results mini-previews include the per-file Planet Check confidence score as an `n/100` badge.
- Split app structure:
  - `main.py` handles HTTP routes, static assets, the compatibility `/analyze` route, and `/analysis-jobs` lifecycle routes.
  - `analysis_jobs.py` queues analyses in isolated processes, retains completed results, and provides process-group cancellation.
  - `parsers.py` handles CSV and FITS ingestion.
  - `analysis.py` handles cleaning, local detection, search selection, diagnostics, and plot payloads.
  - `tls_search.py` wraps the maintained Transit Least Squares engine and converts its models/statistics into compact JSON-safe payloads.
  - `static/index.html`, `static/styles.css`, and `static/app.js` hold the frontend.
- CSV upload with case-insensitive `Time`/`Flux` parsing.
- CSV upload size limit of `80 MB`.
- FITS upload support for `.fits`, `.fit`, and `.fts` files.
- FITS upload size limit of `200 MB`.
- FITS parser support for table HDUs with common time/flux column names.
- FITS `QUALITY == 0` filtering when a recognized quality column is present.
- Batch upload support for up to `100` files.
- Sequential batch processing through cancellable `/analysis-jobs` background jobs.
- Batch Results dropdown for switching between processed filenames.
- Batch dropdown labels include the current planet-candidate verdict for each successful file.
- Failed batch items are kept visible in the dropdown but disabled.
- Large dataset handling with downsampling for plotting.
- Raw clipped, full cleaned, transit zoom, and phase-folded chart modes.
- Periodogram chart mode that plots compact BLS power/SDE over searched periods and marks top candidates.
- Ephemeris audit chart mode:
  - Shows predicted period windows from the recovered ephemeris.
  - Colors detected boxes green when they align with the predicted ephemeris.
  - Colors detected boxes red when they are off-period.
  - Draws residual connectors and a compact ephemeris-fit legend.
- Robust clipping and moving-average smoothing for visualization.
- Per-observing-segment median normalization for gapped/multi-zone light curves.
- Transit detection using scipy peak/prominence logic with fallback threshold detection.
- BLS orbital period estimate using `astropy.timeseries.BoxLeastSquares`.
- Binned-BLS fallback period estimate when the full BLS path is unavailable or fails at runtime.
- Physical Transit Least Squares using `transitleastsquares` 1.32:
  - Physical TLS is the default search mode.
  - Limb-darkened, grazing, and box comparison templates.
  - Ingress/egress-aware fitting over the unbinned phase-folded light curve.
  - Physically constrained period/duration grids.
  - Optional stellar mass/radius and quadratic limb-darkening priors.
  - Configurable period oversampling, duration-grid step, minimum transit count, minimum depth, and CPU workers.
  - Four CPU workers are used by default to parallelize the unchanged TLS search grid without changing the fitted result.
  - TLS SDE, raw SDE, white-noise FAP, combined SNR, period uncertainty, odd/even mismatch, per-transit statistics, and model payloads.
  - TLS-derived transit boxes instead of relying on the local prominence detector for shallow signals.
  - Physical model overlays in time-series and phase-folded views.
  - Time-series model overlays are evaluated at the actual observation timestamps, smoothed with the same transit-safe display window as the cleaned curve, and downsampled with transit extrema preserved.
  - Transit duration is measured from the fitted folded physical model. The reference engine's original gap-fill-adjusted value is retained as `engine_duration` for diagnostics.
- Period displayed in Julian days.
- Period search controls:
  - Minimum period.
  - Maximum period.
  - BLS + regularity and physical TLS search modes.
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
  - Minimum period.
  - Maximum period.
  - Reset detection.
- Transit depth estimates:
  - Raw flux depth.
  - Depth fraction, percent, and ppm.
  - Radius-ratio estimate using `Rp/Rs = sqrt(depth fraction)`.
  - Flux near a positive baseline is treated as fractional flux; residual ppm-style flux is treated as ppm directly.
- False-positive and TLS diagnostics:
  - Warnings panel for low-SNR, few-transit, no-period, provisional-period, weak-significance, odd/even mismatch, inconsistent-depth, large-radius-ratio, and sparse-sampling cases.
  - Depth SNR, period SDE, and reduced chi-squared metrics in the Analysis panel.
  - Warning and diagnostic fields included in summary JSON exports.
- Planet/no-planet assessment:
  - Backend emits a `planet_assessment` object for every analysis.
  - Frontend shows a `Planet Check` panel with a 0-100 candidate score.
  - Verdict states include `strong_candidate`, `possible_candidate`, `inconclusive`, and `no_planet_like_signal`.
  - The no-signal verdict is phrased as no detectable planet-like transit at the current settings, not proof that no planet exists.
  - Manual box edits recompute the visible verdict client-side.
  - Ephemeris agreement is now part of the verdict: detected dips must mostly align with the recovered period.
  - Off-period transit-like dips are penalized heavily to avoid mistaking irregular systematics for a planet.
  - Expected transit coverage now counts only predicted events that fall inside observed data segments, so long gaps do not unfairly penalize real gapped datasets.
  - Candidate scores are capped by verdict tier so a `possible_candidate` no longer displays as `100/100`.
  - High-repeat, high-period-confidence datasets with moderate per-transit SNR can still become `strong_candidate`.
- Export controls:
  - Transit CSV, including edited boxes and original JD columns.
  - Current graph PNG.
  - Summary JSON with metrics, detection options, warnings, `planet_assessment`, and transits.
  - Analysis PDF for the currently selected file, including assessment and candidate score.
  - Batch PDF table for all successfully processed uploaded files, including assessment and candidate score.

## Important Implementation Decisions

- The app has been split out of the old monolithic `main.py` into Python modules plus static frontend assets, while preserving the simple local `python3 main.py` workflow.
- Use `numpy`, `scipy`, and `astropy` for numerical and astronomy-specific operations instead of hand-rolling everything.
- FITS support depends on `astropy.io.fits`; if `astropy` is unavailable, FITS uploads fail with a user-visible error.
- Use the repo-local `.venv` as the VS Code/Pylance interpreter. `.vscode/settings.json` points Pylance at `.venv/bin/python`.
- Treat `Time` as Julian dates and convert to relative days for graph readability.
- Normalize gapped observing segments independently before transit detection. This fixed the HD 209458-style file where obvious dips existed in separate data zones but global noise/baseline handling hid them.
- Use BLS for orbital period, because simple averaging of nearby detected boxes was badly wrong for real gapped datasets.
- Use observed-window ephemeris coverage for Planet Check and audit logic. Predicted transits that fall entirely inside data gaps are not counted against a candidate.
- Treat broad automated period-search results as candidate rankings, not ground truth. The Kepler sample previously showed a strong alias around `294` days while a constrained `380-390` day search returned about `386.16` days.
- Use phase-folding as the primary validation view for repeated transit structure.
- TLS mode uses the maintained reference implementation from Hippke & Heller rather than the earlier lightweight approximation. The app adds segment-aware normalization, observed-window ephemeris checks, compact model payloads, and conservative candidate gating around the reference result.
- TLS white-noise FAP values can be optimistic for correlated/red noise and are never treated as planet confirmation.
- Batch upload is implemented client-side by submitting and polling one background analysis job at a time.
- The synchronous `/analyze` endpoint remains available for compatibility, while the app UI uses `/analysis-jobs` so TLS computation never holds an upload socket open.
- Client socket disconnects during static or JSON response writes are logged once and do not trigger a second write to the already-closed socket.
- Manual box edits are frontend-local. They update the displayed table and metrics but do not round-trip to the backend.
- Detection controls require clicking `Analyze files` again. They are not live-updated while dragging sliders.
- Chi-squared p-value is an approximate model-vs-flat significance metric, not a literal probability that a planet is real.
- The planet assessment is a heuristic vetting layer. It combines transit count, BLS period, period SDE, depth SNR, chi-squared improvement, depth consistency, odd/even mismatch, radius ratio, point counts, and warning severity.
- `no_planet_like_signal` means the current data/settings do not contain a credible detectable transiting-exoplanet signal. It is not a universal statement that the target has no planets.
- Exports are client-side downloads.
- `docs/CURRENT_STATE.md` is now tracked in git. `docs/REPO_MAP.md` is still ignored by `.gitignore` unless it is intentionally force-added.

## Things That Worked

- BLS and the binned-BLS fallback replaced naive average-gap period estimation.
- Period min/max controls made period aliases visible and controllable; constraining the Kepler sample to `380-390` days previously returned about `386.16` days.
- A repo-local `.venv` fixed Pylance missing-import warnings for `numpy`, `scipy`, and `astropy`.
- Phase-folded view made repeated transit structure visually obvious when centered on phase 0.
- Local curve-bounded boxes are much more readable than full-height boxes.
- Manual editing is useful for correcting imperfect automatic boxes.
- Detection strictness and smoothing controls affect candidate counts.
- Per-segment median normalization and a more permissive fallback detector fixed the HD 209458 CSV case with clear transits in two separated data zones.
- FITS parsing works on synthetic table-HDU light curve fixtures.
- Batch uploads work for mixed successful/failed files and preserve filename switching.
- PDF analysis exports work for both the selected file and all successful batch results.
- Splitting the monolithic file made the code easier to navigate without changing the local startup command.
- Synthetic positive/no-signal tests now demonstrate both sides of the new assessment layer:
  - A clean injected-transit dataset returns `strong_candidate`.
  - A flat/noisy dataset returns `no_planet_like_signal`.
- Ephemeris audit view made the irregular false-positive failure mode visible instead of only numeric.
- Observed-window ephemeris coverage fixed a WASP-19-style case where the correct period was penalized as only `6%` covered because expected transits inside long observing gaps were being counted.
- Batch Results score badges make it easier to compare many uploaded files without opening each Planet Check panel.
- Isolated background jobs fixed the long-TLS `BrokenPipeError` failure mode: analysis continues independently of short HTTP requests, results are polled, and cancellation leaves the server responsive.

## Things That Did Not Work Or Needed Correction

- Initial Pylance reported missing `numpy`; this was fixed by creating `.venv`, installing `requirements.txt`, and adding `.vscode/settings.json`.
- An earlier global Python environment had a broken `astropy` import due to a dependency mismatch. The repo-local `.venv` imports `numpy`, `scipy`, and `astropy` successfully.
- Early plots were unreadable because the raw data had large outliers and too many points. Clipping, smoothing, and downsampling were added.
- Early transit detection found only one transit. Detection was broadened and later improved with prominence logic, threshold fallback, and segment-aware normalization.
- Early box drawing covered too much vertical space. It now boxes the local transit curve region.
- Simple average of detected transit centers was not reliable for orbital period because the detector can find many local dips that are not consecutive orbital events. BLS is now preferred.
- The wrong local folder was used for several edits before copying the final app into the correct Git repo. The correct repo is now documented here.
- The docs became stale after FITS support, batch uploads, PDF exports, and the file split. This update corrects that.
- A p-value display experiment added raw/scientific p-value formatting and a `p_value_log10` field, but it was reverted. The current app is back to the earlier Chi-sq p-value percentage display.

## Current Verification Notes

Known sample file previously used during testing:

```text
/Users/jakenaor/Downloads/kepler_Kepler-452b_transit_data_20.csv
```

As of 2026-06-02, that sample file was not present at the old path, so it was not revalidated in that update.

The HD 209458 CSV used for the transit-detection fix was:

```text
/Users/jakenaor/Desktop/hd209458_time_flux.csv
```

That desktop file later disappeared, so do not assume it exists in future sessions.

Recent verification used temporary fixtures in `/private/tmp`, including:

```text
/private/tmp/synthetic_transit_lightcurve.fits
/private/tmp/transit-batch-fixtures/batch_sample_1.csv
/private/tmp/transit-batch-fixtures/batch_sample_2.csv
```

Desktop adversarial/no-signal fixtures created during testing:

```text
/Users/jakenaor/Desktop/no_exoplanet_noise_lightcurve.csv
/Users/jakenaor/Desktop/irregular_false_positive_transits.csv
```

Observed verification results from recent work:

- Synthetic FITS fixture: `2592` points, `9` transits, BLS period about `1.9993686868639833` days.
- Batch CSV fixture 1: `8` transits, period about `1.69795663` days.
- Batch CSV fixture 2: `6` transits, period about `2.29867111` days.
- Earlier HD 209458 CSV run: `15` transits, BLS period about `3.5242522516600965` days, segment count `4`, SNR about `50.67`.
- 2026-07-20 direct synthetic transit test: `strong_candidate`, score `100`, `8` transits, BLS period about `3.502190694763197` days, period SDE about `13.578`.
- 2026-07-20 direct flat/noisy test: `no_planet_like_signal`, score `18`, `0` transits.
- 2026-07-20 HTTP upload positive CSV test: `strong_candidate`, score `100`, `8` transits.
- 2026-07-20 HTTP upload flat/noisy CSV test: `no_planet_like_signal`, score `0`, `0` transits.
- 2026-07-20 irregular false-positive test before ephemeris vetting: incorrectly returned `strong_candidate`, score `100`, `9` transits.
- 2026-07-20 irregular false-positive test after ephemeris vetting: `no_planet_like_signal`, score `24`, `9` detected dips, ephemeris fit `3/9`, warnings `Irregular transit timing` and `Many off-period dips`.
- 2026-07-20 clean synthetic transit after ephemeris vetting: `strong_candidate`, score `100`, ephemeris fit `8/8`.
- 2026-07-22 WASP-19 dataset verification:
  - File: `/Users/jakenaor/Desktop/Extrasolar Research Stuff/Datasets/wasp19_time_flux.csv`
  - Result: `strong_candidate`, score `100`, `55` transits, BLS period about `0.787919` days.
  - Observed expected coverage: `55/57` events, coverage about `0.9649`.
  - This replaced the earlier incorrect weak-coverage behavior that reported about `6%`.
- 2026-07-22 pure-noise guardrail verification:
  - File: `/Users/jakenaor/Desktop/Extrasolar Research Stuff/datasets/no_exoplanet_just_pure_noiselightcurve.csv`
  - Result: `no_planet_like_signal`, score `0`, `0` transits.
- 2026-07-22 p-value display rollback verification:
  - `/analyze` no longer emits `p_value_log10`.
  - Frontend Analysis and PDF table use the older Chi-sq p-value percentage display.
- 2026-07-22 physical TLS integration verification:
  - Reference engine: Transit Least Squares 1.32 (5 Apr 2024).
  - A 1200-point injected 2.4-day limb-darkened transit recovered about `2.4009` days, TLS SDE about `7.36`, FAP about `0.0050`, combined SNR about `37.6`, and a `strong_candidate` verdict.
  - A seeded pure-noise run produced TLS SDE about `3.33` and was capped at `no_planet_like_signal` rather than becoming a candidate.
  - The live `/analyze` multipart route returned a TLS period about `2.4009` days, SDE about `9.40`, FAP about `8.0e-5`, five TLS-derived boxes, and a physical model payload.
  - The reproducible 18-case shallow-transit benchmark in `tests/benchmark_searches.py` recovered the injected period in `17/18` TLS runs and `18/18` BLS runs at the chosen 1% period tolerance. TLS produced credible candidate verdicts in `17/18`; the existing BLS/local-box path produced `0/18` at these shallow depths. This small benchmark does not establish universal superiority.
- 2026-07-22 background-job/BrokenPipe fix verification:
  - The `6878`-row HD 209458 file at `/Users/jakenaor/Desktop/Extrasolar Research Stuff/datasets/hd209458_time_flux.csv` spans about `733.98` days; blank period bounds create `89,518` TLS period trials at oversampling `3`.
  - `POST /analysis-jobs` accepted the upload with HTTP `202` in under a second, and status remained readable through short `GET /analysis-jobs/{id}` polls.
  - A bounded `3-4` day, oversampling `1` job completed in about `20.76` seconds and recovered `3.525006` days, TLS SDE about `26.84`, FAP `8.0032e-5`, and combined SNR about `60.67`.
  - A separate broad TLS job was cancelled in about `1.09` seconds; its worker stopped and the app still returned HTTP `200` for the index page.
  - The regression suite now covers spawned-job completion, running-job cancellation, disconnect-safe JSON writes, job-route parsing, TLS recovery/noise gating, and BLS fallback.
- 2026-07-22 TLS time-overlay/duration fix verification:
  - The pre-fix WASP-43 payload retained a time-series model-bottom point for only `4/49` observed transits after uniform compaction.
  - The reference result's global gap-fill correction reported about `0.002404` days (3.46 minutes), while its fitted folded model spans about `0.023388` days (33.68 minutes).
  - The corrected constrained TLS run recovered the same `0.8134680414`-day period, used the folded-model duration, and produced `49/49` observed transits with aligned model samples.
  - Cleaned-view smoothing was capped from `95` samples (about 190 minutes) to `5` samples for this transit, preventing the display line from averaging away the event.
  - The model and cleaned line now use the same `8060`-point observation-aligned plot grid; the median absolute difference between their per-transit bottoms was about `0.0030` relative flux.
  - Model compaction now retains bucket minima/maxima, and regression tests cover narrow-transit preservation, folded-model duration measurement, observation-aligned model coverage, transit-safe smoothing, and segment-boundary smoothing.

Commands used for basic checks:

```bash
PYTHONPYCACHEPREFIX=/private/tmp/transit-pycache .venv/bin/python -m py_compile \
  "Exoplanet data parsing tool/main.py" \
  "Exoplanet data parsing tool/analysis.py" \
  "Exoplanet data parsing tool/parsers.py"

.venv/bin/python "Exoplanet data parsing tool/main.py"
```

Browser JavaScript has also been syntax-checked with macOS `osascript -l JavaScript` when no in-app browser was available.

As of 2026-07-20, the in-app browser surface was unavailable in the coding session, so visible UI verification was replaced with static asset `GET` checks and endpoint upload checks.

## Known Limitations

- Manual box edits are not persisted after re-analysis or page reload.
- The p-value recomputed after manual edits uses frontend plotted/smoothed data, not the full backend dataset. This is useful for feedback but less rigorous than a backend recompute.
- Exports are client-side downloads.
- False-positive warnings are heuristic and advisory; they do not prove or disprove that a candidate is planetary.
- The Planet Check verdict is heuristic and should be treated as a candidate/no-detection triage layer, not confirmation or publication-grade validation.
- Top period candidates are exposed, but harmonics/aliases are not yet analyzed deeply.
- Broad automated period search can still prefer aliases. Use period min/max controls when a target period range is known.
- Batch processing is sequential and client-driven. It is cancellable and shows backend state/elapsed time, but does not yet expose exact period-grid completion percentages.
- Cleaned-view TLS overlays are display-smoothed for direct comparison with the cleaned line; their boxes include the same filter radius as a display-only margin, while the reported duration, raw view, and phase-folded overlay remain physical and unsmoothed.
- TLS duration recovery corrects the reference engine's sampling-gap compression and can conservatively widen significant candidates to phase-folded observed ingress/egress. This changes neither the recovered period nor epoch and only expands durations when the folded signal clears robust noise checks.
- FITS support handles table HDUs with recognizable time/flux columns; it does not analyze FITS image cubes or arbitrary instrument-specific products yet.
- The data cleaning report/panel is still pending.
- The automated regression suite covers job completion/cancellation, disconnect handling, TLS option parsing, limb-darkening validation, physical TLS recovery, pure-noise rejection, JSON serialization, and BLS runtime fallback. Broader real-dataset coverage is still needed.

## TLS Parity Roadmap

The project now includes the reference physical Transit Least Squares engine. Primary references are the [TLS paper](https://doi.org/10.1051/0004-6361/201834672), [official Python interface](https://transitleastsquares.readthedocs.io/en/latest/Python%20interface.html), and [reference source](https://github.com/hippke/tls). Remaining extensions are:

- Transit-shaped model fitting:
  - Full limb-darkened TLS, grazing, and box templates are implemented.
  - Model overlays in time and phase-folded views are implemented.
  - A separately parameterized trapezoid template beyond the reference grazing template remains optional future work.
- Stellar parameter priors:
  - Users can enter stellar radius, stellar mass, and quadratic limb-darkening coefficients.
  - Catalog import and direct stellar-density priors remain pending.
  - Use stellar priors to constrain physically plausible period and duration grids.
  - Surface missing/invalid stellar-prior warnings clearly.
- Search controls:
  - Period minimum/maximum controls are implemented.
  - Duration minimum/maximum controls are implemented as detection controls, but not yet tied to physical stellar priors.
  - Period search bounds are exported in JSON; full period/duration grid visualization is still pending.
  - Add quick-look binning/resampling controls for large or short-cadence datasets.
- Detection statistics:
  - TLS SDE, raw SDE, FAP, period uncertainty, combined SNR, odd/even mismatch, transit counts, and per-transit values are now emitted and exported.
  - Surface more of the per-transit TLS detail directly in the UI rather than only in JSON.
  - Add red-noise-aware significance estimates beyond the reference white-noise FAP.
- Transit masks and iterative searches:
  - Generate an in-transit mask for the best candidate.
  - Let users hide, highlight, or export in-transit/out-of-transit points.
  - Add "cleanse detected signal and search again" for multi-planet systems.
- Data cleaning and uncertainties:
  - Accept an optional flux uncertainty column.
  - Clean NaN, None, infinite, masked, and invalid flux/error values with a user-visible report.
  - Preserve a reversible cleaning log for exports.
- Power-spectrum inspection:
  - Periodogram/SDE-ogram view and top candidate periods are implemented for BLS and TLS.
  - Expose harmonic/alias groups and a UI toggle between TLS median-smoothed and raw SDE spectra.
  - Flag edge-effect or phase-wrapping artifacts where relevant.
- Performance/user feedback:
  - Per-file queued/running state, elapsed time, and explicit cancellation are implemented with isolated worker processes.
  - Exact backend search-stage/period-grid progress streaming is still pending.
  - Add a fast preview mode before full-resolution search.
  - Cancellable worker-process execution for long TLS searches is implemented.

## Planned Feature Order

Current feature sequence status:

1. Phase-folded light curve: done.
2. Manual transit box editing: done.
3. Detection sensitivity controls: done.
4. Export results: done.
5. Transit depth in percent/ppm and radius-ratio estimate: done.
6. False-positive warnings: done.
7. Planet/no-planet assessment: done.
8. Ephemeris audit view: done.
9. Data cleaning panel: next.
10. Sensitivity/no-planet upper-limit message: pending.
11. Physical TLS search mode: done.
12. Reset/home view button: pending.

Additional useful future features after step 12:

- Transit prediction from period and epoch.
- Better candidate-period ranking with explicit harmonic/alias grouping.
- Periodogram alias grouping and raw vs smoothed power comparison.
- Catalog-backed stellar priors and additional physical-template controls.
- User-entered stellar priors and limb-darkening coefficients.
- SDE, FAP, SNR, period uncertainty, reduced chi-squared, and odd/even mismatch statistics.
- Transit masks, signal cleansing, and iterative multi-planet search.
- Optional uncertainty-column support.
- Search progress reporting and quick-look binning/resampling.
- Save/load edited sessions.
- Expand the regression suite to real mission light curves and additional failure modes.

## Current Git State Expectations

The main branch should contain the current app implementation and `docs/CURRENT_STATE.md`. The canonical remote is:

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
