import math as Math

import numpy as Np

from tls_search import RunTlsSearch, ExposureArraySeconds, ExposureIntegratedTemplate

try:
    from scipy.signal import find_peaks as FindPeaks, peak_widths as PeakWidths
except Exception:
    FindPeaks = None
    PeakWidths = None

try:
    from scipy.stats import chi2 as Chi2
except Exception:
    Chi2 = None

try:
    from astropy.timeseries import BoxLeastSquares
except Exception:
    BoxLeastSquares = None


#MARK: core stuffs
MAX_PLOT_POINTS = 12000
MAX_PERIODOGRAM_POINTS = 1600
DEFAULT_DETECTION_OPTIONS = {
    "strictness": 1.0,
    "smoothing": 1.0,
    "search_mode": "tls",
    "min_depth": None,
    "min_duration": None,
    "max_duration": None,
    "min_period": None,
    "max_period": None,
    "tls_template": "default",
    "stellar_radius": None,
    "stellar_mass": None,
    "limb_darkening_u1": None,
    "limb_darkening_u2": None,
    "tls_oversampling": 3,
    "tls_min_transits": 3,
    "tls_threads": 4,
    "tls_min_depth_ppm": 10.0,
    "tls_duration_grid_step": 1.1,
    "tls_max_signals": 1,
    "exposure_seconds": None,
}


#MARK: curve funcs
def RunCurve(Time, Flux, Options=None, ProgressCallback=None, **LegacyOptions):
    # keep the callback spelling older scripts pass in.
    ProgressCallback = LegacyOptions.pop("progress_callback", ProgressCallback)
    if LegacyOptions:
        raise TypeError(f"Unknown analysis options: {', '.join(LegacyOptions)}")
    def ReportProgress(Stage, StageLabel, Details=None):
        if callable(ProgressCallback):
            if Details is None:
                ProgressCallback(Stage, StageLabel)
            else:
                ProgressCallback(Stage, StageLabel, Details)

    #MARK: curve funcs
    Time, Flux, Options, Exposures, ExposureMetadata = _PrepCurve(Time, Flux, Options)
    ReportProgress("preparing", "Preparing light curve")
    NormalizationPlan = FluxNormalizationPlan(Flux)
    AnalysisFlux, Segments = NormalizeFluxBySegments(Time, Flux)
    NormalizedUncertainty, UncertaintyComplete = _ScaleFluxErrors(
        Flux, Segments, NormalizationPlan, Options.get("_flux_uncertainty")
    )
    if UncertaintyComplete:
        Options = {**Options, "_normalized_flux_uncertainty": NormalizedUncertainty}
    #MARK: period funcs
    SearchMode = Options.get("search_mode", DEFAULT_DETECTION_OPTIONS["search_mode"])
    if SearchMode == "tls":
        ReportProgress("tls_search", "Searching periods with TLS")
    else:
        ReportProgress("bls_search", "Searching periods with BLS")
    Detection = DetectTransits(Time, AnalysisFlux, Options,
                                ProgressCallback=lambda Details: ReportProgress(
                                    "tls_finalizing" if Details.get("search_complete") else "tls_search",
                                    "Finalizing TLS model" if Details.get("search_complete") else "Searching periods with TLS", Details))
    #MARK: plot stuffs
    ReportProgress("building", "Building transit model and plots")
    TimeReference = float(Time[0])
    DisplayTime = Time - TimeReference
    RawLow, RawHigh = RobustFluxLimits(AnalysisFlux, Sigma=4.0)
    RawClipped = Np.clip(AnalysisFlux, RawLow, RawHigh)

    TransitModel = Detection.get("transit_model")
    BaseSmoothWidth = int(max(25, min(251, len(AnalysisFlux) // 300)))
    SmoothWidth = OddWindowWidth(BaseSmoothWidth, float(Options["smoothing"]), 5, 601)
    Cadence = float(Np.median(Np.diff(Time))) if len(Time) > 1 else 1.0
    PeriodSde = FiniteNumber(Detection.get("period_sde"))
    if TransitModel is not None and PeriodSde is not None and PeriodSde >= 5.0:
        SmoothWidth = TransitPreservingSmoothingWidth(
            SmoothWidth,
            Cadence,
            Detection.get("period_duration"),
        )
    SmoothFlux = MovingAverageBySegments(RawClipped, SmoothWidth, Segments)

    ObservedModelFlux = ModelFluxAtObservations(
        Time,
        Detection.get("period"),
        Detection.get("period_epoch"),
        TransitModel,
        Exposures,
    )
    DisplayModelFlux = None
    if ObservedModelFlux is not None:
        DisplayModelFlux = MovingAverageBySegments(ObservedModelFlux, SmoothWidth, Segments)

    PlotKeep = DownsampleIndicesForSeries(
        [AnalysisFlux, SmoothFlux, DisplayModelFlux] if DisplayModelFlux is not None else [AnalysisFlux, SmoothFlux],
        MAX_PLOT_POINTS,
    )
    # keep each segment's ends when shrinking the plot.
    PlotKeep = Np.unique(Np.r_[PlotKeep, [Index for Start, End in Segments for Index in (Start, End - 1)]]).astype(int)
    PlotBreaks = [int(Np.searchsorted(PlotKeep, Start)) for Start, _ in Segments[1:]]
    PlotTime = DisplayTime[PlotKeep]
    PlotRaw = AnalysisFlux[PlotKeep]
    PlotSmooth = SmoothFlux[PlotKeep]
    RawFluxMin, RawFluxMax = DomainFor(RawClipped, 0.5, 99.5)
    CleanDomainValues = (
        Np.r_[SmoothFlux, DisplayModelFlux]
        if DisplayModelFlux is not None
        else SmoothFlux
    )
    CleanFluxMin, CleanFluxMax = DomainFor(CleanDomainValues, 0.2, 99.8)
    PhaseFolded = MakePhasePlot(
        Time,
        RawClipped,
        SmoothFlux,
        Detection["period"],
        Detection["period_epoch"],
        Detection["period_duration"],
    )
    TransitStack = BuildTransitStack(
        Time,
        AnalysisFlux,
        [Event for Event in Detection["transits"] if Event.get("points", 1) > 0],
        Detection["period"],
        Detection["period_duration"],
    )

    if TransitModel is not None and DisplayModelFlux is not None:
        TransitModel = {
            **TransitModel,
            "time": PlotTime.tolist(),
            "flux": DisplayModelFlux[PlotKeep].tolist(),
            "time_series_representation": "observation-aligned and plot-smoothed",
            "plot_smooth_points": SmoothWidth,
        }
        Detection = {**Detection, "transit_model": TransitModel}

    #MARK: transit checks
    DisplayTransits = []
    for Transit in Detection["transits"]:
        DisplayTransit = dict(Transit)
        AddDepthMetrics(DisplayTransit, Transit.get("local_baseline", Detection["median_flux"]))
        for Key in ("predicted_center", "measured_center"):
            if Transit.get(Key) is not None:
                DisplayTransit[Key] = float(Transit[Key] - TimeReference)
        DisplayTransit["start"] = float(Transit["start"] - TimeReference)
        DisplayTransit["center"] = float(Transit["center"] - TimeReference)
        DisplayTransit["end"] = float(Transit["end"] - TimeReference)
        DisplayTransit["display_extents"] = _TransitBoxLimits(
            Time, Transit, AnalysisFlux, SmoothFlux, DisplayModelFlux
        )
        if TransitModel is not None and DisplayModelFlux is not None:
            DisplayStart, DisplayEnd = SmoothedTransitDisplayBounds(
                DisplayTransit["start"],
                DisplayTransit["end"],
                Cadence,
                SmoothWidth,
                float(DisplayTime[0]),
                float(DisplayTime[-1]),
            )
            DisplayTransit["display_start"] = DisplayStart
            DisplayTransit["display_end"] = DisplayEnd
        DisplayTransits.append(DisplayTransit)
    ObservedRanges = [
        (float(Time[Start] - TimeReference), float(Time[End - 1] - TimeReference))
        for Start, End in Segments
    ]
    #MARK: transit checks
    ReportProgress("vetting", "Calculating diagnostics")
    Diagnostics, Warnings = BuildCandidateDiagnostics(DisplayTransits, Detection, TimeReference, ObservedRanges)
    if SearchMode == "tls" and ExposureMetadata["unknown_rows"]:
        Warnings.append({"severity": "info", "title": "Unknown exposure duration",
                         "detail": "Some or all sample exposure durations are unknown. Template refinement uses an instantaneous approximation for those rows; cadence is not treated as exposure, and duration uncertainty excludes this systematic. Supply an exposure in seconds when known."})
    if NormalizedUncertainty is not None and not UncertaintyComplete:
        Warnings.append({"severity": "info", "title": "Partial measurement uncertainties",
                         "detail": "Some flux errors are missing or invalid. They remain null in plots/exports; TLS uses its unweighted fallback for this file and local checks use empirical noise."})
    PlanetAssessment = BuildPlanetAssessment(DisplayTransits, Detection, Diagnostics, Warnings)
    # these markers are for inspection. they stay out of the score above.
    ExploratoryDips, ExploratoryMetadata = ([], None)
    if not Options.get("_skip_local_inspection"):
        ExploratoryDips, ExploratoryMetadata = ExploratoryLocalDips(Time, AnalysisFlux, Options, TimeReference)
    FitAccepted = PlanetAssessment["status"] in ("strong_candidate", "possible_candidate")
    FitQuality = {"state": "accepted" if FitAccepted else "tentative",
                   "label": "Candidate model" if FitAccepted else "Tentative fit - below candidate threshold",
                   "reason_codes": [Warning["title"].lower().replace(" ", "_") for Warning in Warnings if Warning.get("severity") in ("caution", "danger")]}
    SearchFlux = None
    if SearchMode == "tls":
        SearchFlux, _ = NormalizedFluxForTls(Time, AnalysisFlux)
    Comparison = None
    if SearchFlux is not None and ObservedModelFlux is not None:
        Comparison = _MakePlotThing(
            PlotTime, SearchFlux, ObservedModelFlux, PlotKeep, PlotBreaks,
            "search-detrended observations and physical template on identical timestamps",
        )

    ZoomDomain = None
    if DisplayTransits:
        First = DisplayTransits[0]
        Last = DisplayTransits[-1]
        MedianDuration = float(Np.median([Item["duration"] for Item in DisplayTransits]))
        if len(DisplayTransits) == 1:
            Pad = max(First["duration"] * 2.8, (Time[-1] - Time[0]) * 0.015, 1.0)
        else:
            Pad = max(MedianDuration * 3.0, (Time[-1] - Time[0]) * 0.02, 1.0)
        ZoomTimeMin = float(max(0.0, First["start"] - Pad))
        ZoomTimeMax = float(min(DisplayTime[-1], Last["end"] + Pad))
        ZoomMask = (DisplayTime >= ZoomTimeMin) & (DisplayTime <= ZoomTimeMax)
        ZoomValues = SmoothFlux[ZoomMask]
        if DisplayModelFlux is not None:
            ZoomValues = Np.r_[ZoomValues, DisplayModelFlux[ZoomMask]]
        ZoomFluxMin, ZoomFluxMax = DomainFor(ZoomValues, 0.0, 100.0)
        ZoomDomain = {
            "time_min": ZoomTimeMin,
            "time_max": ZoomTimeMax,
            "flux_min": ZoomFluxMin,
            "flux_max": ZoomFluxMax,
        }

    #MARK: run details
    ReportProgress("finalizing", "Finalizing results")
    PublicOptions = {Key: Value for Key, Value in Options.items() if not Key.startswith("_")}
    Result = {
        "total_points": int(len(Time)),
        "time_reference": TimeReference,
        "time_unit": "Days since first observation",
        "flux_unit": "relative flux",
        "normalization": {
            "method": NormalizationPlan["method"],
            "input_representation": NormalizationPlan["input_representation"],
            "residual_scale": NormalizationPlan["residual_scale"],
            "segment_count": len(Segments),
            "segment_time_ranges": [
                {
                    "start_day": float(Time[Start] - TimeReference),
                    "end_day": float(Time[End - 1] - TimeReference),
                    "median_flux": float(Np.median(Flux[Start:End])),
                }
                for Start, End in Segments
            ],
        },
        "plot": {
            "time": PlotTime.tolist(),
            "raw_flux": PlotRaw.tolist(),
            "smooth_flux": PlotSmooth.tolist(),
            "break_indices": PlotBreaks.copy(),
            "raw_representation": "unclipped segment-normalized flux at retained plot samples",
            "clean_representation": "display-clipped, segment-smoothed observations",
        },
        "domain": {
            "time_min": 0.0,
            "time_max": float(DisplayTime[-1]),
        },
        "raw_domain": {"flux_min": RawFluxMin, "flux_max": RawFluxMax},
        "clean_domain": {"flux_min": CleanFluxMin, "flux_max": CleanFluxMax},
        "zoom_domain": ZoomDomain,
        "phase_folded": PhaseFolded,
        "transit_stack": TransitStack,
        "plot_smooth_points": SmoothWidth,
        "diagnostics": Diagnostics,
        "warnings": Warnings,
        "planet_assessment": PlanetAssessment,
        "fit_quality": FitQuality,
        "model_comparison": Comparison,
        "predicted_windows": DisplayTransits,
        "observed_events": [Event for Event in DisplayTransits if Event.get("state", "supported_dip") == "supported_dip"],
        "exploratory_dips": ExploratoryDips,
        "exploratory_dips_metadata": ExploratoryMetadata,
        "cleaning_report": Options.get("_cleaning_report"),
        "input_metadata": Options.get("_input_metadata", {"time_format": "unspecified", "time_standard": "unspecified"}),
        "exposure_metadata": ExposureMetadata,
        "preprocessing": {"normalized": "per-observing-segment median", "search": "segment-local trend removal; downward samples retained", "display": "segment-local moving average", "stack": "per-event linear baseline, no automatic recentering"},
        "significance_metadata": {"p_value": "Approximate fixed-model-versus-flat chi-squared comparison after selecting the period; not search-wide false alarm or planet probability.",
                                  "tls_fap": "Reference TLS white-noise lookup; correlated noise and selection effects can make it optimistic.",
                                  "candidate_score": "Heuristic review score, not a calibrated probability."},
        "effective_settings": _PackSettingsThing(PublicOptions, Detection, ExposureMetadata, SearchMode),
        "detection_snr": Diagnostics["detection_snr"],
        "odd_even_depth_mismatch": Diagnostics["odd_even_depth_mismatch"],
        "depth_scatter_ratio": Diagnostics["depth_scatter_ratio"],
        **{**Detection, "transits": [Event for Event in DisplayTransits if Event.get("points", 1) > 0], "detection_options": PublicOptions},
    }
    if NormalizedUncertainty is not None:
        Result["plot"]["flux_uncertainty"] = [float(Value) if Np.isfinite(Value) and Value > 0 else None for Value in NormalizedUncertainty[PlotKeep]]
        Result["uncertainty_usage"] = ("Normalized input uncertainties supplied to TLS; local event estimates additionally use empirical correlated-noise errors." if UncertaintyComplete
                                       else "Incomplete errors retained as null; TLS uses unweighted fallback and local checks use empirical correlated-noise errors.")
    if ExposureMetadata["known_rows"]:
        Result["plot"]["exposure_seconds"] = [float(Value) if Np.isfinite(Value) else None for Value in Exposures[PlotKeep]]
    #MARK: extra signals
    MaxSignals = int(Options.get("tls_max_signals", Options.get("max_signals", 1)))
    if SearchMode == "tls" and MaxSignals > 1:
        Signals = [{"signal_id": "signal-1", "label": "Signal 1", **Result}]
        Retained = Np.ones(len(Time), dtype=bool)
        StopReason = "requested_signal_limit"
        for SignalIndex in range(1, min(MaxSignals, 5)):
            Prev = Signals[-1]
            # don't mask a bad fit and then search whatever it leaves behind.
            if Prev["planet_assessment"]["status"] != "strong_candidate":
                StopReason = "Previous signal lacks strong support; no tentative model was masked."
                break
            Supported = Prev.get("observed_events", [])
            if len(Supported) < 3:
                StopReason = "Fewer than three locally supported events; residual search stopped."
                break
            for Event in Supported:
                Center = Event["center"] + Prev["time_reference"]
                Retained &= Np.abs(Time - Center) > Event["duration"] * 0.65
            if Np.count_nonzero(Retained) < 50:
                StopReason = "Too few unmasked observations remain."
                break
            ReportProgress("tls_search", f"Searching residual observations for signal {SignalIndex + 1}")
            NextOptions = {**Options, "tls_max_signals": 1, "max_signals": 1, "_skip_local_inspection": True}
            if Options.get("_flux_uncertainty") is not None:
                NextOptions["_flux_uncertainty"] = Np.asarray(Options["_flux_uncertainty"])[Retained]
                NextOptions.pop("_normalized_flux_uncertainty", None)
            NextOptions["_exposure_seconds"] = Exposures[Retained]
            Candidate = RunCurve(Time[Retained], Flux[Retained], NextOptions, ProgressCallback)
            # do not present another optimizer noise pattern as a recovered planet.
            if Candidate["planet_assessment"]["status"] not in ("strong_candidate", "possible_candidate"):
                Result["residual_search_attempt"] = {"period": Candidate.get("period"), "sde": Candidate.get("period_sde"), "fit_quality": Candidate.get("fit_quality")}
                StopReason = "No additional credible periodic signal in the residual observations."
                break
            Candidate.update(signal_id=f"signal-{SignalIndex + 1}", label=f"Signal {SignalIndex + 1}",
                             search_context={"method": "iterative conservative transit masking", "masked_samples": int(Np.count_nonzero(~Retained)), "joint_refit": False})
            Signals.append(Candidate)
        Result["signals"] = Signals
        Result["multi_signal_search"] = {"requested": MaxSignals, "recovered": sum(Signal["planet_assessment"]["status"] in ("strong_candidate", "possible_candidate") for Signal in Signals),
                                         "attempted_signals": len(Signals), "stop_reason": StopReason,
                                         "method": "conservative supported-event masking; conditional residual searches", "joint_refit": False,
                                         "limitation": "Overlapping events and period aliases still require joint follow-up vetting."}
        #MARK: extra signals
        if len(Signals) >= 2 and SearchFlux is not None:
            ReportProgress("building", "Refining overlapping transit amplitudes together")
            Joint = JointTemplateAmplitudes(Time, SearchFlux, Signals,
                                               NormalizedUncertainty if UncertaintyComplete else None, Exposures)
            if Joint is not None:
                for Signal, Depth, DepthError in zip(Signals, Joint["depths"], Joint["depth_uncertainties"]):
                    UpdateSignalJointDepth(Signal, Depth, DepthError)
                    Signal["search_context"] = {**Signal.get("search_context", {}), "joint_refit": True,
                                                 "joint_scope": "amplitudes and shared baseline; orbital parameters held fixed"}
                for Field in ("transit_model", "tls", "model_comparison", "joint_depth_refinement"):
                    Result[Field] = Signals[0][Field]
                Result["joint_model_comparison"] = _MakePlotThing(
                    PlotTime, SearchFlux, Joint["model_flux"], PlotKeep, PlotBreaks,
                    "original search-detrended observations with simultaneous fixed-template signal amplitudes",
                )
                Result["joint_model_comparison"]["components"] = [
                    {"signal_id": Signal["signal_id"], "label": Signal["label"], "flux": Component[PlotKeep].tolist()}
                    for Signal, Component in zip(Signals, Joint["components"])
                ]
                Result["multi_signal_search"].update(joint_refit=True, joint_fit=Joint["metadata"],
                                                      limitation="Joint amplitudes and baseline fitted; orbital parameters and transit shapes remain conditional and require follow-up vetting.")
    TagExploratoryAssignments(Result, Result.get("signals") or [Result])
    return Result




#MARK: clamp
def Clamp(Value, Low, High):
    return max(Low, min(High, Value))


#MARK: form bits
def FieldValue(Form, Name):
    if Name not in Form:
        return None
    Item = Form[Name]
    if isinstance(Item, list):
        Item = Item[0]
    return getattr(Item, "value", None)


#MARK: form bits
def ParseOptionalFloat(Form, Name, Low=None, High=None):
    RawValue = FieldValue(Form, Name)
    if RawValue is None or str(RawValue).strip() == "":
        return None
    try:
        Value = float(RawValue)
    except (TypeError, ValueError):
        raise ValueError(f"{Name} must be a number.")
    if not Math.isfinite(Value):
        raise ValueError(f"{Name} must be finite.")
    if Low is not None and Value < Low:
        raise ValueError(f"{Name} must be at least {Low}.")
    if High is not None and Value > High:
        raise ValueError(f"{Name} must be at most {High}.")
    return Value


#MARK: form bits
def ParseOptionalInt(Form, Name, Low=None, High=None):
    Value = ParseOptionalFloat(Form, Name, Low, High)
    if Value is None:
        return None
    if not float(Value).is_integer():
        raise ValueError(f"{Name} must be a whole number.")
    return int(Value)


#MARK: form bits
def ParseChoice(Form, Name, Choices, Default):
    RawValue = FieldValue(Form, Name)
    if RawValue is None or str(RawValue).strip() == "":
        return Default
    Value = str(RawValue).strip().lower().replace("_", "-")
    if Value not in Choices:
        Allowed = ", ".join(sorted(Choices))
        raise ValueError(f"{Name} must be one of: {Allowed}.")
    return Choices[Value]


#MARK: parse detection options
def ParseDetectionOptions(Form):
    Options = dict(DEFAULT_DETECTION_OPTIONS)
    Strictness = ParseOptionalFloat(Form, "strictness", 0.2, 5.0)
    Smoothing = ParseOptionalFloat(Form, "smoothing", 0.25, 4.0)
    if Strictness is not None:
        Options["strictness"] = Clamp(Strictness, 0.2, 5.0)
    if Smoothing is not None:
        Options["smoothing"] = Clamp(Smoothing, 0.25, 4.0)
    Options["search_mode"] = ParseChoice(
        Form,
        "searchMode",
        {
            "bls": "bls",
            "bls-regularity": "bls",
            "bls+regularity": "bls",
            "tls": "tls",
            "tls-style": "tls",
        },
        DEFAULT_DETECTION_OPTIONS["search_mode"],
    )

    Options["min_depth"] = ParseOptionalFloat(Form, "minDepth", 0.0, None)
    Options["min_duration"] = ParseOptionalFloat(Form, "minDuration", 0.0, None)
    Options["max_duration"] = ParseOptionalFloat(Form, "maxDuration", 0.0, None)
    Options["min_period"] = ParseOptionalFloat(Form, "minPeriod", 0.0, None)
    Options["max_period"] = ParseOptionalFloat(Form, "maxPeriod", 0.0, None)
    Options["tls_template"] = ParseChoice(
        Form,
        "tlsTemplate",
        {"default": "default", "grazing": "grazing", "box": "box"},
        "default",
    )
    Options["stellar_radius"] = ParseOptionalFloat(Form, "stellarRadius", 0.1, 100.0)
    Options["stellar_mass"] = ParseOptionalFloat(Form, "stellarMass", 0.01, 100.0)
    Options["limb_darkening_u1"] = ParseOptionalFloat(Form, "limbDarkeningU1", -1.0, 2.0)
    Options["limb_darkening_u2"] = ParseOptionalFloat(Form, "limbDarkeningU2", -1.0, 2.0)
    Options["tls_oversampling"] = ParseOptionalInt(Form, "tlsOversampling", 1, 9) or 3
    Options["tls_min_transits"] = ParseOptionalInt(Form, "tlsMinTransits", 2, 10) or 3
    Options["tls_max_signals"] = ParseOptionalInt(Form, "tlsMaxSignals", 1, 5) or 1
    Options["tls_threads"] = (
        ParseOptionalInt(Form, "tlsThreads", 1, 8)
        or DEFAULT_DETECTION_OPTIONS["tls_threads"]
    )
    Options["tls_min_depth_ppm"] = ParseOptionalFloat(Form, "tlsMinDepthPpm", 0.1, 500000.0) or 10.0
    Options["tls_duration_grid_step"] = ParseOptionalFloat(Form, "tlsDurationGridStep", 1.01, 2.0) or 1.1
    Options["exposure_seconds"] = ParseOptionalFloat(Form, "exposureSeconds", 0.0, 86400.0)
    LimbU1 = Options["limb_darkening_u1"]
    LimbU2 = Options["limb_darkening_u2"]
    if (LimbU1 is None) != (LimbU2 is None):
        raise ValueError("Both limbDarkeningU1 and limbDarkeningU2 are required when either is set.")
    if LimbU1 is not None and (LimbU1 + LimbU2 < 0 or LimbU1 + LimbU2 > 1.5):
        raise ValueError("Quadratic limb-darkening coefficients must have a sum between 0 and 1.5.")
    if (
        Options["min_duration"] is not None
        and Options["max_duration"] is not None
        and Options["max_duration"] <= Options["min_duration"]
    ):
        raise ValueError("maxDuration must be greater than minDuration.")
    if (
        Options["min_period"] is not None
        and Options["max_period"] is not None
        and Options["max_period"] <= Options["min_period"]
    ):
        raise ValueError("maxPeriod must be greater than minPeriod.")
    return Options


#MARK: clean rows
def OddWindowWidth(BaseWidth, Scale, Minimum, Maximum):
    Width = int(round(BaseWidth * Scale))
    Width = int(Clamp(Width, Minimum, Maximum))
    if Width % 2 == 0:
        Width += 1
    return int(min(Width, Maximum if Maximum % 2 == 1 else Maximum - 1))


#MARK: smooth flux
def TransitPreservingSmoothingWidth(RequestedWidth, Cadence, Duration):
    if (
        Duration is None
        or not Math.isfinite(float(Duration))
        or float(Duration) <= 0
        or not Math.isfinite(float(Cadence))
        or float(Cadence) <= 0
    ):
        return int(RequestedWidth)

    TransitSamples = float(Duration) / float(Cadence)
    MaxWidth = max(1, int(Math.floor(TransitSamples / 3.0)))
    if MaxWidth % 2 == 0:
        MaxWidth = max(1, MaxWidth - 1)
    return int(min(int(RequestedWidth), MaxWidth))


#MARK: smooth flux
def SmoothedTransitDisplayBounds(Start, End, Cadence, SmoothWidth, DomainMin, DomainMax):
    Start = float(Start)
    End = float(End)
    Cadence = float(Cadence)
    SmoothWidth = int(SmoothWidth)
    if not Math.isfinite(Cadence) or Cadence <= 0 or SmoothWidth <= 1:
        return Start, End

    SmoothingRadius = (SmoothWidth // 2) * Cadence
    return (
        float(max(DomainMin, Start - SmoothingRadius)),
        float(min(DomainMax, End + SmoothingRadius)),
    )


#MARK: moving average
def MovingAverage(Values, Width):
    if Width <= 1:
        return Values.copy()
    Kernel = Np.ones(Width, dtype=float) / Width
    Padded = Np.pad(Values, (Width // 2, Width - 1 - Width // 2), mode="edge")
    return Np.convolve(Padded, Kernel, mode="valid")


#MARK: curve funcs
def MovingAverageBySegments(Values, Width, Segments):
    Values = Np.asarray(Values, dtype=float)
    if Width <= 1 or not Segments:
        return Values.copy()

    Smoothed = Values.copy()
    for Start, End in Segments:
        Length = int(End - Start)
        if Length <= 1:
            continue
        SegmentWidth = min(int(Width), Length)
        if SegmentWidth % 2 == 0:
            SegmentWidth -= 1
        if SegmentWidth <= 1:
            continue
        Smoothed[Start:End] = MovingAverage(Values[Start:End], SegmentWidth)
    return Smoothed


#MARK: observing segments
def ObservingSegments(Time):
    if len(Time) == 0:
        return []
    if len(Time) == 1:
        return [(0, 1)]

    Deltas = Np.diff(Time)
    PositiveDeltas = Deltas[Np.isfinite(Deltas) & (Deltas > 0)]
    if PositiveDeltas.size == 0:
        return [(0, len(Time))]

    Cadence = float(Np.median(PositiveDeltas))
    FullSpan = float(Time[-1] - Time[0])
    GapThreshold = max(Cadence * 25.0, 0.25)
    if FullSpan > 0:
        GapThreshold = min(GapThreshold, max(Cadence * 25.0, FullSpan * 0.08))

    Starts = Np.r_[0, Np.where(Deltas > GapThreshold)[0] + 1]
    Ends = Np.r_[Starts[1:], len(Time)]
    return [
        (int(Start), int(End))
        for Start, End in zip(Starts, Ends)
        if End > Start
    ]


#MARK: clean rows
def FluxNormalizationPlan(Flux):
    Values = Np.asarray(Flux, dtype=float)
    Finite = Values[Np.isfinite(Values)]
    if Finite.size == 0:
        return {
            "input_representation": "absolute or relative flux",
            "residual_scale": None,
            "method": "per-observing-segment median",
        }

    Baseline = float(Np.median(Finite))
    Low, High = Np.percentile(Finite, [5.0, 95.0])
    Mad = float(Np.median(Np.abs(Finite - Baseline)))
    RobustSpread = max(1.4826 * Mad, float((High - Low) / 2.0), 1e-12)
    CrossesZero = Low < 0 < High
    ResidualLike = (
        not Math.isfinite(Baseline)
        or Baseline <= 1e-9
        or (CrossesZero and abs(Baseline) <= RobustSpread * 5.0)
    )
    if not ResidualLike:
        return {
            "input_representation": "absolute or relative flux",
            "residual_scale": None,
            "method": "per-observing-segment median",
        }

    Amplitude = float(Np.percentile(Np.abs(Finite), 95.0))
    ResidualScale = 1000000.0 if Amplitude > 1.0 else 1.0
    return {
        "input_representation": (
            "zero-centered residual flux (ppm)"
            if ResidualScale == 1000000.0
            else "zero-centered residual relative flux"
        ),
        "residual_scale": ResidualScale,
        "method": "residual-to-relative conversion, then per-observing-segment median",
    }


#MARK: clean rows
def NormalizeFluxBySegments(Time, Flux):
    Plan = FluxNormalizationPlan(Flux)
    Normalized = Np.asarray(Flux, dtype=float).copy()
    ResidualScale = Plan["residual_scale"]
    if ResidualScale is not None:
        Normalized = 1.0 + Normalized / ResidualScale
    Segments = ObservingSegments(Time)

    for Start, End in Segments:
        Segment = Normalized[Start:End]
        Baseline = float(Np.median(Segment))
        if Math.isfinite(Baseline) and Baseline > 1e-9:
            Normalized[Start:End] = Segment / Baseline

    return Normalized, Segments


#MARK: contiguous regions
def ContiguousRegions(Mask):
    if not Np.any(Mask):
        return []
    Edges = Np.diff(Mask.astype(Np.int8))
    Starts = Np.where(Edges == 1)[0] + 1
    Ends = Np.where(Edges == -1)[0] + 1
    if Mask[0]:
        Starts = Np.r_[0, Starts]
    if Mask[-1]:
        Ends = Np.r_[Ends, Mask.size]
    return list(zip(Starts.tolist(), Ends.tolist()))


#MARK: merge regions
def MergeRegions(Regions, MaxGap):
    if not Regions:
        return []
    Merged = [Regions[0]]
    for Start, End in Regions[1:]:
        PrevStart, PrevEnd = Merged[-1]
        if Start - PrevEnd <= MaxGap:
            Merged[-1] = (PrevStart, End)
        else:
            Merged.append((Start, End))
    return Merged


#MARK: period funcs
def EstimatePeriod(Centers):
    if len(Centers) < 2:
        return None, None, 0
    Centers = Np.asarray(sorted(Centers), dtype=float)
    Gaps = Np.diff(Centers)
    if Gaps.size == 0:
        return None, None, 0

    Period = float(Np.mean(Gaps))
    Scatter = float(Np.std(Gaps)) if Gaps.size > 1 else 0.0
    return Period, Scatter, int(len(Centers))


#MARK: period funcs
def EstimatePeriodFromCandidates(Transits, TimeSpan):
    Centers = Np.asarray([Item["center"] for Item in Transits], dtype=float)
    return EstimatePeriod(Centers)


#MARK: period funcs
def FlattenedFluxForPeriodSearch(Time, Flux):
    Cadence = float(Np.median(Np.diff(Time))) if len(Time) > 1 else 1.0
    FullSpan = float(Time[-1] - Time[0]) if len(Time) > 1 else 0.0
    if FullSpan <= 0:
        return None

    FlattenedFlux = Np.empty_like(Flux, dtype=float)
    for Start, End in ObservingSegments(Time):
        Values = Np.asarray(Flux[Start:End], dtype=float)
        SegmentSteps = Np.diff(Time[Start:End])
        Positive = SegmentSteps[SegmentSteps > 0]
        LocalCadence = float(Np.median(Positive)) if Positive.size else Cadence
        # keep dips for tls. only clip upward spikes here.
        Low, High = RobustFluxLimits(Values, Sigma=5.0)
        Clipped = Np.minimum(Values, High)
        TrendDays = min(10.0, max(2.0, float(Time[End - 1] - Time[Start]) / 6.0))
        TrendWidth = min(len(Values), max(5, int(TrendDays / max(LocalCadence, 1e-9))))
        if TrendWidth % 2 == 0:
            TrendWidth -= 1
        # clip the trend separately so deep dips don't drag the baseline down.
        Trend = MovingAverage(Np.clip(Values, Low, High), max(TrendWidth, 1))
        SegmentFlat = Clipped - Trend
        FlattenedFlux[Start:End] = SegmentFlat - Np.median(SegmentFlat)
    return FlattenedFlux


#MARK: curve funcs
def ChiSquaredTransitProbability(Time, FlattenedFlux, Period, Duration, TransitTime):
    if Chi2 is None or Period <= 0 or Duration <= 0:
        return None

    Phase = ((Time - TransitTime + Period / 2.0) % Period) - Period / 2.0
    InTransit = Np.abs(Phase) <= Duration / 2.0
    if Np.count_nonzero(InTransit) < 3 or Np.count_nonzero(~InTransit) < 3:
        return None

    Y = Np.asarray(FlattenedFlux, dtype=float)
    Baseline = float(Np.mean(Y))
    FlatResiduals = Y - Baseline
    FlatMad = float(Np.median(Np.abs(FlatResiduals - Np.median(FlatResiduals))))
    Sigma = max(1.4826 * FlatMad, float(Np.std(FlatResiduals)), 1e-9)

    InLevel = float(Np.mean(Y[InTransit]))
    OutLevel = float(Np.mean(Y[~InTransit]))
    if InLevel >= OutLevel:
        return None

    BoxModel = Np.where(InTransit, InLevel, OutLevel)
    Chi2Flat = float(Np.sum(((Y - Baseline) / Sigma) ** 2))
    Chi2Box = float(Np.sum(((Y - BoxModel) / Sigma) ** 2))
    DeltaChi2 = max(0.0, Chi2Flat - Chi2Box)
    PValue = float(Chi2.sf(DeltaChi2, 1))
    if not Math.isfinite(PValue):
        PValue = 0.0

    return {
        "chi_squared_flat": Chi2Flat,
        "chi_squared_box": Chi2Box,
        "reduced_chi_squared_box": Chi2Box / max(len(Y) - 2, 1),
        "delta_chi_squared": DeltaChi2,
        "p_value": PValue,
    }


#MARK: period funcs
def PeriodSearchBounds(Cadence, FullSpan, Options=None):
    AutoMinPeriod = max(Cadence * 20.0, 0.5)
    MinimumTransits = int((Options or {}).get("tls_min_transits", 3))
    AutoMaxPeriod = max(AutoMinPeriod * 1.5, FullSpan / max(MinimumTransits, 2))
    MinPeriod = AutoMinPeriod
    MaxPeriod = AutoMaxPeriod
    if Options:
        if Options.get("min_period") is not None:
            MinPeriod = max(Cadence * 2.0, float(Options["min_period"]))
        if Options.get("max_period") is not None:
            MaxPeriod = min(FullSpan * 0.95, float(Options["max_period"]))
    return MinPeriod, MaxPeriod


#MARK: model shape
def DurationSearchBounds(Cadence, FullSpan, Options=None):
    AutoMinDuration = max(Cadence * 4.0, 0.05)
    AutoMaxDuration = min(30.0, max(AutoMinDuration * 2.0, FullSpan / 8.0))
    MinDuration = AutoMinDuration
    MaxDuration = AutoMaxDuration
    if Options:
        if Options.get("min_duration") is not None:
            MinDuration = max(Cadence * 2.0, float(Options["min_duration"]))
        if Options.get("max_duration") is not None:
            MaxDuration = min(FullSpan * 0.25, float(Options["max_duration"]))
    return MinDuration, MaxDuration


#MARK: period funcs
def PeriodGrid(MinPeriod, MaxPeriod, Count):
    if MinPeriod >= MaxPeriod:
        return Np.asarray([], dtype=float)

    LinearPeriods = Np.linspace(MinPeriod, MaxPeriod, Count)
    FrequencyPeriods = 1.0 / Np.linspace(1.0 / MaxPeriod, 1.0 / MinPeriod, Count)
    Periods = Np.unique(Np.r_[LinearPeriods, FrequencyPeriods])
    Periods = Periods[(Periods >= MinPeriod) & (Periods <= MaxPeriod)]
    return Np.sort(Periods.astype(float))


#MARK: period peaks
def BuildPeriodogramPayload(Periods, Powers, PowerMedian=None, PowerStd=None, Method=None, SelectedPeriod=None):
    Periods = Np.asarray(Periods, dtype=float)
    Powers = Np.asarray(Powers, dtype=float)
    Size = min(Periods.size, Powers.size)
    if Size == 0:
        return None

    Periods = Periods[:Size]
    Powers = Powers[:Size]
    Valid = Np.isfinite(Periods) & Np.isfinite(Powers) & (Periods > 0)
    if not Np.any(Valid):
        return None

    Periods = Periods[Valid]
    Powers = Powers[Valid]
    Order = Np.argsort(Periods)
    Periods = Periods[Order]
    Powers = Powers[Order]
    PointCount = int(Periods.size)

    FinitePowers = Powers[Np.isfinite(Powers)]
    if PowerMedian is None or PowerStd is None:
        if FinitePowers.size >= 5:
            PowerMedian = float(Np.median(FinitePowers))
            PowerStd = max(float(Np.std(FinitePowers)), 1e-9)
    if PowerMedian is not None and PowerStd is not None and PowerStd > 0:
        Sdes = (Powers - float(PowerMedian)) / float(PowerStd)
    else:
        Sdes = Np.full(Periods.shape, Np.nan, dtype=float)

    Keep = set(Np.linspace(0, PointCount - 1, min(PointCount, MAX_PERIODOGRAM_POINTS), dtype=int).tolist())
    TopCount = min(80, PointCount)
    if TopCount:
        TopIndices = Np.argpartition(Powers, PointCount - TopCount)[-TopCount:]
        Keep.update(int(Index) for Index in TopIndices)
    if SelectedPeriod is not None and Math.isfinite(float(SelectedPeriod)) and SelectedPeriod > 0:
        Keep.add(int(Np.argmin(Np.abs(Periods - float(SelectedPeriod)))))

    KeepIndices = Np.asarray(sorted(Keep), dtype=int)
    ShownPeriods = Periods[KeepIndices]
    ShownPowers = Powers[KeepIndices]
    ShownSdes = Sdes[KeepIndices]

    return {
        "periods": [float(Value) for Value in ShownPeriods],
        "power": [float(Value) for Value in ShownPowers],
        "sde": [float(Value) if Math.isfinite(float(Value)) else None for Value in ShownSdes],
        "method": Method,
        "selected_period": float(SelectedPeriod) if SelectedPeriod is not None and Math.isfinite(float(SelectedPeriod)) and SelectedPeriod > 0 else None,
        "power_median": float(PowerMedian) if PowerMedian is not None and Math.isfinite(float(PowerMedian)) else None,
        "power_std": float(PowerStd) if PowerStd is not None and Math.isfinite(float(PowerStd)) else None,
        "point_count": PointCount,
        "shown_count": int(ShownPeriods.size),
    }


#MARK: model shape
def ConstrainDurationBounds(Cadence, MinPeriod, MinDuration, MaxDuration, Options=None):
    MaxDuration = min(MaxDuration, MinPeriod * 0.5)
    if MinDuration >= MaxDuration:
        if Options and Options.get("min_duration") is not None:
            return MinDuration, MaxDuration
        MinDuration = max(Cadence * 2.0, MaxDuration * 0.2)
    return MinDuration, MaxDuration


#MARK: bls funcs
def EstimatePeriodWithBinnedBls(Time, Flux, Options=None):
    if len(Time) < 50:
        return None

    Cadence = float(Np.median(Np.diff(Time))) if len(Time) > 1 else 1.0
    FullSpan = float(Time[-1] - Time[0]) if len(Time) > 1 else 0.0
    if FullSpan <= 0:
        return None

    FlattenedFlux = FlattenedFluxForPeriodSearch(Time, Flux)
    if FlattenedFlux is None:
        return None
    ResidualMedian = float(Np.median(FlattenedFlux))
    ResidualMad = float(Np.median(Np.abs(FlattenedFlux - ResidualMedian)))
    Sigma = max(1.4826 * ResidualMad, float(Np.std(FlattenedFlux)), 1e-9)

    MinPeriod, MaxPeriod = PeriodSearchBounds(Cadence, FullSpan, Options)
    MinDuration, MaxDuration = DurationSearchBounds(Cadence, FullSpan, Options)
    MinDuration, MaxDuration = ConstrainDurationBounds(Cadence, MinPeriod, MinDuration, MaxDuration, Options)
    if MinPeriod >= MaxPeriod or MinDuration >= MaxDuration:
        return None

    Periods = PeriodGrid(MinPeriod, MaxPeriod, 900)
    Durations = Np.linspace(MinDuration, MaxDuration, 10)
    BinCount = 360
    Best = None
    Powers = []
    ReferenceTime = float(Time[0])

    for Period in Periods:
        Phase = ((Time - ReferenceTime) % Period) / Period
        BinIds = Np.minimum((Phase * BinCount).astype(int), BinCount - 1)
        Sums = Np.bincount(BinIds, weights=FlattenedFlux, minlength=BinCount)
        Counts = Np.bincount(BinIds, minlength=BinCount)
        DoubledSums = Np.r_[Sums, Sums]
        DoubledCounts = Np.r_[Counts, Counts]
        SumPrefix = Np.r_[0.0, Np.cumsum(DoubledSums)]
        CountPrefix = Np.r_[0.0, Np.cumsum(DoubledCounts)]
        PeriodBestPower = -Math.inf

        for Duration in Durations:
            Window = max(1, int(round((Duration / Period) * BinCount)))
            if Window >= BinCount // 2:
                continue

            WindowSums = SumPrefix[Window:Window + BinCount] - SumPrefix[:BinCount]
            WindowCounts = CountPrefix[Window:Window + BinCount] - CountPrefix[:BinCount]
            Valid = WindowCounts > 2
            if not Np.any(Valid):
                continue

            Means = Np.where(Valid, WindowSums / Np.maximum(WindowCounts, 1), Np.inf)
            BinIndex = int(Np.argmin(Means))
            Depth = -float(Means[BinIndex])
            if Depth <= 0:
                continue

            power = Depth / Sigma * Math.sqrt(max(float(WindowCounts[BinIndex]), 1.0))
            PeriodBestPower = max(PeriodBestPower, power)
            if Best is None or power > Best["power"]:
                TransitTime = ReferenceTime + ((BinIndex + Window / 2.0) / BinCount) * Period
                Best = {
                    "period": float(Period),
                    "duration": float(Duration),
                    "transit_time": float(TransitTime),
                    "power": float(power),
                }

        Powers.append(PeriodBestPower if Math.isfinite(PeriodBestPower) else 0.0)

    if Best is None:
        return None

    Powers = Np.asarray(Powers, dtype=float)
    FinitePowers = Powers[Np.isfinite(Powers)]
    PowerMedian = None
    PowerStd = None
    if FinitePowers.size >= 5:
        PowerMedian = float(Np.median(FinitePowers))
        PowerStd = max(float(Np.std(FinitePowers)), 1e-9)
        Sde = (Best["power"] - PowerMedian) / PowerStd
    else:
        Sde = None

    CandidateIndices = Np.argsort(Powers)[-8:][::-1]
    Candidates = []
    for Index in CandidateIndices:
        power = float(Powers[Index])
        if not Math.isfinite(power) or power <= 0:
            continue
        Candidates.append({
            "period": float(Periods[Index]),
            "power": power,
            "sde": None if Sde is None else float((power - PowerMedian) / PowerStd),
        })

    FirstEpoch = Math.ceil((Time[0] - Best["transit_time"]) / Best["period"])
    LastEpoch = Math.floor((Time[-1] - Best["transit_time"]) / Best["period"])
    ExpectedCount = max(1, int(LastEpoch - FirstEpoch + 1))
    ChiSquared = ChiSquaredTransitProbability(
        Time,
        FlattenedFlux,
        Best["period"],
        Best["duration"],
        Best["transit_time"],
    )
    return {
        "period": Best["period"],
        "scatter": 0.0,
        "count": ExpectedCount,
        "duration": Best["duration"],
        "transit_time": Best["transit_time"],
        "power": Best["power"],
        "sde": Sde,
        "candidates": Candidates,
        "periodogram": BuildPeriodogramPayload(
            Periods,
            Powers,
            PowerMedian=PowerMedian,
            PowerStd=PowerStd,
            Method="binned BLS fallback",
            SelectedPeriod=Best["period"],
        ),
        "search_min_period": float(MinPeriod),
        "search_max_period": float(MaxPeriod),
        "search_min_duration": float(MinDuration),
        "search_max_duration": float(MaxDuration),
        "method": "binned BLS fallback",
        **(ChiSquared or {}),
    }


#MARK: bls funcs
def EstimatePeriodWithBls(Time, Flux, Options=None):
    if BoxLeastSquares is None or len(Time) < 50:
        return EstimatePeriodWithBinnedBls(Time, Flux, Options)

    Cadence = float(Np.median(Np.diff(Time))) if len(Time) > 1 else 1.0
    FullSpan = float(Time[-1] - Time[0]) if len(Time) > 1 else 0.0
    if FullSpan <= 0:
        return None

    FlattenedFlux = FlattenedFluxForPeriodSearch(Time, Flux)
    if FlattenedFlux is None:
        return None

    MinPeriod, MaxPeriod = PeriodSearchBounds(Cadence, FullSpan, Options)
    MinDuration, MaxDuration = DurationSearchBounds(Cadence, FullSpan, Options)
    MinDuration, MaxDuration = ConstrainDurationBounds(Cadence, MinPeriod, MinDuration, MaxDuration, Options)
    if MinPeriod >= MaxPeriod or MinDuration >= MaxDuration:
        return None

    Periods = PeriodGrid(MinPeriod, MaxPeriod, 1200)
    Durations = Np.linspace(MinDuration, MaxDuration, 12)
    try:
        Model = BoxLeastSquares(Time, FlattenedFlux)
        Result = Model.power(Periods, Durations)
    except Exception:
        return EstimatePeriodWithBinnedBls(Time, Flux, Options)

    if len(Result.power) == 0 or not Np.any(Np.isfinite(Result.power)):
        return None

    BestIndex = int(Np.nanargmax(Result.power))
    Period = float(Result.period[BestIndex])
    Duration = float(Result.duration[BestIndex])
    TransitTime = float(Result.transit_time[BestIndex])
    power = float(Result.power[BestIndex])
    if not Math.isfinite(Period) or Period <= 0:
        return None

    FirstEpoch = Math.ceil((Time[0] - TransitTime) / Period)
    LastEpoch = Math.floor((Time[-1] - TransitTime) / Period)
    ExpectedCount = max(1, int(LastEpoch - FirstEpoch + 1))
    ChiSquared = ChiSquaredTransitProbability(Time, FlattenedFlux, Period, Duration, TransitTime)
    Order = Np.argsort(Result.power)[-8:][::-1]
    Candidates = []
    PowerMedian = float(Np.nanmedian(Result.power))
    PowerStd = max(float(Np.nanstd(Result.power)), 1e-9)
    for Index in Order:
        if not Math.isfinite(float(Result.power[Index])):
            continue
        PowerValue = float(Result.power[Index])
        Candidates.append({
            "period": float(Result.period[Index]),
            "power": PowerValue,
            "sde": (PowerValue - PowerMedian) / PowerStd,
        })

    return {
        "period": Period,
        "scatter": 0.0,
        "count": ExpectedCount,
        "duration": Duration,
        "transit_time": TransitTime,
        "power": power,
        "sde": (power - PowerMedian) / PowerStd,
        "candidates": Candidates,
        "periodogram": BuildPeriodogramPayload(
            Result.period,
            Result.power,
            PowerMedian=PowerMedian,
            PowerStd=PowerStd,
            Method="BLS",
            SelectedPeriod=Period,
        ),
        "search_min_period": float(MinPeriod),
        "search_max_period": float(MaxPeriod),
        "search_min_duration": float(MinDuration),
        "search_max_duration": float(MaxDuration),
        "method": "BLS",
        **(ChiSquared or {}),
    }


#MARK: tls funcs
def NormalizedFluxForTls(Time, Flux):
    Flux = Np.asarray(Flux, dtype=float)
    Plan = FluxNormalizationPlan(Flux)
    ResidualScale = Plan["residual_scale"]
    if ResidualScale is not None:
        Normalized = 1.0 + Flux / ResidualScale
    else:
        Baseline = float(Np.median(Flux))
        Normalized = Flux / Baseline

    Flattened = FlattenedFluxForPeriodSearch(Time, Normalized)
    if Flattened is None:
        return None, None
    TlsFlux = 1.0 + Flattened
    Finite = TlsFlux[Np.isfinite(TlsFlux)]
    if Finite.size == 0:
        return None, None
    PositiveFloor = max(float(Np.percentile(Finite, 0.01)), 1e-6)
    TlsFlux = Np.maximum(TlsFlux, PositiveFloor)
    Residual = TlsFlux - 1.0
    ResidualMedian = float(Np.median(Residual))
    ResidualMad = float(Np.median(Np.abs(Residual - ResidualMedian)))
    RobustNoise = max(1.4826 * ResidualMad, float(Np.std(Residual)), 1e-9)
    return TlsFlux, RobustNoise


#MARK: tls funcs
def EstimatePeriodWithTls(Time, Flux, Options=None, ProgressCallback=None):
    if len(Time) < 50:
        raise ValueError("TLS needs at least 50 finite light-curve samples.")
    if Options is None:
        Options = dict(DEFAULT_DETECTION_OPTIONS)

    Cadence = float(Np.median(Np.diff(Time))) if len(Time) > 1 else 1.0
    FullSpan = float(Time[-1] - Time[0]) if len(Time) > 1 else 0.0
    if FullSpan <= 0:
        return None

    TlsFlux, TlsNoise = NormalizedFluxForTls(Time, Flux)
    if TlsFlux is None:
        return None
    MinPeriod, MaxPeriod = PeriodSearchBounds(Cadence, FullSpan, Options)
    MaxPeriod = min(MaxPeriod, FullSpan / max(int(Options.get("tls_min_transits", 3)), 1))
    if MinPeriod >= MaxPeriod:
        raise ValueError(
            "TLS period bounds do not leave room for the requested minimum number of transits."
        )

    TlsOptions = {
        **Options,
        "period_min": float(MinPeriod),
        "period_max": float(MaxPeriod),
    }
    Result = RunTlsSearch(Time, TlsFlux, TlsOptions, ProgressCallback=ProgressCallback)
    FlattenedFlux = TlsFlux - 1.0
    ChiSquared = ChiSquaredTransitProbability(
        Time,
        FlattenedFlux,
        Result["period"],
        Result["duration"],
        Result["transit_time"],
    )
    ExpectedCount = Result.get("transit_count")
    if ExpectedCount is None:
        FirstEpoch = Math.ceil((Time[0] - Result["transit_time"]) / Result["period"])
        LastEpoch = Math.floor((Time[-1] - Result["transit_time"]) / Result["period"])
        ExpectedCount = max(1, int(LastEpoch - FirstEpoch + 1))

    return {
        "period": Result["period"],
        "period_uncertainty": Result.get("period_uncertainty"),
        "scatter": Result.get("period_uncertainty") or 0.0,
        "count": int(ExpectedCount),
        "duration": Result["duration"],
        "transit_time": Result["transit_time"],
        "power": Result.get("power"),
        "sde": Result.get("sde"),
        "sde_raw": Result.get("sde_raw"),
        "fap": Result.get("fap"),
        "snr": Result.get("snr"),
        "candidates": Result.get("candidates", []),
        "periodogram": Result.get("periodogram"),
        "search_min_period": float(MinPeriod),
        "search_max_period": float(MaxPeriod),
        "search_min_duration": None,
        "search_max_duration": None,
        "method": "TLS",
        "tls_noise": TlsNoise,
        "tls_result": Result,
        "transit_model": Result.get("model"),
        **(ChiSquared or {}),
    }


#MARK: transit checks
def RobustStandardError(Values):
    Values = Np.asarray(Values, dtype=float)
    Values = Values[Np.isfinite(Values)]
    if Values.size < 2:
        return None
    Center = float(Np.median(Values))
    Sigma = max(1.4826 * float(Np.median(Np.abs(Values - Center))), 1e-9)
    # median standard error, with a short-block noise floor for correlations.
    Error = 1.253 * Sigma / Math.sqrt(Values.size)
    if Values.size >= 12:
        Blocks = [Np.mean(Block) for Block in Np.array_split(Values - Center, min(8, Values.size // 3))]
        Error = max(Error, float(Np.std(Blocks, ddof=1)) / Math.sqrt(len(Blocks)))
    return float(Error)


#MARK: tls funcs
def TransitsFromTlsResult(Time, Flux, TlsPeriod):
    if TlsPeriod is None:
        return []
    Result = TlsPeriod.get("tls_result") or {}
    Duration = FiniteNumber(TlsPeriod.get("duration"))
    Period = FiniteNumber(TlsPeriod.get("period"))
    Epoch = FiniteNumber(TlsPeriod.get("transit_time"))
    if Duration is None or Duration <= 0 or Period is None or Epoch is None:
        return []
    Time, Flux = Np.asarray(Time, dtype=float), Np.asarray(Flux, dtype=float)
    Segments = ObservingSegments(Time)
    Steps = Np.diff(Time)
    Positive = Steps[Steps > 0]
    Cadence = float(Np.median(Positive)) if Positive.size else Duration
    Transits = []
    for Center in FiniteValues(Result.get("transit_times", [])):
        Start, End = Center - Duration / 2.0, Center + Duration / 2.0
        Left = int(Np.searchsorted(Time, Start, side="left"))
        Right = int(Np.searchsorted(Time, End, side="right"))
        Count = Right - Left
        Segment = next(((A, B) for A, B in Segments if Time[A] <= Center <= Time[B - 1]), None)
        ExpectedPoints = max(1.0, Duration / max(Cadence, 1e-9))
        Coverage = min(1.0, Count / ExpectedPoints)
        Shoulders = Np.asarray([], dtype=float)
        if Segment is not None:
            A, B = Segment
            ShoulderStart = max(A, int(Np.searchsorted(Time, Center - Duration * 2.5)))
            ShoulderLeft = max(A, min(B, int(Np.searchsorted(Time, Center - Duration * 0.75, side="right"))))
            ShoulderRight = max(A, min(B, int(Np.searchsorted(Time, Center + Duration * 0.75))))
            ShoulderEnd = min(B, int(Np.searchsorted(Time, Center + Duration * 2.5, side="right")))
            Shoulders = Np.r_[Flux[ShoulderStart:ShoulderLeft], Flux[ShoulderRight:ShoulderEnd]]
        InFlux = Np.asarray(Flux[Left:Right], dtype=float)
        CoreFlux = InFlux[Np.abs(Time[Left:Right] - Center) <= Duration * 0.25]
        if CoreFlux.size < 3:
            CoreFlux = InFlux
        Baseline = float(Np.median(Shoulders)) if Shoulders.size >= 3 else None
        Depth = Baseline - float(Np.median(CoreFlux)) if Baseline is not None and CoreFlux.size else None
        InError = RobustStandardError(CoreFlux)
        OutError = RobustStandardError(Shoulders)
        Error = Math.hypot(InError, OutError) if InError is not None and OutError is not None else None
        LocalSnr = Depth / Error if Depth is not None and Error and Error > 0 else None
        if Count == 0:
            State = "outside_observations"
        elif Segment is None or Count < 3 or Shoulders.size < 6 or Coverage < 0.35:
            State = "insufficient_coverage"
        elif LocalSnr is not None and LocalSnr >= 3.0 and Depth > 0:
            State = "supported_dip"
        else:
            State = "unsupported_window"
        MeasuredCenter = TimingError = None
        if State == "supported_dip" and Count >= 5:
            # a flux-weighted local centroid is measured from observations,
            # not copied from t0+np. it is conditional on the selected window.
            Deficits = Np.maximum(0.0, Baseline - InFlux - (OutError or 0.0))
            if Deficits.sum() > 0:
                MeasuredCenter = float(Np.sum(Time[Left:Right] * Deficits) / Deficits.sum())
                TimingError = max(Cadence / Math.sqrt(12.0), Duration / (2.0 * LocalSnr))
        Values = Np.r_[InFlux, Baseline] if Baseline is not None else InFlux
        RawMin, RawMax = (Np.percentile(Values, [5, 95]).tolist() if Values.size else [None, None])
        Transits.append({
            "start": float(Start), "end": float(End), "center": float(Center),
            "predicted_center": float(Center), "measured_center": MeasuredCenter,
            "timing_uncertainty": TimingError, "timing_method": "conditional local flux centroid" if MeasuredCenter is not None else None,
            "cycle_number": int(round((Center - Epoch) / Period)),
            "duration": float(Duration), "depth": Depth, "signed_depth": Depth,
            "depth_estimator": "median flux in central half of predicted window relative to local shoulders",
            "full_window_depth": Baseline - float(Np.median(InFlux)) if Baseline is not None and Count else None,
            "depth_uncertainty": Error, "local_snr": LocalSnr,
            "local_baseline": Baseline, "points": int(Count), "coverage_fraction": float(Coverage),
            "baseline_points": int(Shoulders.size), "state": State,
            "flux_min": float(RawMin) if RawMin is not None else None,
            "flux_max": float(RawMax) if RawMax is not None else None,
            "source": "TLS model", "evidence_source": "local observations",
        })
    return Transits


#MARK: period checks
def TransitRegularityTolerance(Period, Durations):
    CleanDurations = Np.asarray(
        [Value for Value in Durations if Math.isfinite(float(Value)) and float(Value) > 0],
        dtype=float,
    )
    DurationScale = float(Np.percentile(CleanDurations, 40)) if CleanDurations.size else 0.0
    Tolerance = max(DurationScale * 1.25, Period * 0.02)
    return float(min(Tolerance, Period * 0.12))


#MARK: period checks
def IsDenseRegularityMatch(MatchCount, EventCount, ExpectedCoverage, TransitCount):
    if (
        MatchCount is None
        or EventCount is None
        or ExpectedCoverage is None
        or TransitCount < 12
    ):
        return False
    DenseBoxFloor = max(6, int(Math.ceil(TransitCount * 0.35)))
    return (
        int(MatchCount) >= DenseBoxFloor
        and int(EventCount) >= 3
        and float(MatchCount) / TransitCount >= 0.35
        and float(ExpectedCoverage) >= 0.30
    )


#MARK: period checks
def ScoreTransitRegularityPeriod(
    Centers,
    Durations,
    Depths,
    TimeStart,
    TimeEnd,
    Period,
    CandidateSupport=0,
    PairSupport=0,
    FixedEpoch=None,
):
    if Centers.size < 3 or not Math.isfinite(float(Period)) or Period <= 0:
        return None

    Period = float(Period)
    Tolerance = TransitRegularityTolerance(Period, Durations)
    if not Math.isfinite(Tolerance) or Tolerance <= 0:
        return None

    EpochValues = [float(FixedEpoch)] if FixedEpoch is not None and Math.isfinite(float(FixedEpoch)) else Centers
    Best = None
    for Epoch in EpochValues:
        FirstEpoch = Math.ceil((float(TimeStart) - Epoch) / Period)
        LastEpoch = Math.floor((float(TimeEnd) - Epoch) / Period)
        ExpectedCount = int(LastEpoch - FirstEpoch + 1)
        if ExpectedCount < 3:
            continue

        Residuals = Np.abs(((Centers - Epoch + Period / 2.0) % Period) - Period / 2.0)
        MatchedMask = Residuals <= Tolerance
        MatchedIndices = Np.flatnonzero(MatchedMask)
        if MatchedIndices.size == 0:
            continue

        MatchedCycles = Np.rint((Centers[MatchedIndices] - Epoch) / Period).astype(int)
        UniqueCycles = Np.unique(MatchedCycles)
        EventMatchCount = int(UniqueCycles.size)
        if EventMatchCount == 0:
            continue

        RepresentativeDepths = []
        RepresentativeDurations = []
        RepresentativeResiduals = []
        for Cycle in UniqueCycles:
            CycleIndices = MatchedIndices[MatchedCycles == Cycle]
            BestIndex = int(CycleIndices[Np.argmax(Depths[CycleIndices])])
            RepresentativeDepths.append(float(Depths[BestIndex]))
            RepresentativeDurations.append(float(Durations[BestIndex]))
            RepresentativeResiduals.append(float(Residuals[BestIndex]))

        BoxMatchCount = int(MatchedIndices.size)
        ExpectedCoverage = EventMatchCount / ExpectedCount
        ResidualRms = float(Np.sqrt(Np.mean(Np.asarray(RepresentativeResiduals) ** 2)))
        DepthSum = float(Np.sum(RepresentativeDepths))
        Duration = MedianOrNone(RepresentativeDurations) or MedianOrNone(Durations) or Tolerance
        ScoreKey = (
            BoxMatchCount,
            EventMatchCount,
            ExpectedCoverage,
            int(PairSupport),
            int(CandidateSupport),
            DepthSum,
            -ResidualRms,
            -Period,
        )
        Candidate = {
            "period": Period,
            "scatter": ResidualRms,
            "count": ExpectedCount,
            "duration": float(Duration),
            "transit_time": float(Epoch),
            "event_match_count": EventMatchCount,
            "box_match_count": BoxMatchCount,
            "expected_count": ExpectedCount,
            "expected_coverage": ExpectedCoverage,
            "match_fraction": BoxMatchCount / Centers.size,
            "pair_support": int(PairSupport),
            "candidate_support": int(CandidateSupport),
            "tolerance": Tolerance,
            "depth_sum": DepthSum,
            "residual_median": MedianOrNone(RepresentativeResiduals),
            "residual_rms": ResidualRms,
            "method": "transit regularity",
            "_score_key": ScoreKey,
        }
        if Best is None or ScoreKey > Best["_score_key"]:
            Best = Candidate

    return Best


#MARK: period checks
def EstimatePeriodByTransitRegularity(Transits, Time, Options=None, BlsPeriod=None):
    if len(Transits) < 3 or len(Time) < 3:
        return None

    Centers = Np.asarray([Item["center"] for Item in Transits], dtype=float)
    Durations = Np.asarray([max(float(Item.get("duration", 0.0)), 0.0) for Item in Transits], dtype=float)
    Depths = Np.asarray([max(float(Item.get("depth", 0.0)), 0.0) for Item in Transits], dtype=float)
    FiniteMask = Np.isfinite(Centers) & Np.isfinite(Durations) & Np.isfinite(Depths)
    Centers = Centers[FiniteMask]
    Durations = Durations[FiniteMask]
    Depths = Depths[FiniteMask]
    if Centers.size < 3:
        return None

    Order = Np.argsort(Centers)
    Centers = Centers[Order]
    Durations = Durations[Order]
    Depths = Depths[Order]

    Cadence = float(Np.median(Np.diff(Time))) if len(Time) > 1 else 1.0
    FullSpan = float(Time[-1] - Time[0]) if len(Time) > 1 else 0.0
    if FullSpan <= 0:
        return None

    MinPeriod, MaxPeriod = PeriodSearchBounds(Cadence, FullSpan, Options)
    PositiveDurations = Durations[Durations > 0]
    if PositiveDurations.size:
        DurationFloor = float(Np.percentile(PositiveDurations, 40))
        MinPeriod = max(MinPeriod, DurationFloor * 4.0)
    if MinPeriod >= MaxPeriod:
        return None

    Resolution = max(Cadence * 5.0, FullSpan / 50000.0, 1e-4)
    Candidates = {}

    def AddCandidate(Period, Support=1, Pair=False):
        if Period is None:
            return
        try:
            PeriodValue = float(Period)
        except (TypeError, ValueError):
            return
        if not Math.isfinite(PeriodValue) or PeriodValue < MinPeriod or PeriodValue > MaxPeriod:
            return
        Key = int(round(PeriodValue / Resolution))
        Record = Candidates.setdefault(
            Key,
            {"period_sum": 0.0, "weight": 0.0, "support": 0, "pair_support": 0},
        )
        Weight = max(float(Support), 1.0)
        Record["period_sum"] += PeriodValue * Weight
        Record["weight"] += Weight
        Record["support"] += int(max(round(Weight), 1))
        if Pair:
            Record["pair_support"] += int(max(round(Weight), 1))

    PairCount = min(80, Centers.size)
    if Centers.size > PairCount:
        Strongest = Np.argsort(Depths)[-PairCount:]
        PairCenters = Np.sort(Centers[Strongest])
    else:
        PairCenters = Centers

    for LeftIndex in range(PairCenters.size):
        for RightIndex in range(LeftIndex + 1, PairCenters.size):
            Gap = float(PairCenters[RightIndex] - PairCenters[LeftIndex])
            if Gap < MinPeriod:
                continue
            MaxCycles = min(30, int(Gap / MinPeriod))
            for CycleCount in range(1, MaxCycles + 1):
                AddCandidate(Gap / CycleCount, Pair=True)

    BlsSources = []
    if BlsPeriod is not None:
        BlsSources.append(BlsPeriod)
        BlsSources.extend(BlsPeriod.get("candidates", []))
    for Source in BlsSources:
        SourcePeriod = Source.get("period") if isinstance(Source, dict) else None
        AddCandidate(SourcePeriod, Support=30)
        if SourcePeriod is None:
            continue
        for Divisor in range(2, 13):
            AddCandidate(float(SourcePeriod) / Divisor, Support=12)
        for Multiple in range(2, 5):
            AddCandidate(float(SourcePeriod) * Multiple, Support=6)

    if not Candidates:
        return None

    CandidateRecords = sorted(
        Candidates.values(),
        key=lambda Item: (Item["pair_support"], Item["support"]),
        reverse=True,
    )[:3000]

    PairSupportFloor = max(3, min(12, int(Math.ceil(Centers.size * 0.25))))
    EventFloor = max(3, min(6, int(Math.ceil(Centers.size * 0.25))))
    Best = None
    for Record in CandidateRecords:
        Period = Record["period_sum"] / max(Record["weight"], 1.0)
        Score = ScoreTransitRegularityPeriod(
            Centers,
            Durations,
            Depths,
            float(Time[0]),
            float(Time[-1]),
            Period,
            CandidateSupport=Record["support"],
            PairSupport=Record["pair_support"],
        )
        if Score is None:
            continue
        if Score["pair_support"] < PairSupportFloor:
            continue
        if Score["event_match_count"] < EventFloor:
            continue
        if (
            Score["expected_coverage"] < 0.55
            and not IsDenseRegularityMatch(
                Score["box_match_count"],
                Score["event_match_count"],
                Score["expected_coverage"],
                Centers.size,
            )
        ):
            continue
        if Best is None or Score["_score_key"] > Best["_score_key"]:
            Best = Score

    if Best is None:
        return None

    Best.pop("_score_key", None)
    return Best


#MARK: period checks
def ShouldPreferRegularityPeriod(RegularityPeriod, BlsPeriod, Transits, Time):
    if RegularityPeriod is None:
        return False
    if BlsPeriod is None:
        return True

    BlsValue = float(BlsPeriod.get("period", 0.0) or 0.0)
    RegularValue = float(RegularityPeriod.get("period", 0.0) or 0.0)
    if BlsValue <= 0 or RegularValue <= 0:
        return True
    if abs(RegularValue - BlsValue) / BlsValue <= 0.02:
        return False

    Centers = Np.asarray([Item["center"] for Item in Transits], dtype=float)
    Durations = Np.asarray([max(float(Item.get("duration", 0.0)), 0.0) for Item in Transits], dtype=float)
    Depths = Np.asarray([max(float(Item.get("depth", 0.0)), 0.0) for Item in Transits], dtype=float)
    BlsScore = ScoreTransitRegularityPeriod(
        Centers,
        Durations,
        Depths,
        float(Time[0]),
        float(Time[-1]),
        BlsValue,
        FixedEpoch=BlsPeriod.get("transit_time"),
    )
    BlsEventCount = int(BlsScore.get("event_match_count", 0)) if BlsScore else 0
    BlsCoverage = float(BlsScore.get("expected_coverage", 0.0)) if BlsScore else 0.0
    RegularEventCount = int(RegularityPeriod.get("event_match_count", 0))
    RegularBoxCount = int(RegularityPeriod.get("box_match_count", 0))
    RegularCoverage = float(RegularityPeriod.get("expected_coverage", 0.0))
    TransitCount = len(Transits)

    if RegularEventCount >= BlsEventCount + 2 and RegularCoverage >= 0.55:
        return True
    if (
        RegularEventCount >= BlsEventCount + 2
        and IsDenseRegularityMatch(
            RegularBoxCount,
            RegularEventCount,
            RegularCoverage,
            TransitCount,
        )
    ):
        return True
    return (
        RegularValue < BlsValue
        and RegularEventCount >= BlsEventCount
        and RegularCoverage >= max(0.65, BlsCoverage)
    )


#MARK: bls funcs
def DealiasedBlsPeriod(BlsPeriod, Transits, Time, Flux):
    if BlsPeriod is None or len(Transits) < 3:
        return BlsPeriod

    TopPeriod = FiniteNumber(BlsPeriod.get("period"))
    TopPower = FiniteNumber(BlsPeriod.get("power"))
    if TopPeriod is None or TopPeriod <= 0 or TopPower is None or TopPower <= 0:
        return BlsPeriod

    Candidates = [
        Candidate
        for Candidate in BlsPeriod.get("candidates", [])
        if FiniteNumber(Candidate.get("period")) is not None
    ]
    if len(Candidates) < 2:
        return BlsPeriod

    Centers = Np.asarray([Item["center"] for Item in Transits], dtype=float)
    Durations = Np.asarray([max(float(Item.get("duration", 0.0)), 0.0) for Item in Transits], dtype=float)
    Depths = Np.asarray([max(float(Item.get("depth", 0.0)), 0.0) for Item in Transits], dtype=float)
    TopScore = ScoreTransitRegularityPeriod(
        Centers,
        Durations,
        Depths,
        float(Time[0]),
        float(Time[-1]),
        TopPeriod,
    )
    if TopScore is None:
        return BlsPeriod

    Best = None
    for Candidate in Candidates:
        CandidatePeriod = FiniteNumber(Candidate.get("period"))
        CandidatePower = FiniteNumber(Candidate.get("power"))
        CandidateSde = FiniteNumber(Candidate.get("sde"))
        if CandidatePeriod is None or CandidatePower is None:
            continue
        if CandidatePeriod <= TopPeriod * 1.5:
            continue

        Ratio = CandidatePeriod / TopPeriod
        Harmonic = int(round(Ratio))
        if Harmonic < 2 or Harmonic > 4:
            continue
        if abs(Ratio / Harmonic - 1.0) > 0.035:
            continue
        if CandidatePower / TopPower < 0.75:
            continue
        if CandidateSde is not None and CandidateSde < 5.0:
            continue

        CandidateScore = ScoreTransitRegularityPeriod(
            Centers,
            Durations,
            Depths,
            float(Time[0]),
            float(Time[-1]),
            CandidatePeriod,
        )
        if CandidateScore is None:
            continue

        TopBoxCount = int(TopScore.get("box_match_count", 0))
        TopEventCount = int(TopScore.get("event_match_count", 0))
        CandidateBoxCount = int(CandidateScore.get("box_match_count", 0))
        CandidateEventCount = int(CandidateScore.get("event_match_count", 0))
        if CandidateBoxCount < max(3, int(Math.floor(TopBoxCount * 0.9))):
            continue
        if CandidateEventCount < max(3, int(Math.floor(TopEventCount * 0.9))):
            continue
        if CandidateScore["expected_count"] >= TopScore["expected_count"] * 0.75:
            continue

        SelectionKey = (
            CandidateBoxCount,
            CandidateEventCount,
            CandidatePower / TopPower,
            CandidateSde if CandidateSde is not None else 0.0,
            CandidatePeriod,
        )
        if Best is None or SelectionKey > Best["selection_key"]:
            Best = {
                "candidate": Candidate,
                "score": CandidateScore,
                "harmonic": Harmonic,
                "selection_key": SelectionKey,
            }

    if Best is None:
        return BlsPeriod

    Candidate = Best["candidate"]
    Score = Best["score"]
    FlattenedFlux = FlattenedFluxForPeriodSearch(Time, Flux)
    ChiSquared = None if FlattenedFlux is None else ChiSquaredTransitProbability(
        Time,
        FlattenedFlux,
        Score["period"],
        Score["duration"],
        Score["transit_time"],
    )

    SelectedPeriod = Score["period"]
    SelectedCandidates = []
    SelectedSeen = set()
    for Item in [Candidate, *Candidates]:
        ItemPeriod = FiniteNumber(Item.get("period"))
        if ItemPeriod is None:
            continue
        Key = round(ItemPeriod, 10)
        if Key in SelectedSeen:
            continue
        SelectedSeen.add(Key)
        SelectedCandidates.append(Item)

    return {
        **BlsPeriod,
        "period": SelectedPeriod,
        "scatter": Score["scatter"],
        "count": Score["expected_count"],
        "duration": Score["duration"],
        "transit_time": Score["transit_time"],
        "power": FiniteNumber(Candidate.get("power")) or BlsPeriod.get("power"),
        "sde": FiniteNumber(Candidate.get("sde")),
        "candidates": SelectedCandidates,
        "harmonic_alias_corrected": True,
        "harmonic_alias_period": TopPeriod,
        "harmonic_alias_factor": Best["harmonic"],
        "harmonic_alias_power_ratio": (FiniteNumber(Candidate.get("power")) or 0.0) / TopPower,
        **(ChiSquared or {}),
    }


#MARK: curve funcs
def TimeAtFractionalIndex(Time, IndexPosition):
    if IndexPosition <= 0:
        return float(Time[0])
    if IndexPosition >= len(Time) - 1:
        return float(Time[-1])
    Left = int(Math.floor(IndexPosition))
    Right = int(Math.ceil(IndexPosition))
    if Left == Right:
        return float(Time[Left])
    Fraction = IndexPosition - Left
    return float(Time[Left] + (Time[Right] - Time[Left]) * Fraction)


#MARK: prune overlapping transits
def PruneOverlappingTransits(Transits):
    if not Transits:
        return []

    Kept = []
    for Candidate in sorted(Transits, key=lambda Item: Item["center"]):
        if not Kept:
            Kept.append(Candidate)
            continue

        Prev = Kept[-1]
        Overlap = min(Prev["end"], Candidate["end"]) - max(Prev["start"], Candidate["start"])
        Shorter = max(min(Prev["duration"], Candidate["duration"]), 1e-9)
        if Overlap > 0 and Overlap / Shorter > 0.78:
            if Candidate["depth"] > Prev["depth"]:
                Kept[-1] = Candidate
            continue
        Kept.append(Candidate)
    return Kept


#MARK: dip funcs
def DetectTransitsByProminence(Time, Flux, MedianFlux, Options):
    if FindPeaks is None:
        return None

    ClippedLow, ClippedHigh = RobustFluxLimits(Flux, Sigma=3.0)
    ClippedFlux = Np.clip(Flux, ClippedLow, ClippedHigh)

    Strictness = float(Options["strictness"])
    Smoothing = float(Options["smoothing"])
    BaseSmoothWidth = int(max(31, min(201, len(ClippedFlux) // 360)))
    SmoothWidth = OddWindowWidth(BaseSmoothWidth, Smoothing, 7, 501)
    Smoothed = MovingAverageBySegments(ClippedFlux, SmoothWidth, ObservingSegments(Time))

    Baseline = float(Np.median(Smoothed))
    Mad = float(Np.median(Np.abs(Smoothed - Baseline)))
    RobustNoise = max(1.4826 * Mad, 1e-9)
    Cadence = float(Np.median(Np.diff(Time))) if len(Time) > 1 else 1.0
    FullSpan = float(Time[-1] - Time[0]) if len(Time) > 1 else 0.0

    AutoMinWidthTime = max(Cadence * 4.0, min(0.08, FullSpan / 5000.0))
    AutoMaxCurveTime = max(AutoMinWidthTime * 4.0, min(36.0, max(1.0, FullSpan * 0.12)))
    MinWidthTime = (
        max(Cadence * 2.0, float(Options["min_duration"]))
        if Options["min_duration"] is not None
        else AutoMinWidthTime
    )
    MaxCurveTime = (
        max(MinWidthTime * 1.2, float(Options["max_duration"]))
        if Options["max_duration"] is not None
        else AutoMaxCurveTime
    )
    MaxCurvePoints = max(4, int(MaxCurveTime / Cadence))
    MinDistanceTime = max(MinWidthTime * 2.5, min(4.0, FullSpan / 350.0))
    MinDistancePoints = max(SmoothWidth // 2, int(MinDistanceTime / Cadence))
    AutoMinProminence = max(2.2 * RobustNoise, abs(MedianFlux) * 0.002) * Strictness
    MinProminence = (
        float(Options["min_depth"])
        if Options["min_depth"] is not None
        else AutoMinProminence
    )

    Peaks, Properties = FindPeaks(
        -Smoothed,
        prominence=MinProminence,
        distance=MinDistancePoints,
        wlen=MaxCurvePoints * 2,
    )

    if len(Peaks) == 0:
        return {
            "transits": [],
            "robust_noise": RobustNoise,
            "smooth_points": SmoothWidth,
        }

    Transits = []
    PeakIndexes = Np.asarray(sorted(Peaks.tolist()), dtype=int)
    ProminenceByIndex = {
        int(PeakIndex): float(Properties["prominences"][Offset])
        for Offset, PeakIndex in enumerate(Peaks)
    }

    for Offset, CenterIndex in enumerate(PeakIndexes):
        PreviousCenter = PeakIndexes[Offset - 1] if Offset > 0 else None
        NextCenter = PeakIndexes[Offset + 1] if Offset + 1 < len(PeakIndexes) else None

        LeftCap = max(0, CenterIndex - MaxCurvePoints)
        RightCap = min(len(Smoothed) - 1, CenterIndex + MaxCurvePoints)
        if PreviousCenter is not None:
            LeftCap = max(LeftCap, int((PreviousCenter + CenterIndex) // 2))
        if NextCenter is not None:
            RightCap = min(RightCap, int((CenterIndex + NextCenter) // 2))
        if LeftCap >= CenterIndex or RightCap <= CenterIndex:
            continue

        LeftIndex = LeftCap + int(Np.argmax(Smoothed[LeftCap:CenterIndex + 1]))
        RightIndex = CenterIndex + int(Np.argmax(Smoothed[CenterIndex:RightCap + 1]))
        if LeftIndex >= CenterIndex or RightIndex <= CenterIndex:
            continue

        Duration = float(Time[RightIndex] - Time[LeftIndex])
        if Duration < MinWidthTime or Duration > MaxCurveTime:
            continue

        LeftShoulder = float(Smoothed[LeftIndex])
        RightShoulder = float(Smoothed[RightIndex])
        Trough = float(Smoothed[CenterIndex])
        Depth = min(LeftShoulder, RightShoulder) - Trough
        if Depth < MinProminence:
            continue

        BoxLevel = Trough + Depth * 0.85
        BoxLeft = CenterIndex
        while BoxLeft > LeftIndex and Smoothed[BoxLeft] < BoxLevel:
            BoxLeft -= 1
        BoxRight = CenterIndex
        while BoxRight < RightIndex and Smoothed[BoxRight] < BoxLevel:
            BoxRight += 1

        LeftIndex = BoxLeft
        RightIndex = BoxRight
        Duration = float(Time[RightIndex] - Time[LeftIndex])
        if Duration < MinWidthTime or Duration > MaxCurveTime:
            continue

        Segment = Smoothed[LeftIndex:RightIndex + 1]
        if Segment.size < 3:
            continue

        ShapeProminence = max(RobustNoise * 0.8 * Strictness, Depth * 0.28)
        InnerDistance = max(3, SmoothWidth // 3)
        InnerPeaks, _ = FindPeaks(Segment, prominence=ShapeProminence, distance=InnerDistance)
        InnerTroughs, _ = FindPeaks(-Segment, prominence=ShapeProminence, distance=InnerDistance)
        CenterRelative = CenterIndex - LeftIndex
        ExtraTroughs = [
            TroughIndex
            for TroughIndex in InnerTroughs
            if abs(int(TroughIndex) - CenterRelative) > InnerDistance
        ]
        if len(InnerPeaks) > 1 or len(ExtraTroughs) > 1:
            continue

        FluxMin = float(Np.min(Segment))
        FluxMax = float(Np.max(Segment))
        Transits.append({
            "start": float(Time[LeftIndex]),
            "end": float(Time[RightIndex]),
            "center": float(Time[CenterIndex]),
            "duration": float(Duration),
            "depth": max(float(Depth), ProminenceByIndex.get(int(CenterIndex), float(Depth))),
            "points": int(RightIndex - LeftIndex + 1),
            "flux_min": FluxMin,
            "flux_max": FluxMax,
        })

    return {
        "transits": PruneOverlappingTransits(Transits),
        "robust_noise": RobustNoise,
        "smooth_points": SmoothWidth,
    }


#MARK: dip funcs
def DetectTransitsByThreshold(Time, Flux, MedianFlux, Options):
    ClippedLow, ClippedHigh = RobustFluxLimits(Flux, Sigma=3.0)
    ClippedFlux = Np.clip(Flux, ClippedLow, ClippedHigh)

    Strictness = float(Options["strictness"])
    Smoothing = float(Options["smoothing"])
    BaseSmoothWidth = int(max(31, min(101, len(ClippedFlux) // 700)))
    SmoothWidth = OddWindowWidth(BaseSmoothWidth, Smoothing, 7, 501)
    Smoothed = MovingAverageBySegments(ClippedFlux, SmoothWidth, ObservingSegments(Time))

    Baseline = float(Np.median(Smoothed))
    Mad = float(Np.median(Np.abs(Smoothed - Baseline)))
    RobustNoise = max(1.4826 * Mad, 1e-9)

    DipSigma = 2.4 * Strictness
    AutoMinDepth = max(DipSigma * RobustNoise, abs(MedianFlux) * 0.002 * Strictness)
    MinDepth = (
        float(Options["min_depth"])
        if Options["min_depth"] is not None
        else AutoMinDepth
    )
    DipThreshold = MinDepth if Options["min_depth"] is not None else DipSigma * RobustNoise
    CandidateMask = Smoothed < (Baseline - DipThreshold)
    Regions = MergeRegions(ContiguousRegions(CandidateMask), MaxGap=max(2, SmoothWidth // 2))

    Transits = []
    Cadence = float(Np.median(Np.diff(Time))) if len(Time) > 1 else 1.0
    FullSpan = float(Time[-1] - Time[0]) if len(Time) > 1 else 0.0
    AutoMinPoints = max(5, SmoothWidth // 4)
    AutoMaxPoints = max(SmoothWidth * 5, min(len(Time), int(len(Time) * 0.05)))
    MinPoints = (
        max(3, int(float(Options["min_duration"]) / max(Cadence, 1e-9)))
        if Options["min_duration"] is not None
        else AutoMinPoints
    )
    MaxPoints = (
        max(MinPoints + 1, int(float(Options["max_duration"]) / max(Cadence, 1e-9)))
        if Options["max_duration"] is not None
        else AutoMaxPoints
    )
    for StartIndex, EndIndex in Regions:
        if EndIndex - StartIndex < MinPoints:
            continue
        if EndIndex - StartIndex > MaxPoints:
            continue
        Segment = Smoothed[StartIndex:EndIndex]
        LocalMin = float(Np.min(Segment))
        Depth = Baseline - LocalMin
        if Depth < MinDepth:
            continue

        EdgeLevel = Baseline - max(RobustNoise * 0.55, Depth * 0.28)
        Left = StartIndex
        while Left > 0 and Smoothed[Left - 1] < EdgeLevel:
            Left -= 1
        Right = EndIndex
        while Right < len(Smoothed) and Smoothed[Right] < EdgeLevel:
            Right += 1

        Duration = float(Time[Right - 1] - Time[Left]) if Right > Left else 0.0
        if Duration <= 0:
            continue
        if Options["min_duration"] is not None and Duration < float(Options["min_duration"]):
            continue
        if Options["max_duration"] is not None and Duration > float(Options["max_duration"]):
            continue
        if FullSpan > 0 and Duration > 0.15 * FullSpan:
            continue

        CenterIndex = Left + int(Np.argmin(Smoothed[Left:Right]))
        BoxSegment = Smoothed[Left:Right]
        Transits.append({
            "start": float(Time[Left]),
            "end": float(Time[Right - 1]),
            "center": float(Time[CenterIndex]),
            "duration": Duration,
            "depth": float(Depth),
            "points": int(Right - Left),
            "flux_min": float(Np.min(BoxSegment)),
            "flux_max": float(Np.max(BoxSegment)),
        })

    return {
        "transits": PruneOverlappingTransits(Transits),
        "robust_noise": RobustNoise,
        "smooth_points": SmoothWidth,
    }


#MARK: run the search
def DetectTransits(Time, Flux, Options=None, ProgressCallback=None):
    if Options is None:
        Options = dict(DEFAULT_DETECTION_OPTIONS)
    MedianFlux = float(Np.median(Flux))
    SearchMode = Options.get("search_mode", DEFAULT_DETECTION_OPTIONS["search_mode"])
    if SearchMode == "tls":
        FluxMad = float(Np.median(Np.abs(Flux - MedianFlux)))
        Detection = {
            "transits": [],
            "robust_noise": max(1.4826 * FluxMad, 1e-9),
            "smooth_points": 1,
        }
    else:
        Detection = DetectTransitsByProminence(Time, Flux, MedianFlux, Options)
        ThresholdDetection = DetectTransitsByThreshold(Time, Flux, MedianFlux, Options)
        if Detection is None:
            Detection = ThresholdDetection
        elif ThresholdDetection is not None and len(ThresholdDetection["transits"]) > len(Detection["transits"]):
            Detection = {
                **Detection,
                "transits": PruneOverlappingTransits(Detection["transits"] + ThresholdDetection["transits"]),
                "robust_noise": min(float(Detection["robust_noise"]), float(ThresholdDetection["robust_noise"])),
                "smooth_points": min(int(Detection["smooth_points"]), int(ThresholdDetection["smooth_points"])),
            }

    Transits = sorted(Detection["transits"], key=lambda Item: Item["center"])
    FullSpan = float(Time[-1] - Time[0]) if len(Time) > 1 else 0.0
    TlsPeriod = EstimatePeriodWithTls(Time, Flux, Options, ProgressCallback=ProgressCallback) if SearchMode == "tls" else None
    if TlsPeriod is not None:
        TlsTransits = TransitsFromTlsResult(Time, Flux, TlsPeriod)
        if TlsTransits:
            Transits = TlsTransits
        BlsPeriod = None
        RegularityPeriod = None
        UseRegularityPeriod = False
    else:
        BlsPeriod = EstimatePeriodWithBls(Time, Flux, Options)
        BlsPeriod = DealiasedBlsPeriod(BlsPeriod, Transits, Time, Flux)
        RegularityPeriod = EstimatePeriodByTransitRegularity(Transits, Time, Options, BlsPeriod)
        UseRegularityPeriod = ShouldPreferRegularityPeriod(RegularityPeriod, BlsPeriod, Transits, Time)
    PValue = None
    ChiSquaredFlat = None
    ChiSquaredBox = None
    ReducedChiSquaredBox = None
    DeltaChiSquared = None
    PeriodEpoch = None
    PeriodDuration = None
    PeriodSde = None
    PeriodUncertainty = None
    PeriodCandidates = []
    PeriodSearch = None
    Periodogram = None
    TlsSdeRaw = None
    TlsFap = None
    TlsSnr = None
    TlsDetails = None
    TransitModel = None
    if TlsPeriod is not None:
        Period = TlsPeriod["period"]
        PeriodScatter = TlsPeriod["scatter"]
        PeriodUncertainty = TlsPeriod.get("period_uncertainty")
        PeriodMatchCount = TlsPeriod["count"]
        PeriodMethod = TlsPeriod["method"]
        PValue = TlsPeriod.get("p_value")
        ChiSquaredFlat = TlsPeriod.get("chi_squared_flat")
        ChiSquaredBox = TlsPeriod.get("chi_squared_box")
        ReducedChiSquaredBox = TlsPeriod.get("reduced_chi_squared_box")
        DeltaChiSquared = TlsPeriod.get("delta_chi_squared")
        PeriodEpoch = TlsPeriod.get("transit_time")
        PeriodDuration = TlsPeriod.get("duration")
        PeriodSde = TlsPeriod.get("sde")
        TlsSdeRaw = TlsPeriod.get("sde_raw")
        TlsFap = TlsPeriod.get("fap")
        TlsSnr = TlsPeriod.get("snr")
        PeriodCandidates = TlsPeriod.get("candidates", [])
        Periodogram = TlsPeriod.get("periodogram")
        PeriodSearch = {
            "min_period": TlsPeriod.get("search_min_period"),
            "max_period": TlsPeriod.get("search_max_period"),
            "min_duration": TlsPeriod.get("search_min_duration"),
            "max_duration": TlsPeriod.get("search_max_duration"),
        }
        TlsResult = TlsPeriod.get("tls_result") or {}
        TlsDetails = {
            Key: Value
            for Key, Value in TlsResult.items()
            if Key not in ("candidates", "periodogram", "model")
        }
        TransitModel = TlsPeriod.get("transit_model")
    elif BlsPeriod is not None and not UseRegularityPeriod:
        Periodogram = BlsPeriod.get("periodogram")
        Period = BlsPeriod["period"]
        PeriodScatter = BlsPeriod["scatter"]
        PeriodMatchCount = BlsPeriod["count"]
        PeriodMethod = BlsPeriod["method"]
        PValue = BlsPeriod.get("p_value")
        ChiSquaredFlat = BlsPeriod.get("chi_squared_flat")
        ChiSquaredBox = BlsPeriod.get("chi_squared_box")
        ReducedChiSquaredBox = BlsPeriod.get("reduced_chi_squared_box")
        DeltaChiSquared = BlsPeriod.get("delta_chi_squared")
        PeriodEpoch = BlsPeriod.get("transit_time")
        PeriodDuration = BlsPeriod.get("duration")
        PeriodSde = BlsPeriod.get("sde")
        PeriodCandidates = BlsPeriod.get("candidates", [])
        if RegularityPeriod is not None:
            PeriodCandidates = [
                {
                    "period": RegularityPeriod["period"],
                    "power": RegularityPeriod["event_match_count"],
                    "sde": None,
                    "method": RegularityPeriod["method"],
                    "event_match_count": RegularityPeriod["event_match_count"],
                    "expected_transit_count": RegularityPeriod["expected_count"],
                    "expected_transit_coverage": RegularityPeriod["expected_coverage"],
                },
                *PeriodCandidates,
            ]
        PeriodSearch = {
            "min_period": BlsPeriod.get("search_min_period"),
            "max_period": BlsPeriod.get("search_max_period"),
            "min_duration": BlsPeriod.get("search_min_duration"),
            "max_duration": BlsPeriod.get("search_max_duration"),
        }
    elif RegularityPeriod is not None:
        Period = RegularityPeriod["period"]
        PeriodScatter = RegularityPeriod["scatter"]
        PeriodMatchCount = RegularityPeriod["count"]
        PeriodMethod = RegularityPeriod["method"]
        PeriodEpoch = RegularityPeriod["transit_time"]
        PeriodDuration = RegularityPeriod["duration"]
        PeriodCandidates = [
            {
                "period": RegularityPeriod["period"],
                "power": RegularityPeriod["event_match_count"],
                "sde": None,
                "method": RegularityPeriod["method"],
                "event_match_count": RegularityPeriod["event_match_count"],
                "expected_transit_count": RegularityPeriod["expected_count"],
                "expected_transit_coverage": RegularityPeriod["expected_coverage"],
            },
            *(BlsPeriod.get("candidates", []) if BlsPeriod is not None else []),
        ]
        if BlsPeriod is not None:
            Periodogram = BlsPeriod.get("periodogram")
            PeriodSearch = {
                "min_period": BlsPeriod.get("search_min_period"),
                "max_period": BlsPeriod.get("search_max_period"),
                "min_duration": BlsPeriod.get("search_min_duration"),
                "max_duration": BlsPeriod.get("search_max_duration"),
            }
        FlattenedFlux = FlattenedFluxForPeriodSearch(Time, Flux)
        ChiSquared = None if FlattenedFlux is None else ChiSquaredTransitProbability(
            Time,
            FlattenedFlux,
            Period,
            PeriodDuration,
            PeriodEpoch,
        )
        if ChiSquared:
            PValue = ChiSquared.get("p_value")
            ChiSquaredFlat = ChiSquared.get("chi_squared_flat")
            ChiSquaredBox = ChiSquared.get("chi_squared_box")
            ReducedChiSquaredBox = ChiSquared.get("reduced_chi_squared_box")
            DeltaChiSquared = ChiSquared.get("delta_chi_squared")
    else:
        Period, PeriodScatter, PeriodMatchCount = EstimatePeriodFromCandidates(Transits, FullSpan)
        PeriodMethod = "average gaps" if Period is not None else None
        if Period is not None and Transits:
            PeriodEpoch = float(Transits[0]["center"])
            PeriodDuration = float(Np.median([Item["duration"] for Item in Transits]))
    return {
        "transits": Transits,
        "period": Period,
        "period_scatter": PeriodScatter,
        "period_match_count": PeriodMatchCount,
        "period_method": PeriodMethod,
        "period_epoch": PeriodEpoch,
        "period_duration": PeriodDuration,
        "period_sde": PeriodSde,
        "period_uncertainty": PeriodUncertainty,
        "period_candidates": PeriodCandidates,
        "period_search": PeriodSearch,
        "periodogram": Periodogram,
        "tls_sde_raw": TlsSdeRaw,
        "tls_fap": TlsFap,
        "tls_snr": TlsSnr,
        "tls": TlsDetails,
        "transit_model": TransitModel,
        "p_value": PValue,
        "p_value_percent": None if PValue is None else PValue * 100.0,
        "chi_squared_flat": ChiSquaredFlat,
        "chi_squared_box": ChiSquaredBox,
        "reduced_chi_squared_box": ReducedChiSquaredBox,
        "delta_chi_squared": DeltaChiSquared,
        "median_flux": MedianFlux,
        "robust_noise": float(Detection["robust_noise"]),
        "smooth_points": int(Detection["smooth_points"]),
        "detection_options": Options,
    }


#MARK: check the results
def AddDepthMetrics(Transit, BaselineFlux):
    Depth = Transit.get("depth")
    if (
        Depth is None
        or not Math.isfinite(float(Depth))
        or float(Depth) < 0
    ):
        Transit["depth_fraction"] = None
        Transit["depth_percent"] = None
        Transit["depth_ppm"] = None
        Transit["radius_ratio"] = None
        Transit["depth_basis"] = None
        return Transit

    NormalizedFraction = None
    if (
        BaselineFlux is not None
        and Math.isfinite(float(BaselineFlux))
        and float(BaselineFlux) > 0
    ):
        NormalizedFraction = float(Depth) / float(BaselineFlux)

    UseNormalizedFlux = NormalizedFraction is not None and NormalizedFraction <= 0.5
    DepthFraction = NormalizedFraction if UseNormalizedFlux else float(Depth) / 1000000.0
    Transit["depth_fraction"] = DepthFraction
    Transit["depth_percent"] = DepthFraction * 100.0
    Transit["depth_ppm"] = DepthFraction * 1000000.0
    Transit["radius_ratio"] = Math.sqrt(DepthFraction)
    Transit["depth_basis"] = "fractional flux" if UseNormalizedFlux else "ppm flux"
    return Transit


#MARK: finite values
def FiniteValues(Values):
    return [float(Value) for Value in Values if Value is not None and Math.isfinite(float(Value))]


#MARK: finite number
def FiniteNumber(Value):
    if Value is None or isinstance(Value, (bool, Np.bool_)):
        return None
    try:
        Number = float(Value)
    except (TypeError, ValueError):
        return None
    return Number if Math.isfinite(Number) else None


#MARK: format metric
def FormatMetric(Value, Digits=2):
    Number = FiniteNumber(Value)
    return "-" if Number is None else f"{Number:.{Digits}f}"


#MARK: median or none
def MedianOrNone(Values):
    Clean = sorted(FiniteValues(Values))
    if not Clean:
        return None
    Middle = len(Clean) // 2
    if len(Clean) % 2:
        return Clean[Middle]
    return (Clean[Middle - 1] + Clean[Middle]) / 2.0


#MARK: coefficient of variation
def CoefficientOfVariation(Values):
    Clean = FiniteValues(Values)
    Center = MedianOrNone(Clean)
    if Center is None or Center <= 0 or len(Clean) < 2:
        return None
    return float(Np.std(Np.asarray(Clean, dtype=float)) / Center)


#MARK: normalize observed ranges
def NormalizeObservedRanges(ObservedRanges):
    Ranges = []
    for Item in ObservedRanges or []:
        if isinstance(Item, dict):
            Start = FiniteNumber(Item.get("start_day", Item.get("start")))
            End = FiniteNumber(Item.get("end_day", Item.get("end")))
        else:
            try:
                Start = FiniteNumber(Item[0])
                End = FiniteNumber(Item[1])
            except (TypeError, IndexError):
                Start = None
                End = None
        if Start is None or End is None:
            continue
        if End < Start:
            Start, End = End, Start
        Ranges.append((float(Start), float(End)))
    return Ranges


#MARK: event timing
def EphemerisCyclesInObservedRanges(Period, Epoch, Tolerance, ObservedRanges):
    Period = FiniteNumber(Period)
    Epoch = FiniteNumber(Epoch)
    Tolerance = FiniteNumber(Tolerance)
    if Period is None or Epoch is None or Tolerance is None or Period <= 0:
        return set()

    Cycles = set()
    for Start, End in NormalizeObservedRanges(ObservedRanges):
        FirstCycle = Math.ceil((Start - Tolerance - Epoch) / Period)
        LastCycle = Math.floor((End + Tolerance - Epoch) / Period)
        if LastCycle < FirstCycle:
            continue
        Cycles.update(range(int(FirstCycle), int(LastCycle) + 1))
    return Cycles


#MARK: event timing
def BuildEphemerisDiagnostics(Transits, Detection, TimeReference=0.0, ObservedRanges=None):
    Period = FiniteNumber(Detection.get("period"))
    Epoch = FiniteNumber(Detection.get("period_epoch"))
    PeriodDuration = FiniteNumber(Detection.get("period_duration"))
    ExpectedCount = FiniteNumber(Detection.get("period_match_count"))
    IndependentTiming = Detection.get("period_method") == "TLS"
    Centers = FiniteValues([
        Item.get("measured_center") if IndependentTiming else Item.get("center")
        for Item in Transits
        if not IndependentTiming or Item.get("state") == "supported_dip"
    ])
    Durations = FiniteValues([Item.get("duration") for Item in Transits])

    Empty = {
        "ephemeris_match_count": None,
        "ephemeris_match_fraction": None,
        "ephemeris_event_match_count": None,
        "ephemeris_event_match_fraction": None,
        "off_ephemeris_transit_count": None,
        "off_ephemeris_fraction": None,
        "expected_transit_count": ExpectedCount,
        "expected_transit_coverage": None,
        "timing_residual_median": None,
        "timing_residual_max": None,
        "timing_residual_tolerance": None,
        "timing_residual_ratio": None,
        "timing_basis": "independently measured local centroids" if IndependentTiming else "detected event centers",
        "measured_timing_count": len(Centers),
        "predicted_window_count": len(Transits),
        "covered_window_count": sum(Item.get("state") in ("supported_dip", "unsupported_window") for Item in Transits) if IndependentTiming else len(Transits),
    }
    if not Centers or Period is None or Epoch is None or Period <= 0:
        return Empty

    EpochRelative = Epoch - float(TimeReference)
    MedianDuration = MedianOrNone(Durations)
    DurationScale = max(
        PeriodDuration or 0.0,
        MedianDuration or 0.0,
        Period * 0.035,
    )
    Tolerance = max(DurationScale * 1.5, Period * 0.025)
    Tolerance = min(Tolerance, Period * 0.18)
    if Tolerance <= 0:
        return Empty

    Residuals = []
    MatchedResiduals = []
    MatchedCycles = set()
    for Center in Centers:
        Cycles = round((Center - EpochRelative) / Period)
        NearestEpoch = EpochRelative + Cycles * Period
        Residual = abs(Center - NearestEpoch)
        Residuals.append(Residual)
        if Residual <= Tolerance:
            MatchedResiduals.append(Residual)
            MatchedCycles.add(int(Cycles))

    MatchCount = len(MatchedResiduals)
    EventMatchCount = len(MatchedCycles)
    TransitCount = len(Centers)
    OffCount = TransitCount - MatchCount
    MedianResidual = MedianOrNone(Residuals)
    ObservedCycles = EphemerisCyclesInObservedRanges(Period, EpochRelative, Tolerance, ObservedRanges)
    if IndependentTiming:
        ExpectedCount = sum(Item.get("state") in ("supported_dip", "unsupported_window") for Item in Transits)
    elif ObservedCycles:
        ExpectedCount = len(ObservedCycles)
    ExpectedCoverage = None
    if ExpectedCount is not None and ExpectedCount > 0:
        ExpectedCoverage = min(1.0, EventMatchCount / ExpectedCount)

    return {
        **Empty,
        "ephemeris_match_count": int(MatchCount),
        "ephemeris_match_fraction": MatchCount / TransitCount,
        "ephemeris_event_match_count": int(EventMatchCount),
        "ephemeris_event_match_fraction": None if ExpectedCount is None or ExpectedCount <= 0 else EventMatchCount / ExpectedCount,
        "off_ephemeris_transit_count": int(OffCount),
        "off_ephemeris_fraction": OffCount / TransitCount,
        "expected_transit_count": int(ExpectedCount) if ExpectedCount is not None else None,
        "expected_transit_coverage": ExpectedCoverage,
        "timing_residual_median": MedianResidual,
        "timing_residual_max": max(Residuals) if Residuals else None,
        "timing_residual_tolerance": Tolerance,
        "timing_residual_ratio": None if MedianResidual is None else MedianResidual / Tolerance,
    }


#MARK: transit checks
def BuildCandidateDiagnostics(Transits, Detection, TimeReference=0.0, ObservedRanges=None):
    HasWindowStates = any("state" in Item for Item in Transits)
    EvidenceEvents = [Item for Item in Transits if not HasWindowStates or Item.get("state") == "supported_dip"]
    Depths = FiniteValues([Item.get("depth") for Item in EvidenceEvents])
    RadiusRatios = FiniteValues([Item.get("radius_ratio") for Item in EvidenceEvents])
    PointCounts = FiniteValues([Item.get("points") for Item in EvidenceEvents])
    #MARK: transit checks
    # a missing event shouldn't flip which cycle is odd.
    Epoch = FiniteNumber(Detection.get("period_epoch"))
    Period = FiniteNumber(Detection.get("period"))
    def Parity(Item, Index):
        if Item.get("cycle_number") is not None:
            return int(Item["cycle_number"]) % 2
        if Epoch is not None and Period and Period > 0:
            return int(round((Item["center"] + TimeReference - Epoch) / Period)) % 2
        return Index % 2
    OddDepths = FiniteValues([Item.get("depth") for I, Item in enumerate(EvidenceEvents) if Parity(Item, I) == 1])
    EvenDepths = FiniteValues([Item.get("depth") for I, Item in enumerate(EvidenceEvents) if Parity(Item, I) == 0])
    OddDepth = MedianOrNone(OddDepths)
    EvenDepth = MedianOrNone(EvenDepths)
    DepthCenter = MedianOrNone(Depths)
    RobustNoise = Detection.get("robust_noise")
    LocalDepthSnr = None
    if DepthCenter is not None and RobustNoise is not None and Math.isfinite(float(RobustNoise)) and float(RobustNoise) > 0:
        LocalDepthSnr = DepthCenter / float(RobustNoise)
    TlsSnr = FiniteNumber(Detection.get("tls_snr"))
    DetectionSnr = TlsSnr if Detection.get("period_method") == "TLS" and TlsSnr is not None else LocalDepthSnr
    TlsDetails = Detection.get("tls") or {}
    TlsOddEvenMismatch = FiniteNumber(TlsDetails.get("odd_even_mismatch_sigma"))

    OddEvenDepthMismatch = None
    if OddDepth is not None and EvenDepth is not None and max(OddDepth, EvenDepth) > 0:
        OddEvenDepthMismatch = abs(OddDepth - EvenDepth) / max(OddDepth, EvenDepth)

    Ephemeris = BuildEphemerisDiagnostics(Transits, Detection, TimeReference, ObservedRanges)
    #MARK: dip funcs
    # keep signed depths: a weak dip can help without being a detection by itself.
    UsableWindows = [Item for Item in Transits
                      if Item.get("state") in ("supported_dip", "unsupported_window")
                      and FiniteNumber(Item.get("depth")) is not None
                      and FiniteNumber(Item.get("depth_uncertainty")) is not None
                      and Item["depth_uncertainty"] > 0]
    CombinedDepth = CombinedError = CombinedSnr = None
    if UsableWindows:
        Signed = Np.asarray([Item["depth"] for Item in UsableWindows])
        Errors = Np.asarray([Item["depth_uncertainty"] for Item in UsableWindows])
        Weights = 1.0 / Errors ** 2
        # per-event errors estimated from very few samples can be spuriously
        # small. cap their relative precision rather than allowing one shallow
        # window to dominate the collective signal.
        Weights = Np.minimum(Weights, Np.median(Weights) * 2.0)
        CombinedDepth = float(Np.average(Signed, weights=Weights))
        FormalError = float(1.0 / Math.sqrt(Np.sum(Weights)))
        EmpiricalError = float(Np.std(Signed, ddof=1) / Math.sqrt(len(Signed))) if len(Signed) > 1 else FormalError
        CombinedError = max(FormalError, EmpiricalError)
        CombinedSnr = CombinedDepth / CombinedError if CombinedError > 0 else None
    PositiveWindows = sum(Item["depth"] > 0 for Item in UsableWindows)
    CombinedSupport = (len(UsableWindows) >= 3 and PositiveWindows >= 3
                        and PositiveWindows / len(UsableWindows) >= 0.6
                        and CombinedSnr is not None and CombinedSnr >= 3.0
                        and Detection.get("period_method") == "TLS"
                        and (FiniteNumber(Detection.get("period_sde")) or 0) >= 7.0
                        and (TlsSnr or 0) >= 5.0)
    Diagnostics = {
        "detection_snr": DetectionSnr,
        "local_depth_snr": LocalDepthSnr,
        "tls_snr": TlsSnr,
        "tls_fap": FiniteNumber(Detection.get("tls_fap")),
        "tls_odd_even_mismatch_sigma": TlsOddEvenMismatch,
        "median_transit_points": MedianOrNone(PointCounts),
        "depth_scatter_ratio": CoefficientOfVariation(Depths),
        "odd_depth": OddDepth,
        "even_depth": EvenDepth,
        "odd_even_depth_mismatch": OddEvenDepthMismatch,
        "max_radius_ratio": max(RadiusRatios) if RadiusRatios else None,
        "supported_event_count": len(EvidenceEvents),
        "combined_window_count": len(UsableWindows),
        "positive_window_count": PositiveWindows,
        "combined_signed_depth": CombinedDepth,
        "combined_depth_uncertainty": CombinedError,
        "combined_depth_snr": CombinedSnr,
        "combined_signal_supported": bool(CombinedSupport),
        "predicted_window_count": len(Transits),
        "unsupported_window_count": sum(Item.get("state") == "unsupported_window" for Item in Transits),
        "insufficient_coverage_count": sum(Item.get("state") == "insufficient_coverage" for Item in Transits),
        "outside_observations_count": sum(Item.get("state") == "outside_observations" for Item in Transits),
        "odd_event_count": len(OddDepths), "even_event_count": len(EvenDepths),
        **Ephemeris,
    }

    #MARK: things worth checking
    Warnings = []
    if not Transits:
        Warnings.append({
            "severity": "caution",
            "title": "No transit candidates",
            "detail": "Try lowering strictness or checking the input columns and flux units.",
        })
    if 0 < len(Transits) < 3:
        Warnings.append({
            "severity": "caution",
            "title": "Few observed transits",
            "detail": "A single event or pair of events is harder to separate from systematics.",
        })
    if Detection.get("period") is None:
        Warnings.append({
            "severity": "caution",
            "title": "No stable period",
            "detail": "The app could not estimate a repeating orbital period.",
        })
    if Detection.get("period_method") and Detection.get("period_method") != "BLS":
        if Detection.get("period_method") == "TLS":
            Warnings.append({
                "severity": "info",
                "title": "Physical TLS search",
                "detail": "The period was fitted with a limb-darkened transit template including ingress and egress.",
            })
        elif Detection.get("period_method") == "transit regularity":
            Warnings.append({
                "severity": "info",
                "title": "Period selected by regularity",
                "detail": "A shorter repeating transit-box cadence explained more detected events than the strongest BLS alias.",
            })
        else:
            Warnings.append({
                "severity": "info",
                "title": "Period is provisional",
                "detail": f"Period came from {Detection.get('period_method')}, not a BLS peak.",
            })
    PValue = Detection.get("p_value")
    if PValue is not None and Math.isfinite(float(PValue)) and float(PValue) > 0.01:
        Warnings.append({
            "severity": "caution",
            "title": "Weak model significance",
            "detail": "The box model is not much better than a flat light curve by the current chi-squared estimate.",
        })
    TlsFap = FiniteNumber(Detection.get("tls_fap"))
    TlsSde = FiniteNumber(Detection.get("period_sde"))
    if Detection.get("period_method") == "TLS" and TlsSde is not None and TlsSde < 5:
        Warnings.append({
            "severity": "caution",
            "title": "TLS peak below candidate threshold",
            "detail": f"TLS SDE is {TlsSde:.2f}; candidate review normally starts around SDE 5 and strong evidence around SDE 7.",
        })
    if Detection.get("period_method") == "TLS" and TlsFap is not None and TlsFap > 0.01:
        Warnings.append({
            "severity": "caution",
            "title": "Weak TLS false-alarm estimate",
            "detail": f"TLS reports a white-noise false-alarm probability of about {TlsFap:.2%}; red noise can make this optimistic.",
        })
    if DetectionSnr is not None and DetectionSnr < 7:
        Warnings.append({
            "severity": "caution",
            "title": "Low search SNR" if Detection.get("period_method") == "TLS" else "Low depth SNR",
            "detail": (
                f"TLS reports a combined transit SNR of {DetectionSnr:.2f}."
                if Detection.get("period_method") == "TLS"
                else f"Median transit depth is about {DetectionSnr:.2f}x the robust noise."
            ),
        })
    if TlsOddEvenMismatch is not None and TlsOddEvenMismatch >= 5:
        Warnings.append({
            "severity": "danger",
            "title": "TLS odd/even mismatch",
            "detail": f"TLS measures an odd/even depth difference of {TlsOddEvenMismatch:.2f} sigma.",
        })
    if OddEvenDepthMismatch is not None and OddEvenDepthMismatch > 0.5 and len(OddDepths) >= 2 and len(EvenDepths) >= 2:
        Warnings.append({
            "severity": "danger",
            "title": "Odd/even depth mismatch",
            "detail": "Alternating transit depths can indicate an eclipsing binary or blended source.",
        })
    DepthUncertainties = FiniteValues([Item.get("depth_uncertainty") for Item in EvidenceEvents])
    InconsistentThree = (len(Depths) >= 3 and len(DepthUncertainties) == len(Depths)
                          and max(Depths) - min(Depths) > 3 * Math.hypot(max(DepthUncertainties), min(DepthUncertainties)))
    if Diagnostics["depth_scatter_ratio"] is not None and Diagnostics["depth_scatter_ratio"] > 0.8 and (len(Depths) >= 4 or InconsistentThree):
        Warnings.append({
            "severity": "caution",
            "title": "Inconsistent transit depths",
            "detail": "Measured event depths disagree beyond their local uncertainty estimates. Review stellar variability, overlap, and systematics.",
        })
    if HasWindowStates and len(EvidenceEvents) < min(3, len(Transits)):
        Warnings.append({"severity": "caution", "title": "Predicted windows lack local support",
                         "detail": f"Only {len(EvidenceEvents)} of {len(Transits)} predicted windows have a positive local dip above 3-sigma with usable coverage."})
    if len(OddDepths) < 2 or len(EvenDepths) < 2:
        Diagnostics["odd_even_comparison_state"] = "insufficient_events"
    else:
        Diagnostics["odd_even_comparison_state"] = "available"
    DurationDisagreement = FiniteNumber(TlsDetails.get("duration_disagreement_fraction"))
    if DurationDisagreement is not None and DurationDisagreement > 0.35:
        Warnings.append({"severity": "caution", "title": "Duration estimates disagree",
                         "detail": "Threshold-based width and physical template contacts differ by more than 35%; inspect the conditional fit and cadence."})
    SearchBounds = Detection.get("period_search") or {}
    SelectedPeriod = FiniteNumber(Detection.get("period"))
    Minimum = FiniteNumber(SearchBounds.get("min_period"))
    Maximum = FiniteNumber(SearchBounds.get("max_period"))
    if SelectedPeriod is not None and Minimum is not None and Maximum is not None:
        # a remote upper bound must not make an interior short-period peak
        # appear to lie on the lower edge of a very broad search.
        PeriodUncertainty = FiniteNumber(Detection.get("period_uncertainty")) or 0.0
        EdgeMargin = max(SelectedPeriod * 0.002, PeriodUncertainty * 3.0)
        if min(abs(SelectedPeriod - Minimum), abs(Maximum - SelectedPeriod)) < EdgeMargin:
            Warnings.append({"severity": "caution", "title": "Period peak near search edge",
                             "detail": "The selected period is close to a search bound. Widen the bounds when baseline and minimum-transit constraints permit."})
    StrongAlternatives = [Candidate for Candidate in Detection.get("period_candidates", [])
                           if SelectedPeriod and FiniteNumber(Candidate.get("period"))
                           and abs(Candidate["period"] - SelectedPeriod) / SelectedPeriod > 0.02
                           and FiniteNumber(Candidate.get("sde")) is not None
                           and Candidate["sde"] >= max(7.0, (FiniteNumber(Detection.get("period_sde")) or 0) * 0.85)]
    if StrongAlternatives:
        Diagnostics["strong_alias_periods"] = [Candidate["period"] for Candidate in StrongAlternatives[:4]]
        Warnings.append({"severity": "caution", "title": "Strong alternative periods",
                         "detail": "Other distinct period peaks have comparable strength. Inspect harmonics, aliases, and additional planets before choosing an ephemeris."})
    if (
        len(Transits) >= 3
        and Detection.get("period_method") in ("BLS", "binned BLS fallback", "transit regularity", "TLS")
        and Diagnostics["ephemeris_match_fraction"] is not None
    ):
        MatchFraction = Diagnostics["ephemeris_match_fraction"]
        MatchCount = Diagnostics["ephemeris_match_count"]
        TransitCount = len(Transits)
        EventCount = Diagnostics["ephemeris_event_match_count"]
        ExpectedCount = Diagnostics["expected_transit_count"]
        ExpectedCoverage = Diagnostics["expected_transit_coverage"]
        WellCoveredEvents = (
            Detection.get("period_method") in ("transit regularity", "TLS")
            and EventCount is not None
            and EventCount >= 3
            and (
                (
                    ExpectedCoverage is not None
                    and ExpectedCoverage >= 0.65
                )
                or IsDenseRegularityMatch(
                    MatchCount,
                    EventCount,
                    ExpectedCoverage,
                    TransitCount,
                )
            )
        )
        PeriodLabel = "BLS period" if Detection.get("period_method") == "BLS" else "selected period"
        if MatchFraction < 0.55 and not WellCoveredEvents:
            Warnings.append({
                "severity": "danger",
                "title": "Irregular transit timing",
                "detail": f"Only {MatchCount} of {TransitCount} detected dips align with the {PeriodLabel}.",
            })
        elif MatchFraction < 0.75 and not WellCoveredEvents:
            Warnings.append({
                "severity": "caution",
                "title": "Weak ephemeris agreement",
                "detail": f"{MatchCount} of {TransitCount} detected dips align with the {PeriodLabel}.",
            })
        if WellCoveredEvents and MatchFraction < 0.65:
            Warnings.append({
                "severity": "caution",
                "title": "Noisy extra dips",
                "detail": f"{int(EventCount)} of {int(ExpectedCount)} predicted events are covered, but extra off-period dips were also boxed.",
            })

        OffCount = Diagnostics["off_ephemeris_transit_count"]
        OffFraction = Diagnostics["off_ephemeris_fraction"]
        if OffCount is not None and OffFraction is not None and OffCount >= 3 and OffFraction >= 0.35:
            if not WellCoveredEvents:
                Warnings.append({
                    "severity": "caution",
                    "title": "Many off-period dips",
                    "detail": "Several detected dips do not land near the recovered period and may be systematics.",
                })
    if Diagnostics["max_radius_ratio"] is not None and Diagnostics["max_radius_ratio"] > 0.2:
        Warnings.append({
            "severity": "caution",
            "title": "Large radius ratio",
            "detail": "Rp/Rs above 0.2 is large for many planet candidates and deserves closer inspection.",
        })
    if Diagnostics["median_transit_points"] is not None and Diagnostics["median_transit_points"] < 4:
        Warnings.append({
            "severity": "info",
            "title": "Sparse transit sampling",
            "detail": "Some events have very few points inside the detected box.",
        })

    return Diagnostics, Warnings


#MARK: transit checks
def ScoreBand(Value, Bands):
    if Value is None:
        return None
    for Threshold, Points, Label, Detail in Bands:
        if Value >= Threshold:
            return Points, Label, Detail
    return None


#MARK: build planet assessment
def BuildPlanetAssessment(Transits, Detection, Diagnostics, Warnings):
    LocalEventCount = int(Diagnostics.get("supported_event_count", len(Transits)))
    CombinedSupport = bool(Diagnostics.get("combined_signal_supported"))
    TransitCount = max(LocalEventCount, int(Diagnostics.get("positive_window_count", 0)) if CombinedSupport else 0)
    Period = FiniteNumber(Detection.get("period"))
    PeriodMethod = Detection.get("period_method")
    PeriodSde = FiniteNumber(Detection.get("period_sde"))
    DetectionSnr = FiniteNumber(Diagnostics.get("detection_snr"))
    TlsFap = FiniteNumber(Detection.get("tls_fap"))
    PValue = FiniteNumber(Detection.get("p_value"))
    DepthScatterRatio = FiniteNumber(Diagnostics.get("depth_scatter_ratio"))
    OddEvenMismatch = FiniteNumber(Diagnostics.get("odd_even_depth_mismatch"))
    MaxRadiusRatio = FiniteNumber(Diagnostics.get("max_radius_ratio"))
    MedianTransitPoints = FiniteNumber(Diagnostics.get("median_transit_points"))
    EphemerisMatchFraction = FiniteNumber(Diagnostics.get("ephemeris_match_fraction"))
    EphemerisMatchCount = FiniteNumber(Diagnostics.get("ephemeris_match_count"))
    EphemerisEventMatchCount = FiniteNumber(Diagnostics.get("ephemeris_event_match_count"))
    OffEphemerisCount = FiniteNumber(Diagnostics.get("off_ephemeris_transit_count"))
    OffEphemerisFraction = FiniteNumber(Diagnostics.get("off_ephemeris_fraction"))
    ExpectedTransitCount = FiniteNumber(Diagnostics.get("expected_transit_count"))
    ExpectedTransitCoverage = FiniteNumber(Diagnostics.get("expected_transit_coverage"))
    TimingResidualRatio = FiniteNumber(Diagnostics.get("timing_residual_ratio"))
    EphemerisPeriodMethods = ("BLS", "binned BLS fallback", "transit regularity", "TLS")
    PeriodLabel = "BLS period" if PeriodMethod == "BLS" else "selected period"
    WellCoveredEphemeris = (
        PeriodMethod in ("transit regularity", "TLS")
        and EphemerisEventMatchCount is not None
        and EphemerisEventMatchCount >= 3
        and (
            (
                ExpectedTransitCoverage is not None
                and ExpectedTransitCoverage >= 0.65
            )
            or IsDenseRegularityMatch(
                EphemerisMatchCount,
                EphemerisEventMatchCount,
                ExpectedTransitCoverage,
                TransitCount,
            )
        )
    )

    #MARK: transit checks
    Score = 0.0
    SupportingEvidence = []
    LimitingEvidence = []

    def Support(Title, Detail, Points):
        nonlocal Score
        Score += Points
        SupportingEvidence.append({
            "title": Title,
            "detail": Detail,
            "points": Points,
        })

    def Limit(Title, Detail, Points):
        nonlocal Score
        Score += Points
        LimitingEvidence.append({
            "title": Title,
            "detail": Detail,
            "points": Points,
        })

    if CombinedSupport and LocalEventCount < 3:
        Support("Coherent combined transit signal", f"{TransitCount} windows have positive signed depth; combined local SNR is {Diagnostics['combined_depth_snr']:.2f}. Individual windows remain tentative unless independently supported.", 20)
    elif TransitCount >= 3:
        Support("Repeated locally supported dips", f"{TransitCount} windows contain positive measured dips with usable coverage.", 20)
    elif TransitCount > 0:
        Support("Locally supported dip", f"{TransitCount} window{'s have' if TransitCount != 1 else ' has'} local transit-like support.", 6)
        Limit("Too few events", "Fewer than three events is weak evidence for an orbital period.", -8)
    else:
        Limit("No boxed transit events", "The detector did not find statistically strong local dips.", -28)

    if Period is not None and Period > 0 and PeriodMethod == "BLS":
        Support("Stable BLS period", f"Best period is {Period:.6g} days from the BLS search.", 22)
    elif Period is not None and Period > 0 and PeriodMethod == "TLS":
        Support("Physical TLS period", f"Best period is {Period:.6g} days from the limb-darkened TLS search.", 22)
    elif Period is not None and Period > 0 and PeriodMethod == "transit regularity":
        Support("Frequent transit regularity", f"Best repeating interval is {Period:.6g} days from the boxed transit cadence.", 20)
    elif Period is not None and Period > 0:
        Support("Provisional period", f"Estimated period is {Period:.6g} days from {PeriodMethod or 'candidate spacing'}.", 10)
        Limit("Period is not a BLS peak", "The repeating period needs manual confirmation.", -4)
    else:
        Limit("No stable period", "A repeating orbital period was not recovered.", -18)

    SdeLabel = "TLS SDE" if PeriodMethod == "TLS" else "Period SDE"
    SdeResult = ScoreBand(PeriodSde, (
        (10.0, 22, "Very strong period peak", f"{SdeLabel} is {FormatMetric(PeriodSde)}."),
        (7.0, 17, "Strong period peak", f"{SdeLabel} is {FormatMetric(PeriodSde)}."),
        (5.0, 8, "Moderate period peak", f"{SdeLabel} is {FormatMetric(PeriodSde)}."),
    ))
    if SdeResult is not None:
        Points, Title, Detail = SdeResult
        Support(Title, Detail, Points)
    elif PeriodSde is not None:
        Limit("Weak period peak", f"{SdeLabel} is only {PeriodSde:.2f}.", -10)

    SnrTitle = "TLS signal SNR" if PeriodMethod == "TLS" else "transit depth SNR"
    SnrResult = ScoreBand(DetectionSnr, (
        (10.0, 22, f"High {SnrTitle}", f"Search SNR is {FormatMetric(DetectionSnr)}."),
        (7.0, 16, f"Good {SnrTitle}", f"Search SNR is {FormatMetric(DetectionSnr)}."),
        (5.0, 8, f"Marginal {SnrTitle}", f"Search SNR is {FormatMetric(DetectionSnr)}."),
    ))
    if SnrResult is not None:
        Points, Title, Detail = SnrResult
        Support(Title, Detail, Points)
    elif DetectionSnr is not None:
        Limit(f"Low {SnrTitle}", f"Search SNR is only {DetectionSnr:.2f}.", -14)

    if PeriodMethod == "TLS" and TlsFap is not None:
        if TlsFap <= 0.001:
            Support("Low TLS false-alarm probability", f"White-noise FAP is {TlsFap:.3%}.", 10)
        elif TlsFap <= 0.01:
            Support("Useful TLS false-alarm estimate", f"White-noise FAP is {TlsFap:.2%}.", 6)
        else:
            Limit("Weak TLS false-alarm estimate", f"White-noise FAP is {TlsFap:.2%}.", -10)

    if PValue is not None:
        if PValue <= 1e-6:
            Support("Very significant box model", "The transit model strongly beats a flat light curve.", 16)
        elif PValue <= 1e-4:
            Support("Significant box model", "The transit model clearly beats a flat light curve.", 12)
        elif PValue <= 0.01:
            Support("Useful box-model improvement", "The transit model improves over a flat light curve.", 8)
        else:
            Limit("Weak box-model significance", "The transit model is not much better than a flat light curve.", -12)

    # tls windows are selected with an ephemeris, so their local centroids are
    # conditional evidence. report timing descriptively but award no circular
    # timing bonus. non-tls dip searches can retain independent timing credit.
    if PeriodMethod != "TLS" and PeriodMethod in EphemerisPeriodMethods and TransitCount >= 3 and EphemerisMatchFraction is not None:
        if EphemerisMatchFraction >= 0.8:
            Support("Detected dips follow the ephemeris", f"{int(EphemerisMatchCount)} of {TransitCount} dips align with the {PeriodLabel}.", 16)
        elif WellCoveredEphemeris:
            Support(
                "Predicted events are covered",
                f"{int(EphemerisEventMatchCount)} of {int(ExpectedTransitCount)} predicted events have matching dips.",
                12,
            )
        elif EphemerisMatchFraction >= 0.65:
            Support("Partial ephemeris agreement", f"{int(EphemerisMatchCount)} of {TransitCount} dips align with the {PeriodLabel}.", 5)
            Limit("Some off-period dips", "Several detected dips do not belong to the recovered period.", -6)
        elif EphemerisMatchFraction < 0.55:
            Limit("Irregular transit timing", f"Only {int(EphemerisMatchCount)} of {TransitCount} dips align with the {PeriodLabel}.", -34)
        else:
            Limit("Weak timing agreement", f"Only {int(EphemerisMatchCount)} of {TransitCount} dips align with the {PeriodLabel}.", -18)

    if (
        OffEphemerisCount is not None
        and OffEphemerisFraction is not None
        and OffEphemerisCount >= 3
        and OffEphemerisFraction >= 0.35
    ):
        if WellCoveredEphemeris:
            Limit("Extra off-period dips", "The selected ephemeris repeats, but extra boxed dips may be noise or systematics.", -6)
        else:
            Limit("Many off-period dips", "The detector found too many transit-like dips away from the recovered ephemeris.", -24)

    if ExpectedTransitCoverage is not None and TransitCount >= 3 and ExpectedTransitCoverage < 0.5:
        Limit("Weak predicted-transit coverage", f"Only {ExpectedTransitCoverage:.0%} of expected {PeriodLabel} events were matched.", -10)

    if TimingResidualRatio is not None and TimingResidualRatio > 1.0 and TransitCount >= 3 and not WellCoveredEphemeris:
        Limit("Large timing residuals", "Detected dip centers are not tightly clustered around the recovered ephemeris.", -10)

    if DepthScatterRatio is not None and TransitCount >= 3:
        if DepthScatterRatio <= 0.35:
            Support("Consistent transit depths", f"Depth scatter ratio is {DepthScatterRatio:.2f}.", 7)
        elif DepthScatterRatio > 0.8:
            Limit("Inconsistent transit depths", f"Depth scatter ratio is {DepthScatterRatio:.2f}.", -12)
        elif DepthScatterRatio > 0.5:
            Limit("Moderately inconsistent depths", f"Depth scatter ratio is {DepthScatterRatio:.2f}.", -6)

    if OddEvenMismatch is not None and Diagnostics.get("odd_even_comparison_state", "available") == "available" and TransitCount >= 4:
        if OddEvenMismatch <= 0.25:
            Support("Odd/even depths agree", f"Odd/even mismatch is {OddEvenMismatch:.2f}.", 6)
        elif OddEvenMismatch > 0.5:
            Limit("Odd/even depth mismatch", "Alternating depths can indicate an eclipsing binary or blend.", -18)
        elif OddEvenMismatch > 0.35:
            Limit("Possible odd/even mismatch", f"Odd/even mismatch is {OddEvenMismatch:.2f}.", -8)

    if MaxRadiusRatio is not None:
        if MaxRadiusRatio <= 0.2:
            Support("Planet-sized radius ratio", f"Maximum Rp/Rs estimate is {MaxRadiusRatio:.3f}.", 4)
        elif MaxRadiusRatio > 0.3:
            Limit("Very large radius ratio", f"Maximum Rp/Rs estimate is {MaxRadiusRatio:.3f}.", -16)
        else:
            Limit("Large radius ratio", f"Maximum Rp/Rs estimate is {MaxRadiusRatio:.3f}.", -8)

    if MedianTransitPoints is not None:
        if MedianTransitPoints >= 8:
            Support("Well-sampled events", f"Median supported event has {MedianTransitPoints:.0f} analysis samples.", 4)
        elif MedianTransitPoints < 4:
            Limit("Sparse transit sampling", f"Median supported event has only {MedianTransitPoints:.0f} analysis samples.", -6)

    DangerCount = sum(1 for Warning in Warnings if Warning.get("severity") == "danger")
    CautionCount = sum(1 for Warning in Warnings if Warning.get("severity") == "caution")
    if DangerCount:
        Score -= DangerCount * 10
    if CautionCount >= 3:
        Score -= 6

    #MARK: transit checks
    RawCandidateScore = int(round(Clamp(Score, 0, 100)))
    RequiredPeriodSde = 7 if PeriodMethod == "TLS" else 5
    HighRepeatConfidence = (
        TransitCount >= 5
        and DetectionSnr is not None
        and DetectionSnr >= 5
        and PeriodSde is not None
        and PeriodSde >= (7 if PeriodMethod == "TLS" else 8)
        and (EphemerisMatchFraction is None or EphemerisMatchFraction >= 0.85)
        and (ExpectedTransitCoverage is None or ExpectedTransitCoverage >= 0.65)
        and (OffEphemerisFraction is None or OffEphemerisFraction <= 0.2)
    )
    StrongRequirementsMet = (
        TransitCount >= 3
        and Period is not None
        and PeriodMethod in ("BLS", "TLS")
        and DetectionSnr is not None
        and (DetectionSnr >= 7 or HighRepeatConfidence)
        and (PeriodSde is None or PeriodSde >= RequiredPeriodSde)
        and (PeriodMethod != "TLS" or TlsFap is None or TlsFap <= 0.01)
        and (EphemerisMatchFraction is None or EphemerisMatchFraction >= 0.75)
        and (OffEphemerisFraction is None or OffEphemerisFraction <= 0.3)
        and DangerCount == 0
    )
    SevereTimingMismatch = (
        TransitCount >= 3
        and PeriodMethod in EphemerisPeriodMethods
        and EphemerisMatchFraction is not None
        and EphemerisMatchFraction < 0.55
        and not WellCoveredEphemeris
        and OffEphemerisCount is not None
        and OffEphemerisCount >= 2
    )
    CredibleTlsSignal = (
        PeriodMethod != "TLS"
        or (
            PeriodSde is not None
            and PeriodSde >= 5
            and DetectionSnr is not None
            and DetectionSnr >= 5
        )
    )

    if TransitCount == 0:
        HasUnboxedPeriodSignal = (
            RawCandidateScore >= 35
            and PeriodSde is not None
            and PeriodSde >= 7
            and (PValue is None or PValue <= 0.01)
        )
        if HasUnboxedPeriodSignal:
            Status = "inconclusive"
            Title = "Period signal needs review"
            ShortLabel = "Inconclusive"
            Summary = (
                "The period search found some signal, but the local detector did not box credible transit events. "
                "This needs manual review before calling it an exoplanet candidate."
            )
            Recommendation = "Inspect the phase-folded view and try adjusted duration/strictness bounds."
        else:
            Status = "no_planet_like_signal"
            Title = "No planet-like transit detected"
            ShortLabel = "No credible signal"
            Summary = (
                "No statistically credible repeating transit signal was found. "
                "This dataset may not contain a detectable transiting exoplanet at the current settings."
            )
            Recommendation = "Check the input columns, try lower strictness, or analyze a longer/higher-SNR light curve."
    elif SevereTimingMismatch:
        Status = "no_planet_like_signal"
        Title = "Transit-like dips are not periodic"
        ShortLabel = "No credible signal"
        Summary = (
            "The detector found dip-shaped events, but most do not align with one repeating orbital schedule. "
            "That pattern is more consistent with irregular variability or systematics than a single transiting exoplanet."
        )
        Recommendation = "Inspect the off-period dips and try stricter duration/depth bounds before treating this as a candidate."
    elif RawCandidateScore >= 75 and StrongRequirementsMet:
        Status = "strong_candidate"
        Title = "Strong planet-like transit candidate"
        ShortLabel = "Strong candidate"
        Summary = (
            "Repeated dips align with a stable period and pass the current signal-strength checks. "
            "This is a strong candidate, not a confirmed planet."
        )
        Recommendation = "Use the phase-folded view, exports, and follow-up vetting before treating this as confirmed."
    elif RawCandidateScore >= 45 and TransitCount >= 2 and CredibleTlsSignal:
        Status = "possible_candidate"
        Title = "Possible transit candidate"
        ShortLabel = "Possible candidate"
        Summary = (
            "The dataset contains some planet-like transit evidence, but one or more checks are not strong enough "
            "for a confident candidate call."
        )
        Recommendation = "Review warnings, period aliases, and the phase-folded view."
    else:
        Status = "no_planet_like_signal"
        Title = "No credible planet-like signal"
        ShortLabel = "No credible signal"
        Summary = (
            "Detected dips do not currently pass enough planet-likeness checks. "
            "This dataset may not contain a detectable transiting exoplanet."
        )
        Recommendation = "Inspect warnings and rerun with adjusted detection bounds if the light curve looks suspicious."

    CandidateScore = RawCandidateScore
    if Status == "possible_candidate":
        CandidateScore = min(CandidateScore, 74)
    elif Status == "inconclusive":
        CandidateScore = min(CandidateScore, 59)
    elif Status == "no_planet_like_signal":
        CandidateScore = min(CandidateScore, 44)

    return {
        "assessment_version": 2,
        "score_label": "Candidate score",
        "score_is_probability": False,
        "status": Status,
        "title": Title,
        "short_label": ShortLabel,
        "candidate_score": CandidateScore,
        "summary": Summary,
        "recommendation": Recommendation,
        "supporting_evidence": SupportingEvidence,
        "limiting_evidence": LimitingEvidence,
        "inputs": {
            "transit_count": TransitCount,
            "locally_supported_event_count": LocalEventCount,
            "evidence_basis": "combined periodic signal" if CombinedSupport and LocalEventCount < 3 else "locally supported events",
            "predicted_window_count": len(Transits),
            "period": Period,
            "period_method": PeriodMethod,
            "period_sde": PeriodSde,
            "detection_snr": DetectionSnr,
            "tls_fap": TlsFap,
            "p_value": PValue,
            "depth_scatter_ratio": DepthScatterRatio,
            "odd_even_depth_mismatch": OddEvenMismatch,
            "max_radius_ratio": MaxRadiusRatio,
            "median_transit_points": MedianTransitPoints,
            "ephemeris_match_fraction": EphemerisMatchFraction,
            "ephemeris_match_count": EphemerisMatchCount,
            "ephemeris_event_match_count": EphemerisEventMatchCount,
            "off_ephemeris_transit_count": OffEphemerisCount,
            "off_ephemeris_fraction": OffEphemerisFraction,
            "expected_transit_count": ExpectedTransitCount,
            "expected_transit_coverage": ExpectedTransitCoverage,
            "timing_residual_ratio": TimingResidualRatio,
            "warning_count": len(Warnings),
            "danger_warning_count": DangerCount,
            "caution_warning_count": CautionCount,
        },
    }


#MARK: plot stuffs
def RobustFluxLimits(Values, Sigma=4.0):
    Median = float(Np.median(Values))
    Mad = float(Np.median(Np.abs(Values - Median)))
    Noise = max(1.4826 * Mad, 1e-9)
    Low = Median - Sigma * Noise
    High = Median + Sigma * Noise
    PctLow, PctHigh = Np.percentile(Values, [0.2, 99.8])
    return float(min(Low, PctLow)), float(max(High, PctHigh))


#MARK: plot stuffs
def DomainFor(Values, LowerPercentile=0.5, UpperPercentile=99.5):
    Low, High = Np.percentile(Values, [LowerPercentile, UpperPercentile])
    Padding = max((High - Low) * 0.14, Np.std(Values) * 0.08, 1e-9)
    return float(Low - Padding), float(High + Padding)


#MARK: plot stuffs
def DownsampleIndices(Flux, MaxPoints=MAX_PLOT_POINTS):
    N = len(Flux)
    if N <= MaxPoints:
        return Np.arange(N, dtype=int)

    BucketCount = MaxPoints // 2
    Edges = Np.linspace(0, N, BucketCount + 1, dtype=int)
    Keep = []
    for Start, End in zip(Edges[:-1], Edges[1:]):
        if End <= Start:
            continue
        Segment = Flux[Start:End]
        MinI = Start + int(Np.argmin(Segment))
        MaxI = Start + int(Np.argmax(Segment))
        Keep.extend([MinI, MaxI])
    return Np.asarray(sorted(set(Keep)), dtype=int)


#MARK: plot stuffs
def DownsampleIndicesForSeries(SeriesValues, MaxPoints=MAX_PLOT_POINTS):
    Series = [Np.asarray(Values, dtype=float) for Values in SeriesValues if Values is not None]
    if not Series:
        return Np.asarray([], dtype=int)
    Size = min(len(Values) for Values in Series)
    if Size <= MaxPoints:
        return Np.arange(Size, dtype=int)

    PointsPerBucket = max(2, 2 * len(Series))
    BucketCount = max(1, (MaxPoints - 2) // PointsPerBucket)
    Edges = Np.linspace(0, Size, BucketCount + 1, dtype=int)
    Keep = {0, Size - 1}
    for Start, End in zip(Edges[:-1], Edges[1:]):
        if End <= Start:
            continue
        for Values in Series:
            Bucket = Values[Start:End]
            Finite = Np.isfinite(Bucket)
            if not Np.any(Finite):
                continue
            FiniteIndices = Np.flatnonzero(Finite)
            FiniteValues = Bucket[Finite]
            Keep.add(Start + int(FiniteIndices[int(Np.argmin(FiniteValues))]))
            Keep.add(Start + int(FiniteIndices[int(Np.argmax(FiniteValues))]))
    return Np.asarray(sorted(Keep), dtype=int)


#MARK: plot stuffs
def TrimPlotPoints(Time, Flux, SmoothFlux, MaxPoints=MAX_PLOT_POINTS):
    N = len(Time)
    Keep = DownsampleIndices(SmoothFlux if N > MaxPoints else Flux, MaxPoints)
    return Time[Keep], Flux[Keep], SmoothFlux[Keep]


#MARK: curve funcs
def ModelFluxAtObservations(Time, Period, Epoch, TransitModel, ExposureSeconds=None):
    if (
        TransitModel is None
        or Period is None
        or Epoch is None
        or not Math.isfinite(float(Period))
        or float(Period) <= 0
        or not Math.isfinite(float(Epoch))
    ):
        return None

    ModelPhase = Np.asarray(TransitModel.get("folded_phase_days", []), dtype=float)
    ModelFlux = Np.asarray(TransitModel.get("folded_flux", []), dtype=float)
    Size = min(ModelPhase.size, ModelFlux.size)
    if Size < 2:
        return None
    ModelPhase = ModelPhase[:Size]
    ModelFlux = ModelFlux[:Size]
    Valid = Np.isfinite(ModelPhase) & Np.isfinite(ModelFlux)
    ModelPhase = ModelPhase[Valid]
    ModelFlux = ModelFlux[Valid]
    if ModelPhase.size < 2:
        return None

    Order = Np.argsort(ModelPhase)
    ModelPhase = ModelPhase[Order]
    ModelFlux = ModelFlux[Order]
    ModelPhase, UniqueIndices = Np.unique(ModelPhase, return_index=True)
    ModelFlux = ModelFlux[UniqueIndices]
    if ModelPhase.size < 2:
        return None

    Period = float(Period)
    Phase = ((Np.asarray(Time, dtype=float) - float(Epoch) + Period / 2.0) % Period) - Period / 2.0
    return ExposureIntegratedTemplate(Phase, ModelPhase, ModelFlux, Period, ExposureSeconds)


#MARK: phase bins
def MakePhasePlot(Time, RawFlux, SmoothFlux, Period, Epoch, Duration, MaxPoints=MAX_PLOT_POINTS):
    if Period is None or Epoch is None:
        return None
    if not Math.isfinite(Period) or Period <= 0 or not Math.isfinite(Epoch):
        return None

    Phase = ((Time - Epoch + Period / 2.0) % Period) - Period / 2.0
    Order = Np.argsort(Phase)
    Phase = Phase[Order]
    RawFlux = RawFlux[Order]
    SmoothFlux = SmoothFlux[Order]

    Keep = DownsampleIndices(SmoothFlux if len(Phase) > MaxPoints else RawFlux, MaxPoints)
    PointPhase = Phase[Keep]
    PointRaw = RawFlux[Keep]
    PointSmooth = SmoothFlux[Keep]

    Cadence = float(Np.median(Np.diff(Time))) if len(Time) > 1 else 1.0
    DurationValue = float(Duration) if Duration is not None and Math.isfinite(Duration) and Duration > 0 else None
    FocusHalfWidth = max(Period * 0.04, Cadence * 30.0, 1.0)
    if DurationValue is not None:
        FocusHalfWidth = max(FocusHalfWidth, DurationValue * 4.0)
    FocusHalfWidth = min(Period / 2.0, FocusHalfWidth)

    GlobalBinCount = int(max(60, min(280, len(Phase) // 180)))
    GlobalEdges = Np.linspace(-Period / 2.0, Period / 2.0, GlobalBinCount + 1)
    FocusPointCount = int(Np.count_nonzero(Np.abs(Phase) <= FocusHalfWidth))
    if DurationValue is not None:
        TargetFocusWidth = max(Cadence, DurationValue / 24.0)
    else:
        TargetFocusWidth = max(Cadence, FocusHalfWidth / 80.0)
    DesiredFocusBins = int(Math.ceil(2.0 * FocusHalfWidth / TargetFocusWidth))
    DataLimitedFocusBins = max(40, FocusPointCount // 8)
    FocusBinCount = int(max(
        40,
        min(600, DesiredFocusBins, DataLimitedFocusBins),
    ))
    FocusEdges = Np.linspace(-FocusHalfWidth, FocusHalfWidth, FocusBinCount + 1)
    Edges = Np.unique(Np.r_[
        GlobalEdges[GlobalEdges < -FocusHalfWidth],
        FocusEdges,
        GlobalEdges[GlobalEdges > FocusHalfWidth],
    ])
    BinCount = len(Edges) - 1
    BinIds = Np.digitize(Phase, Edges) - 1
    BinnedPhase = []
    BinnedFlux = []
    BinnedCount = []
    BinnedUncertainty = []
    BinnedBreakIndices = []
    LastBin = None
    for BinIndex in range(BinCount):
        Mask = BinIds == BinIndex
        if not Np.any(Mask):
            continue
        if LastBin is not None and BinIndex > LastBin + 1:
            BinnedBreakIndices.append(len(BinnedPhase))
        BinnedPhase.append(float((Edges[BinIndex] + Edges[BinIndex + 1]) / 2.0))
        BinnedFlux.append(float(Np.median(RawFlux[Mask])))
        BinnedCount.append(int(Np.count_nonzero(Mask)))
        BinnedUncertainty.append(RobustStandardError(RawFlux[Mask]))
        LastBin = BinIndex

    BinnedPhase = Np.asarray(BinnedPhase, dtype=float)
    BinnedFlux = Np.asarray(BinnedFlux, dtype=float)

    if BinnedFlux.size >= 5:
        FluxMin, FluxMax = DomainFor(BinnedFlux, 0.0, 100.0)
    else:
        FluxMin, FluxMax = DomainFor(RawFlux, 0.5, 99.5)

    FocusMask = (BinnedPhase >= -FocusHalfWidth) & (BinnedPhase <= FocusHalfWidth)
    if Np.count_nonzero(FocusMask) >= 5:
        FocusFluxMin, FocusFluxMax = DomainFor(BinnedFlux[FocusMask], 0.0, 100.0)
    else:
        RawFocusMask = (Phase >= -FocusHalfWidth) & (Phase <= FocusHalfWidth)
        FocusValues = RawFlux[RawFocusMask] if Np.count_nonzero(RawFocusMask) >= 2 else RawFlux
        FocusFluxMin, FocusFluxMax = DomainFor(FocusValues, 0.5, 99.5)

    return {
        "phase": PointPhase.tolist(),
        "raw_flux": PointRaw.tolist(),
        "smooth_flux": PointSmooth.tolist(),
        "binned_phase": BinnedPhase.tolist(),
        "binned_flux": BinnedFlux.tolist(),
        "binned_count": BinnedCount,
        "binned_uncertainty": BinnedUncertainty,
        "binned_break_indices": BinnedBreakIndices,
        "representation": "normalized observations (global phase check)",
        "period": float(Period),
        "epoch": float(Epoch),
        "duration": DurationValue,
        "domain": {
            "time_min": float(-Period / 2.0),
            "time_max": float(Period / 2.0),
            "flux_min": FluxMin,
            "flux_max": FluxMax,
        },
        "focus_domain": {
            "time_min": float(-FocusHalfWidth),
            "time_max": float(FocusHalfWidth),
            "flux_min": FocusFluxMin,
            "flux_max": FocusFluxMax,
        },
    }


#MARK: transit stack
def BuildTransitStack(Time, SmoothFlux, Transits, Period, Duration, MaxTracePoints=320):
    """Align and locally normalize individual events for display-only inspection."""
    Time = Np.asarray(Time, dtype=float)
    SmoothFlux = Np.asarray(SmoothFlux, dtype=float)
    if Time.size < 3 or Time.size != SmoothFlux.size or not Transits:
        return None

    DurationValue = FiniteNumber(Duration)
    if DurationValue is None or DurationValue <= 0:
        Durations = FiniteValues([Item.get("duration") for Item in Transits])
        DurationValue = float(Np.median(Durations)) if Durations else None
    if DurationValue is None or DurationValue <= 0:
        return None

    FiniteTime = Time[Np.isfinite(Time)]
    if FiniteTime.size < 3:
        return None
    PositiveSteps = Np.diff(Np.sort(FiniteTime))
    PositiveSteps = PositiveSteps[PositiveSteps > 0]
    Cadence = float(Np.median(PositiveSteps)) if PositiveSteps.size else DurationValue / 20.0
    HalfWindow = max(DurationValue * 3.0, Cadence * 12.0)
    PeriodValue = FiniteNumber(Period)
    if PeriodValue is not None and PeriodValue > 0:
        HalfWindow = min(HalfWindow, PeriodValue * 0.35)
    HalfWindow = max(HalfWindow, DurationValue * 1.5, Cadence * 4.0)

    Traces = []
    CombinedPhase = []
    CombinedFlux = []
    Segments = ObservingSegments(Time)
    for Index, Transit in enumerate(Transits):
        Center = FiniteNumber(Transit.get("center"))
        if Center is None:
            continue
        Mask = (
            Np.isfinite(Time)
            & Np.isfinite(SmoothFlux)
            & (Time >= Center - HalfWindow)
            & (Time <= Center + HalfWindow)
        )
        Segment = next(((A, B) for A, B in Segments if Time[A] <= Center <= Time[B - 1]), None)
        if Segment is None:
            continue
        SegmentMask = Np.zeros(len(Time), dtype=bool)
        SegmentMask[Segment[0]:Segment[1]] = True
        Mask &= SegmentMask
        if Np.count_nonzero(Mask) < 3:
            continue

        Offsets = Time[Mask] - Center
        Values = SmoothFlux[Mask]
        Order = Np.argsort(Offsets)
        Offsets = Offsets[Order]
        Values = Values[Order]

        BaselineMask = Np.abs(Offsets) >= DurationValue * 0.75
        if Np.count_nonzero(BaselineMask) >= 6:
            Slope, Intercept = Np.polyfit(Offsets[BaselineMask], Values[BaselineMask], 1)
            BaselineCurve = Slope * Offsets + Intercept
            if not Np.all(Np.isfinite(BaselineCurve)) or Np.any(BaselineCurve <= 0):
                BaselineCurve = Np.full_like(Values, float(Np.median(Values[BaselineMask])))
        else:
            BaselineValues = Values[BaselineMask] if Np.any(BaselineMask) else Values
            BaselineCurve = Np.full_like(Values, float(Np.median(BaselineValues)))
        ValidBaseline = Np.isfinite(BaselineCurve) & (BaselineCurve > 0)
        if Np.count_nonzero(ValidBaseline) < 3:
            continue
        Offsets = Offsets[ValidBaseline]
        Values = Values[ValidBaseline]
        BaselineCurve = BaselineCurve[ValidBaseline]
        Normalized = Values / BaselineCurve

        CombinedPhase.append(Offsets)
        CombinedFlux.append(Normalized)
        Keep = DownsampleIndicesForSeries([Normalized], MaxTracePoints)
        Traces.append({
            "transit_index": Index + 1,
            "center": float(Center),
            "phase_days": Offsets[Keep].tolist(),
            "flux": Normalized[Keep].tolist(),
            "point_count": int(Offsets.size),
            "baseline": float(Np.median(BaselineCurve)),
            "cycle_number": Transit.get("cycle_number", Index),
            "state": Transit.get("state", "legacy_event"),
            "depth": Transit.get("signed_depth", Transit.get("depth")),
            "depth_uncertainty": Transit.get("depth_uncertainty"),
            "local_snr": Transit.get("local_snr"),
            "coverage_fraction": Transit.get("coverage_fraction"),
            "timing_residual": None if Transit.get("measured_center") is None else Transit["measured_center"] - Center,
            "timing_uncertainty": Transit.get("timing_uncertainty"),
        })

    if not Traces:
        return None

    AllPhase = Np.concatenate(CombinedPhase)
    AllFlux = Np.concatenate(CombinedFlux)
    TargetBinWidth = max(Cadence, DurationValue / 36.0)
    BinCount = int(max(48, min(400, Math.ceil(2.0 * HalfWindow / TargetBinWidth))))
    Edges = Np.linspace(-HalfWindow, HalfWindow, BinCount + 1)
    BinIds = Np.digitize(AllPhase, Edges) - 1
    MedianPhase = []
    MedianFlux = []
    for BinIndex in range(BinCount):
        Mask = BinIds == BinIndex
        if not Np.any(Mask):
            continue
        MedianPhase.append(float(Np.median(AllPhase[Mask])))
        MedianFlux.append(float(Np.median(AllFlux[Mask])))

    DomainValues = Np.r_[AllFlux, Np.asarray(MedianFlux, dtype=float)]
    FluxMin, FluxMax = DomainFor(DomainValues, 0.2, 99.8)
    return {
        "traces": Traces,
        "median_phase_days": MedianPhase,
        "median_flux": MedianFlux,
        "duration": float(DurationValue),
        "window_half_width": float(HalfWindow),
        "representation": "locally detrended normalized observations (event consistency)",
        "domain": {
            "time_min": float(-HalfWindow),
            "time_max": float(HalfWindow),
            "flux_min": FluxMin,
            "flux_max": FluxMax,
        },
    }


#MARK: extra signals
def ExploratoryLocalDips(Time, Flux, Options, TimeReference, MaxItems=500):
    """Reuse the local morphology detector as an explicitly unvalidated layer."""
    Candidates = []
    for Start, End in ObservingSegments(Time):
        if End - Start < 10:
            continue
        SegmentBaseline = float(Np.median(Flux[Start:End]))
        Prominence = DetectTransitsByProminence(Time[Start:End], Flux[Start:End], SegmentBaseline, Options)
        Threshold = DetectTransitsByThreshold(Time[Start:End], Flux[Start:End], SegmentBaseline, Options)
        LocalEvents = PruneOverlappingTransits((Prominence or {}).get("transits", []) + (Threshold or {}).get("transits", []))
        for Transit in LocalEvents:
            Event = dict(Transit)
            AddDepthMetrics(Event, float(Np.median(Flux[Start:End])))
            for Key in ("start", "end", "center"):
                Event[Key] -= TimeReference
            Event.update(role="exploratory", validated=False, source="local prominence/threshold detectors",
                         matched_signal_ids=[], assignment="unassigned")
            Candidates.append(Event)
    Total = len(Candidates)
    if Total > MaxItems:
        Candidates = sorted(Candidates, key=lambda Item: Item.get("depth", 0) * Math.sqrt(Item.get("points", 1)), reverse=True)[:MaxItems]
    Candidates.sort(key=lambda Item: Item["center"])
    for Index, Candidate in enumerate(Candidates):
        Candidate["dip_id"] = f"dip-{Index + 1}"
    return Candidates, {"method": "existing local prominence/threshold detectors, applied within observing segments",
                        "total_before_display_cap": Total, "display_cap": MaxItems,
                        "interpretation": "Unvalidated local features; not planets, not independent confirmations, and never added to the candidate score."}


#MARK: tag exploratory assignments
def TagExploratoryAssignments(Result, Signals):
    for Dip in Result.get("exploratory_dips", []):
        AbsoluteCenter = Dip["center"] + Result["time_reference"]
        Matches = []
        for Index, Signal in enumerate(Signals):
            RelativeCenter = AbsoluteCenter - Signal["time_reference"]
            if any(Event["start"] <= RelativeCenter <= Event["end"] for Event in Signal.get("predicted_windows", Signal.get("transits", []))):
                Matches.append(Signal.get("signal_id", f"signal-{Index + 1}"))
        Dip["matched_signal_ids"] = Matches
        Dip["assignment"] = "overlaps_predicted_window" if Matches else "unassigned"


#MARK: model shape
def JointTemplateAmplitudes(Time, SearchFlux, Signals, Uncertainty=None, ExposureSeconds=None):
    """Fit simultaneous depths and one baseline with orbital templates fixed.

    This handles additive small-planet flux deficits at overlapping timestamps.
    It does not infer orbital parameters or model overlapping silhouettes.
    """
    if len(Signals) < 2:
        return None
    try:
        from scipy.optimize import least_squares as LeastSquares
    except ImportError:
        return None
    Time, Values = Np.asarray(Time, dtype=float), Np.asarray(SearchFlux, dtype=float)
    Shapes, PriorDepths = [], []
    for Signal in Signals:
        Model = Signal.get("transit_model") or {}
        FoldedFlux = Np.asarray(Model.get("folded_flux", []), dtype=float)
        if FoldedFlux.size < 3:
            return None
        Baseline = float(Np.max(FoldedFlux))
        Depth = float(Baseline - Np.min(FoldedFlux))
        if Depth <= 0:
            return None
        Aligned = ModelFluxAtObservations(Time, Signal["period"], Signal["period_epoch"], Model, ExposureSeconds)
        if Aligned is None:
            return None
        Shapes.append(Np.maximum(0.0, (Baseline - Aligned) / Depth))
        PriorDepths.append(Depth)
    Design = Np.column_stack([Np.ones(len(Time))] + [-Shape for Shape in Shapes])
    Sigma = max(1.4826 * float(Np.median(Np.abs(Values - Np.median(Values)))), 1e-8)
    Errors = Np.full(len(Time), Sigma)
    if Uncertainty is not None:
        Supplied = Np.asarray(Uncertainty, dtype=float)
        if len(Supplied) == len(Time) and Np.all(Np.isfinite(Supplied)) and Np.all(Supplied > 0):
            Errors = Supplied
    Initial = [float(Np.median(Values)), *PriorDepths]
    Fit = LeastSquares(lambda Pars: (Design @ Pars - Values) / Errors, Initial,
                        jac=lambda Pars: Design / Errors[:, None], loss="soft_l1",
                        bounds=([0.5] + [0.0] * len(Signals), [1.5] + [0.5] * len(Signals)), max_nfev=60)
    if not Fit.success or not Np.all(Np.isfinite(Fit.x)):
        return None
    Degrees = max(len(Values) - len(Fit.x), 1)
    ResidualVariance = float(Np.sum(Fit.fun ** 2) / Degrees)
    try:
        Covariance = Np.linalg.pinv(Fit.jac.T @ Fit.jac) * max(1.0, ResidualVariance)
        ErrorsOnParameters = Np.sqrt(Np.maximum(0.0, Np.diag(Covariance)))
    except Np.linalg.LinAlgError:
        ErrorsOnParameters = Np.full(len(Fit.x), Np.nan)
    Fitted = Design @ Fit.x
    return {
        "baseline": float(Fit.x[0]), "depths": Fit.x[1:].tolist(),
        "depth_uncertainties": [float(Value) if Np.isfinite(Value) else None for Value in ErrorsOnParameters[1:]],
        "model_flux": Fitted, "residual_flux": Values - Fitted,
        "components": [1.0 - Depth * Shape for Depth, Shape in zip(Fit.x[1:], Shapes)],
        "metadata": {"method": "robust simultaneous additive template amplitude and baseline fit",
                     "fixed_parameters": ["period", "epoch", "duration", "template shape"],
                     "fitted_parameters": ["per-signal flux deficit", "shared baseline"],
                     "overlap_model": "sum of flux deficits; overlapping planet silhouettes are not modeled geometrically",
                     "uncertainty_basis": "conditional local Jacobian with residual-variance inflation; not an orbital posterior",
                     "reduced_chi_squared": ResidualVariance,
                     "overlapping_sample_count": int(Np.count_nonzero(Np.sum(Np.asarray(Shapes) > .001, axis=0) > 1))},
    }


#MARK: extra signals
def UpdateSignalJointDepth(Signal, Depth, Uncertainty):
    """Keep component model payloads consistent with a conditional joint depth."""
    Model = Signal.get("transit_model") or {}
    FoldedFlux = Np.asarray(Model.get("folded_flux", []), dtype=float)
    if FoldedFlux.size < 3:
        return
    Baseline = float(Np.max(FoldedFlux))
    PrevDepth = float(Baseline - Np.min(FoldedFlux))
    if PrevDepth <= 0:
        return
    Signal["transit_model"] = {**Model,
        "folded_flux": (1.0 - (Baseline - FoldedFlux) * Depth / PrevDepth).tolist(),
        "flux": (1.0 - (Baseline - Np.asarray(Model.get("flux", []))) * Depth / PrevDepth).tolist(),
        "depth_source": "conditional joint template amplitude", "component_baseline": 1.0,
    }
    if Signal.get("tls"):
        Signal["tls"] = {**Signal["tls"], "engine_depth_fraction": Signal["tls"].get("engine_depth_fraction", Signal["tls"].get("depth_fraction")),
                         "depth_fraction": float(Depth), "depth_uncertainty": Uncertainty,
                         "depth_source": "conditional joint template amplitude"}
    Comparison = Signal.get("model_comparison")
    if Comparison:
        Old = Np.asarray(Comparison["model_flux"])
        Updated = 1.0 - (Baseline - Old) * Depth / PrevDepth
        Signal["model_comparison"] = {**Comparison, "model_flux": Updated.tolist(),
                                      "residual_flux": (Np.asarray(Comparison["search_flux"]) - Updated).tolist()}
    Signal["joint_depth_refinement"] = {"depth_fraction": float(Depth), "uncertainty": Uncertainty,
                                        "parameters_held_fixed": ["period", "epoch", "duration", "template shape"]}


#MARK: curve funcs
def _PrepCurve(Time, Flux, Options):
    if Options is None:
        Options = dict(DEFAULT_DETECTION_OPTIONS)
    else:
        Options = {**DEFAULT_DETECTION_OPTIONS, **Options}
    Time, Flux = Np.asarray(Time, dtype=float), Np.asarray(Flux, dtype=float)
    if (
        len(Time) < 3
        or len(Time) != len(Flux)
        or not Np.isfinite(Time).all()
        or not Np.isfinite(Flux).all()
    ):
        raise ValueError("Analysis requires matching finite time/flux samples.")
    if Np.any(Np.diff(Time) <= 0):
        raise ValueError("Analysis timestamps must be sorted, unique, and span more than zero days.")

    # exposure isn't the same as the gap between samples.
    ExplicitExposure = Options.get("exposure_seconds")
    if ExplicitExposure is not None and (
        not Math.isfinite(float(ExplicitExposure))
        or not 0 <= float(ExplicitExposure) <= 86400
    ):
        raise ValueError("Exposure override must be between zero and 86400 seconds; leave blank when unknown.")
    ExposureInput = ExplicitExposure if ExplicitExposure is not None else Options.get("_exposure_seconds")
    Exposures = ExposureArraySeconds(ExposureInput, len(Time))
    Options["_exposure_seconds"] = Exposures
    KnownExposures = Exposures[Np.isfinite(Exposures)]
    if ExplicitExposure is not None:
        ExposureSource = "explicit per-file override"
    else:
        SuppliedMetadata = (Options.get("_input_metadata") or {}).get("exposure") or {}
        ExposureSource = SuppliedMetadata.get("source", "supplied array" if KnownExposures.size else "unknown")
    ExposureMetadata = {
        "source": ExposureSource,
        "unit": "seconds",
        "known_rows": int(KnownExposures.size),
        "unknown_rows": int(len(Time) - KnownExposures.size),
        "minimum_seconds": float(Np.min(KnownExposures)) if KnownExposures.size else None,
        "maximum_seconds": float(Np.max(KnownExposures)) if KnownExposures.size else None,
        "cadence_is_exposure": False,
        "timestamps_assumed": "exposure midpoints",
        "unknown_policy": "instantaneous template approximation; unknown exposure smearing uncertainty is not included",
        "scope": "conditional duration/depth refit and observation-aligned model; reference TLS search is unchanged",
    }
    return Time, Flux, Options, Exposures, ExposureMetadata


#MARK: flux errors
def _ScaleFluxErrors(Flux, Segments, NormalizationPlan, Uncertainties):
    if Uncertainties is None:
        return None, False
    Supplied = Np.asarray(Uncertainties, dtype=float)
    if len(Supplied) != len(Flux):
        return None, False

    # scale the errors along with the flux.
    Normalized = Supplied.copy()
    for Start, End in Segments:
        ResidualScale = NormalizationPlan.get("residual_scale")
        Scale = abs(float(Np.median(Flux[Start:End])) + (ResidualScale or 0.0))
        if Scale > 0:
            Normalized[Start:End] /= Scale
    Complete = bool(Np.all(Np.isfinite(Normalized)) and Np.all(Normalized > 0))
    return Normalized, Complete


#MARK: plot stuffs
def _TransitBoxLimits(Time, Transit, RawFlux, CleanFlux, ModelFlux):
    InWindow = (Time >= Transit["start"]) & (Time <= Transit["end"])
    Extents = {}
    for Name, Values in (("raw", RawFlux), ("clean", CleanFlux)):
        LocalValues = Values[InWindow]
        if Name == "clean" and ModelFlux is not None:
            LocalValues = Np.r_[LocalValues, ModelFlux[InWindow]]
        if not LocalValues.size:
            continue
        # one noisy point shouldn't stretch the whole box.
        Low, High = Np.percentile(LocalValues, [5, 95])
        Baseline = Transit.get("local_baseline")
        if Baseline is not None:
            High = max(High, Baseline)
        Padding = max((High - Low) * 0.12, 1e-6)
        Extents[Name] = {
            "flux_min": float(Low - Padding),
            "flux_max": float(High + Padding),
            "low": float(Low - Padding),
            "high": float(High + Padding),
        }
    return Extents


#MARK: plot stuffs
def _MakePlotThing(PlotTime, SearchFlux, ModelFlux, Keep, Breaks, Representation):
    return {
        "time": PlotTime.tolist(),
        "search_flux": SearchFlux[Keep].tolist(),
        "model_flux": ModelFlux[Keep].tolist(),
        "residual_flux": (SearchFlux - ModelFlux)[Keep].tolist(),
        "representation": Representation,
        "break_indices": Breaks.copy(),
    }


#MARK: analysis settings
def _PackSettingsThing(Options, Detection, ExposureMetadata, SearchMode):
    if SearchMode == "tls":
        DurationPolicy = "Physical TLS stellar-prior/template grid; explicit local dip duration bounds are not applied to TLS."
        BoundsReason = "Upper period limited by observed baseline / minimum transit count; explicit bounds also applied."
    else:
        DurationPolicy = "Explicit or cadence-derived BLS duration bounds."
        BoundsReason = "Cadence, baseline and explicit period/duration bounds applied to BLS."
    return {
        **Options,
        "stellar_priors": (Detection.get("tls") or {}).get("effective_stellar_priors"),
        "exposure": ExposureMetadata,
        "local_dip_settings": {
            Key: Options.get(Key)
            for Key in ("strictness", "smoothing", "min_depth", "min_duration", "max_duration")
        },
        "search_bounds": {
            **(Detection.get("period_search") or {}),
            "min_transits": Options.get("tls_min_transits"),
            "duration_policy": DurationPolicy,
            "bounds_reason": BoundsReason,
        },
    }




#MARK: old calls
def analyze(time, flux, options=None, progress_callback=None):
    return RunCurve(time, flux, options, ProgressCallback=progress_callback)


def parse_detection_options(form):
    return ParseDetectionOptions(form)


def normalized_flux_for_tls(time, flux):
    return NormalizedFluxForTls(time, flux)


#MARK: tls funcs
def estimate_period_with_tls(time, flux, options=None, progress_callback=None):
    return EstimatePeriodWithTls(time, flux, options, ProgressCallback=progress_callback)
