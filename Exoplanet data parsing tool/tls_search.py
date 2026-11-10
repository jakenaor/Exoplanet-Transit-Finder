"""Run reference TLS and turn its results into data the app can use."""

import math as Math
import importlib as Importlib
import threading as Threading
import time as MonotonicTime
from collections import deque as Deque
from contextlib import contextmanager as Contextmanager

import numpy as Np

try:
    from transitleastsquares import transitleastsquares as Transitleastsquares
    from transitleastsquares import tls_constants as TlsConstants
except Exception as Exc:  # pragma: no cover - exercised only in incomplete environments
    Transitleastsquares = None
    TlsConstants = None
    TLS_IMPORT_ERROR = Exc
else:
    TLS_IMPORT_ERROR = None


#MARK: core stuffs
MAX_MODEL_POINTS = 12000
MAX_SPECTRUM_POINTS = 1600
_PROGRESS_LOCK = Threading.RLock()


#MARK: run progress
class SearchProgress:
    """Count real TLS trials; forecast only from stable observed throughput.

    TLS 1.32 shuffles its trial grid and reports unordered worker completions.
    These counts do not expose the cost of the remaining trials. The displayed
    range is the spread of observed throughput, not a confidence interval.
    """

    #MARK: core stuffs
    def __init__(self, Callback, total=0, **Kwargs):
        self.Callback = Callback
        self.Total = int(total)
        self.Completed = 0
        self.Started = MonotonicTime.monotonic()
        self.LastSent = -Math.inf
        self.FirstCompletionTime = None
        self.FirstCompletionCount = 0
        self.windows = Deque(maxlen=12)
        self.WindowStarted = None
        self.WindowCompleted = 0
        self.emit(Force=True)

    #MARK: emit
    def emit(self, Force=False, Finished=False):
        Now = MonotonicTime.monotonic()
        if not Force and Now - self.LastSent < 0.75:
            return
        Elapsed = Now - self.Started
        ActiveElapsed = Now - self.FirstCompletionTime if self.FirstCompletionTime is not None else 0.0
        Remaining = Low = High = Variation = None
        SampleSeconds = sum(Duration for _, Duration in self.windows)
        # leave worker startup out of the estimate and use separate rate windows.
        Enough = (self.Completed >= max(12, int(self.Total * 0.05))
                  and len(self.windows) >= 4)
        if Enough and self.Completed < self.Total and not Finished:
            OverallRate = (self.Completed - self.FirstCompletionCount) / max(ActiveElapsed, 1e-9)
            RecentRate = sum(Count for Count, _ in self.windows) / max(SampleSeconds, 1e-9)
            if RecentRate > 0 and OverallRate > 0:
                WorkLeft = self.Total - self.Completed
                Rates = [Count / Duration for Count, Duration in self.windows] + [OverallRate]
                if min(Rates) > 0:
                    Variation = max(Rates) / min(Rates)
                    Trend = max(OverallRate, RecentRate) / min(OverallRate, RecentRate)
                    if Variation <= 1.75 and Trend <= 1.5:
                        Remaining = WorkLeft / RecentRate
                        Low = WorkLeft / max(Rates)
                        High = WorkLeft / min(Rates)
        Details = {
            "completed_trials": self.Completed, "total_trials": self.Total,
            "work_completed": self.Completed, "work_total": self.Total,
            "estimated_remaining_seconds": Remaining,
            "eta_lower_seconds": Low, "eta_upper_seconds": High,
            "remaining_seconds_range": [Low, High] if Low is not None else None,
            "eta_scope": "search", "search_elapsed_seconds": Elapsed,
            "throughput_elapsed_seconds": ActiveElapsed,
            "search_complete": bool(Finished),
            "eta_state": "available" if Remaining is not None else "estimating",
            "eta_method": "observed_trial_throughput",
            "eta_sample_seconds": SampleSeconds,
            "eta_variation": Variation,
        }
        self.Callback(Details)
        self.LastSent = Now

    #MARK: update
    def update(self, Count=1):
        self.Completed = min(self.Total, self.Completed + int(Count))
        if self.FirstCompletionTime is None and self.Completed > 0:
            self.FirstCompletionTime = MonotonicTime.monotonic()
            self.FirstCompletionCount = self.Completed
            self.WindowStarted = self.FirstCompletionTime
            self.WindowCompleted = self.Completed
            self.emit(Force=True)
            return
        Now = MonotonicTime.monotonic()
        if self.WindowStarted is not None and Now - self.WindowStarted >= 5.0:
            self.windows.append((self.Completed - self.WindowCompleted, Now - self.WindowStarted))
            self.WindowStarted = Now
            self.WindowCompleted = self.Completed
        self.emit()

    #MARK: close
    def close(self):
        self.emit(Force=True, Finished=True)


#MARK: run progress
@Contextmanager
def MeasuredTlsProgress(Callback):
    # read tls's own trial counter. the lock also covers direct threaded calls.
    with _PROGRESS_LOCK:
        if not callable(Callback):
            yield False
            return
        Module = Importlib.import_module("transitleastsquares.main")
        Stats = Importlib.import_module("transitleastsquares.stats")
        Original = Module.tqdm
        OriginalStats = Stats.tqdm
        Module.tqdm = lambda *Args, **Kwargs: SearchProgress(Callback, *Args, **Kwargs)
        class QuietFinalization:
            def __init__(self, *Args, **Kwargs):
                pass
            def update(self, *Args, **Kwargs):
                pass
            def close(self):
                pass
        Stats.tqdm = QuietFinalization
        try:
            yield True
        finally:
            Module.tqdm = Original
            Stats.tqdm = OriginalStats


#MARK: result helpers
def FiniteNumber(Value):
    if Value is None or isinstance(Value, (bool, Np.bool_)):
        return None
    try:
        Number = float(Value)
    except (TypeError, ValueError):
        return None
    return Number if Math.isfinite(Number) else None


#MARK: finite int
def FiniteInt(Value):
    Number = FiniteNumber(Value)
    return None if Number is None else int(Number)


#MARK: finite list
def FiniteList(Values):
    if Values is None:
        return []
    Array = Np.asarray(Values).reshape(-1)
    return [
        float(Value)
        for Value in Array
        if FiniteNumber(Value) is not None
    ]


#MARK: nullable list
def NullableList(Values):
    return [
        FiniteNumber(Value)
        for Value in Np.asarray(Values).reshape(-1)
    ]


#MARK: compact indices
def CompactIndices(Values, MaxPoints=MAX_SPECTRUM_POINTS, SelectedIndex=None):
    Values = Np.asarray(Values, dtype=float)
    Count = int(Values.size)
    if Count <= MaxPoints:
        return Np.arange(Count, dtype=int)

    Keep = set(Np.linspace(0, Count - 1, MaxPoints, dtype=int).tolist())
    TopCount = min(80, Count)
    if TopCount:
        TopIndices = Np.argpartition(Values, Count - TopCount)[-TopCount:]
        Keep.update(int(Index) for Index in TopIndices)
    if SelectedIndex is not None:
        Keep.add(int(SelectedIndex))
    return Np.asarray(sorted(Keep), dtype=int)


#MARK: period funcs
def DistinctPeriodCandidates(Periods, power, PowerRaw, Limit=8):
    Periods = Np.asarray(Periods, dtype=float)
    power = Np.asarray(power, dtype=float)
    PowerRaw = Np.asarray(PowerRaw, dtype=float)
    Valid = Np.isfinite(Periods) & Np.isfinite(power) & (Periods > 0)
    if not Np.any(Valid):
        return []

    ValidIndices = Np.flatnonzero(Valid)
    LocalIndices = []
    for Index in ValidIndices:
        Left = power[Index - 1] if Index > 0 else -Math.inf
        Right = power[Index + 1] if Index + 1 < power.size else -Math.inf
        if power[Index] >= Left and power[Index] >= Right:
            LocalIndices.append(int(Index))
    if not LocalIndices:
        LocalIndices = ValidIndices.tolist()

    Ordered = sorted(LocalIndices, key=lambda Index: power[Index], reverse=True)
    Candidates = []
    for Index in Ordered:
        Period = float(Periods[Index])
        if any(abs(Period - Item["period"]) / Period < 0.01 for Item in Candidates):
            continue
        RawValue = FiniteNumber(PowerRaw[Index]) if Index < PowerRaw.size else None
        Candidates.append({
            "period": Period,
            "power": RawValue,
            "sde": float(power[Index]),
            "method": "TLS",
        })
        if len(Candidates) >= Limit:
            break
    return Candidates


#MARK: model curves
def CompactModel(TimeValues, FluxValues, MaxPoints=MAX_MODEL_POINTS):
    TimeValues = Np.asarray(TimeValues, dtype=float).reshape(-1)
    FluxValues = Np.asarray(FluxValues, dtype=float).reshape(-1)
    Size = min(TimeValues.size, FluxValues.size)
    if Size == 0:
        return [], []
    TimeValues = TimeValues[:Size]
    FluxValues = FluxValues[:Size]
    Valid = Np.isfinite(TimeValues) & Np.isfinite(FluxValues)
    TimeValues = TimeValues[Valid]
    FluxValues = FluxValues[Valid]
    if TimeValues.size > MaxPoints:
        # keep each bucket's high and low points so narrow transits survive.
        BucketCount = max(1, (MaxPoints - 2) // 2)
        Edges = Np.linspace(0, TimeValues.size, BucketCount + 1, dtype=int)
        Keep = {0, int(TimeValues.size - 1)}
        for Start, End in zip(Edges[:-1], Edges[1:]):
            if End <= Start:
                continue
            Bucket = FluxValues[Start:End]
            Keep.add(Start + int(Np.argmin(Bucket)))
            Keep.add(Start + int(Np.argmax(Bucket)))
        Keep = Np.asarray(sorted(Keep), dtype=int)
        TimeValues = TimeValues[Keep]
        FluxValues = FluxValues[Keep]
    return TimeValues.tolist(), FluxValues.tolist()


#MARK: model shape
def DurationFromFoldedModel(PhaseDays, ModelFlux, Period=None):
    PhaseDays = Np.asarray(PhaseDays, dtype=float).reshape(-1)
    ModelFlux = Np.asarray(ModelFlux, dtype=float).reshape(-1)
    Size = min(PhaseDays.size, ModelFlux.size)
    if Size < 3:
        return None
    PhaseDays = PhaseDays[:Size]
    ModelFlux = ModelFlux[:Size]
    Valid = Np.isfinite(PhaseDays) & Np.isfinite(ModelFlux)
    PhaseDays = PhaseDays[Valid]
    ModelFlux = ModelFlux[Valid]
    if PhaseDays.size < 3:
        return None

    Baseline = float(Np.max(ModelFlux))
    Bottom = float(Np.min(ModelFlux))
    Depth = Baseline - Bottom
    if not Math.isfinite(Depth) or Depth <= 0:
        return None

    # gaps can shorten tls's reported duration; measure the folded curve too.
    InTransit = ModelFlux < Baseline - Depth * 0.001
    if Np.count_nonzero(InTransit) < 2:
        return None
    TransitPhase = PhaseDays[InTransit]
    Duration = float(Np.max(TransitPhase) - Np.min(TransitPhase))
    if Duration <= 0:
        return None
    if Period is not None and Duration >= float(Period) * 0.5:
        return None
    return Duration


#MARK: model shape
def ModelContactSampleCount(ModelFlux):
    Values = Np.asarray(ModelFlux, dtype=float).reshape(-1)
    Values = Values[Np.isfinite(Values)]
    if Values.size < 3:
        return 0
    Baseline, Bottom = float(Np.max(Values)), float(Np.min(Values))
    Depth = Baseline - Bottom
    return int(Np.count_nonzero(Values < Baseline - Depth * .001)) if Depth > 0 else 0


#MARK: core stuffs
def CompactFoldedTransitModel(PhaseDays, ModelFlux, MaxPoints=MAX_MODEL_POINTS):
    """Keep the transit detail when shrinking a model for the browser."""
    Phase, Values = Np.asarray(PhaseDays, dtype=float), Np.asarray(ModelFlux, dtype=float)
    Size = min(Phase.size, Values.size)
    if Size <= MaxPoints:
        return CompactModel(Phase, Values, MaxPoints=MaxPoints)
    Phase, Values = Phase[:Size], Values[:Size]
    Valid = Np.isfinite(Phase) & Np.isfinite(Values)
    Phase, Values = Phase[Valid], Values[Valid]
    if len(Phase) < 3:
        return Phase.tolist(), Values.tolist()
    Baseline = float(Np.max(Values))
    Depth = Baseline - float(Np.min(Values))
    Contact = Np.flatnonzero(Values < Baseline - Depth * 1e-10)
    if not Contact.size:
        return CompactModel(Phase, Values, MaxPoints=MaxPoints)
    Left, Right = max(0, int(Contact[0]) - 1), min(len(Phase), int(Contact[-1]) + 2)
    ContactPhase, ContactFlux = CompactModel(Phase[Left:Right], Values[Left:Right], MaxPoints=MaxPoints - 2)
    Phases = Np.r_[Phase[0], ContactPhase, Phase[-1]]
    Fluxes = Np.r_[Values[0], ContactFlux, Values[-1]]
    Order = Np.argsort(Phases)
    Phases, Fluxes = Phases[Order], Fluxes[Order]
    Phases, Unique = Np.unique(Phases, return_index=True)
    return Phases.tolist(), Fluxes[Unique].tolist()


#MARK: representative unfolded transit
def RepresentativeUnfoldedTransit(ModelTime, ModelFlux, TransitTimes, Period):
    ModelTime = Np.asarray(ModelTime, dtype=float).reshape(-1)
    ModelFlux = Np.asarray(ModelFlux, dtype=float).reshape(-1)
    TransitTimes = Np.asarray(TransitTimes, dtype=float).reshape(-1)
    Size = min(ModelTime.size, ModelFlux.size)
    Period = FiniteNumber(Period)
    if Size < 3 or Period is None or Period <= 0:
        return Np.asarray([], dtype=float), Np.asarray([], dtype=float)

    ModelTime = ModelTime[:Size]
    ModelFlux = ModelFlux[:Size]
    Valid = Np.isfinite(ModelTime) & Np.isfinite(ModelFlux)
    ModelTime = ModelTime[Valid]
    ModelFlux = ModelFlux[Valid]
    TransitTimes = TransitTimes[Np.isfinite(TransitTimes)]
    if ModelTime.size < 3 or TransitTimes.size == 0:
        return Np.asarray([], dtype=float), Np.asarray([], dtype=float)

    ModelMin = float(Np.min(ModelTime))
    ModelMax = float(Np.max(ModelTime))
    CompleteCenters = TransitTimes[
        (TransitTimes - Period / 2.0 >= ModelMin)
        & (TransitTimes + Period / 2.0 <= ModelMax)
    ]
    Centers = CompleteCenters if CompleteCenters.size else TransitTimes
    Center = float(Centers[len(Centers) // 2])
    InCycle = (
        (ModelTime >= Center - Period / 2.0)
        & (ModelTime <= Center + Period / 2.0)
    )
    if Np.count_nonzero(InCycle) < 3:
        return Np.asarray([], dtype=float), Np.asarray([], dtype=float)

    PhaseDays = ModelTime[InCycle] - Center
    CycleFlux = ModelFlux[InCycle]
    Order = Np.argsort(PhaseDays)
    PhaseDays = PhaseDays[Order]
    CycleFlux = CycleFlux[Order]
    PhaseDays, UniqueIndices = Np.unique(PhaseDays, return_index=True)
    CycleFlux = CycleFlux[UniqueIndices]
    return PhaseDays, CycleFlux


#MARK: sampling fill factor
def SamplingFillFactor(Time):
    Time = Np.asarray(Time, dtype=float).reshape(-1)
    Time = Np.sort(Np.unique(Time[Np.isfinite(Time)]))
    if Time.size < 2:
        return None
    Span = float(Time[-1] - Time[0])
    PositiveSteps = Np.diff(Time)
    PositiveSteps = PositiveSteps[PositiveSteps > 0]
    if Span <= 0 or PositiveSteps.size == 0:
        return None
    Cadence = float(Np.median(PositiveSteps))
    if not Math.isfinite(Cadence) or Cadence <= 0:
        return None
    TheoreticalCadences = Span / Cadence
    if TheoreticalCadences <= 0:
        return None
    return float(min(1.0, max((Time.size - 1) / TheoreticalCadences, 1e-9)))


#MARK: model shape
def RescaleFoldedModelDuration(PhaseDays, ModelFlux, TargetDuration, Period=None):
    PhaseDays = Np.asarray(PhaseDays, dtype=float).reshape(-1)
    ModelFlux = Np.asarray(ModelFlux, dtype=float).reshape(-1)
    Size = min(PhaseDays.size, ModelFlux.size)
    TargetDuration = FiniteNumber(TargetDuration)
    Period = FiniteNumber(Period)
    if Size < 3 or TargetDuration is None or TargetDuration <= 0:
        return Np.asarray([], dtype=float), Np.asarray([], dtype=float)
    if Period is not None and TargetDuration >= Period * 0.5:
        return Np.asarray([], dtype=float), Np.asarray([], dtype=float)

    PhaseDays = PhaseDays[:Size]
    ModelFlux = ModelFlux[:Size]
    Valid = Np.isfinite(PhaseDays) & Np.isfinite(ModelFlux)
    PhaseDays = PhaseDays[Valid]
    ModelFlux = ModelFlux[Valid]
    if PhaseDays.size < 3:
        return Np.asarray([], dtype=float), Np.asarray([], dtype=float)

    Order = Np.argsort(PhaseDays)
    PhaseDays = PhaseDays[Order]
    ModelFlux = ModelFlux[Order]
    Baseline = float(Np.max(ModelFlux))
    Bottom = float(Np.min(ModelFlux))
    Depth = Baseline - Bottom
    if not Math.isfinite(Depth) or Depth <= 0:
        return Np.asarray([], dtype=float), Np.asarray([], dtype=float)

    InTransit = ModelFlux < Baseline - Depth * 0.001
    if Np.count_nonzero(InTransit) < 2:
        return Np.asarray([], dtype=float), Np.asarray([], dtype=float)
    # rescale the full contact region, including the faint edges of the transit.
    TransitIndices = Np.flatnonzero(ModelFlux < Baseline - Depth * 1e-10)
    LeftIndex = max(0, int(TransitIndices[0]) - 1)
    RightIndex = min(len(PhaseDays) - 1, int(TransitIndices[-1]) + 1)
    SourceLeft = float(PhaseDays[LeftIndex])
    SourceRight = float(PhaseDays[RightIndex])
    SourceDuration = SourceRight - SourceLeft
    if SourceDuration <= 0:
        return Np.asarray([], dtype=float), Np.asarray([], dtype=float)

    SourceCenter = (SourceLeft + SourceRight) / 2.0
    TargetCenter = 0.0
    Scale = TargetDuration / SourceDuration
    ContactWindow = Np.arange(len(PhaseDays))
    ContactWindow = (ContactWindow >= LeftIndex) & (ContactWindow <= RightIndex)
    ScaledContactPhase = TargetCenter + (
        PhaseDays[ContactWindow] - SourceCenter
    ) * Scale
    OutsideTarget = Np.abs(PhaseDays - TargetCenter) > TargetDuration / 2.0
    KeepBaseline = (~ContactWindow) & (~InTransit) & OutsideTarget
    ScaledPhase = Np.r_[PhaseDays[KeepBaseline], ScaledContactPhase]
    ScaledFlux = Np.r_[ModelFlux[KeepBaseline], ModelFlux[ContactWindow]]
    ScaledOrder = Np.argsort(ScaledPhase)
    ScaledPhase = ScaledPhase[ScaledOrder]
    ScaledFlux = ScaledFlux[ScaledOrder]
    ScaledPhase, UniqueIndices = Np.unique(ScaledPhase, return_index=True)
    ScaledFlux = ScaledFlux[UniqueIndices]
    return ScaledPhase, ScaledFlux


#MARK: model shape
def ObservedPhaseFoldedDuration(Time, Flux, Period, Epoch, SeedDuration):
    Time = Np.asarray(Time, dtype=float).reshape(-1)
    Flux = Np.asarray(Flux, dtype=float).reshape(-1)
    Size = min(Time.size, Flux.size)
    Period = FiniteNumber(Period)
    Epoch = FiniteNumber(Epoch)
    SeedDuration = FiniteNumber(SeedDuration)
    if (
        Size < 20
        or Period is None
        or Epoch is None
        or SeedDuration is None
        or Period <= 0
        or SeedDuration <= 0
    ):
        return None

    Time = Time[:Size]
    Flux = Flux[:Size]
    Valid = Np.isfinite(Time) & Np.isfinite(Flux)
    Time = Time[Valid]
    Flux = Flux[Valid]
    if Time.size < 20:
        return None

    UniqueTime = Np.sort(Np.unique(Time))
    Steps = Np.diff(UniqueTime)
    Steps = Steps[Steps > 0]
    if Steps.size == 0:
        return None
    Cadence = float(Np.median(Steps))
    Focus = min(Period * 0.22, max(SeedDuration * 3.0, Cadence * 40.0))
    if Focus <= SeedDuration / 2.0:
        return None

    BinWidth = max(Cadence, SeedDuration / 60.0)
    BinCount = max(25, int(Math.ceil(2.0 * Focus / BinWidth)))
    Edges = Np.linspace(-Focus, Focus, BinCount + 1)
    Centers = (Edges[:-1] + Edges[1:]) / 2.0
    Phase = ((Time - Epoch + Period / 2.0) % Period) - Period / 2.0
    BinIds = Np.digitize(Phase, Edges) - 1
    BinnedFlux = Np.asarray([
        Np.median(Flux[BinIds == Index])
        if Np.any(BinIds == Index)
        else Np.nan
        for Index in range(BinCount)
    ])
    SmoothFlux = Np.full(BinCount, Np.nan, dtype=float)
    for Index in range(BinCount):
        Window = BinnedFlux[max(0, Index - 1):min(BinCount, Index + 2)]
        FiniteWindow = Window[Np.isfinite(Window)]
        if FiniteWindow.size:
            SmoothFlux[Index] = float(Np.mean(FiniteWindow))
    FiniteBins = Np.isfinite(SmoothFlux)

    ShoulderMin = max(SeedDuration * 0.9, Cadence * 8.0)
    ShoulderMax = min(
        Focus * 0.95,
        max(SeedDuration * 2.2, ShoulderMin + Cadence * 12.0),
    )
    ShoulderMask = (
        FiniteBins
        & (Np.abs(Centers) >= ShoulderMin)
        & (Np.abs(Centers) <= ShoulderMax)
    )
    ShoulderFlux = SmoothFlux[ShoulderMask]
    CoreMask = FiniteBins & (Np.abs(Centers) <= max(SeedDuration * 0.3, Cadence * 3.0))
    CoreFlux = SmoothFlux[CoreMask]
    if ShoulderFlux.size < 8 or CoreFlux.size < 3:
        return None

    Baseline = float(Np.median(ShoulderFlux))
    BaselineNoise = 1.4826 * float(Np.median(Np.abs(ShoulderFlux - Baseline)))
    Bottom = float(Np.percentile(CoreFlux, 15.0))
    Depth = Baseline - Bottom
    if not Math.isfinite(Depth) or Depth <= max(BaselineNoise * 5.0, 1e-9):
        return None

    ThresholdDrop = max(Depth * 0.05, BaselineNoise * 3.0)
    InSignal = FiniteBins & (SmoothFlux < Baseline - ThresholdDrop)
    for Index in range(1, len(InSignal) - 1):
        if not InSignal[Index] and InSignal[Index - 1] and InSignal[Index + 1]:
            InSignal[Index] = True

    CoreIndices = Np.flatnonzero(CoreMask)
    if CoreIndices.size == 0:
        return None
    CenterIndex = int(CoreIndices[Np.argmin(SmoothFlux[CoreIndices])])
    if not InSignal[CenterIndex]:
        return None
    Left = CenterIndex
    while Left > 0 and InSignal[Left - 1]:
        Left -= 1
    Right = CenterIndex
    while Right + 1 < len(InSignal) and InSignal[Right + 1]:
        Right += 1
    if Left == 0 or Right == len(InSignal) - 1:
        return None

    MeasuredStart = float(Edges[Left])
    MeasuredEnd = float(Edges[Right + 1])
    Padding = float(Edges[1] - Edges[0])
    SymmetricDuration = 2.0 * max(
        abs(MeasuredStart - Padding),
        abs(MeasuredEnd + Padding),
    )
    MaximumDuration = min(Period * 0.25, SeedDuration * 2.5)
    if SymmetricDuration <= SeedDuration or SymmetricDuration > MaximumDuration:
        return None
    return {
        "duration": float(SymmetricDuration),
        "measured_start": MeasuredStart,
        "measured_end": MeasuredEnd,
        "bin_width": Padding,
        "baseline": Baseline,
        "depth": Depth,
        "baseline_noise": BaselineNoise,
        "threshold_drop": ThresholdDrop,
    }


#MARK: tls funcs
def TlsEngineVersion():
    if TlsConstants is None:
        return None
    Version = str(getattr(TlsConstants, "TLS_VERSION", "TLS 1.32"))
    return Version.replace("Transit Least Squares ", "").strip()


#MARK: exposure model
def ExposureArraySeconds(ExposureSeconds, Size):
    """Return aligned durations; NaN means unknown, zero means instantaneous."""
    if ExposureSeconds is None:
        return Np.full(Size, Np.nan)
    Values = Np.asarray(ExposureSeconds, dtype=float)
    if Values.ndim == 0:
        Values = Np.full(Size, float(Values))
    if Values.ndim != 1 or len(Values) != Size:
        raise ValueError("Exposure durations must align with observations.")
    if Np.any(Np.isinf(Values)) or Np.any(Values[Np.isfinite(Values)] < 0):
        raise ValueError("Exposure durations must be nonnegative finite seconds or null when unknown.")
    return Values


#MARK: exposure model
def ExposureIntegratedTemplate(PhaseDays, TemplatePhase, TemplateFlux, Period,
                                 ExposureSeconds=None, Baseline=1.0):
    """Evaluate a periodic template at the actual exposure midpoints.

    Unknown durations use an explicitly reported instantaneous approximation.
    The periodic piecewise-linear model is integrated exactly, including whole
    orbital cycles. Cadence and plotting-bin widths are never exposures. The
    caller supplies midpoint timestamps.
    """
    Phases = Np.asarray(PhaseDays, dtype=float)
    Exposures = ExposureArraySeconds(ExposureSeconds, len(Phases))
    Period = float(Period)
    if not Math.isfinite(Period) or Period <= 0:
        raise ValueError("Exposure integration requires a positive finite period.")
    TemplatePhase, TemplateFlux = Np.asarray(TemplatePhase, dtype=float), Np.asarray(TemplateFlux, dtype=float)
    Wrapped = (Phases + Period / 2.0) % Period - Period / 2.0
    Result = Np.interp(Wrapped, TemplatePhase, TemplateFlux, left=Baseline, right=Baseline)
    Finite = Np.flatnonzero(Np.isfinite(Exposures) & (Exposures > 0))
    if not Finite.size:
        return Result
    # subtract the baseline first to keep small transit areas precise.
    # outside the template, use the same flat baseline as np.interp.
    Deviation = TemplateFlux - Baseline
    Intervals = Np.diff(TemplatePhase)
    if len(TemplatePhase) < 2 or Np.any(Intervals <= 0):
        raise ValueError("Exposure integration requires a sorted unique template with at least two points.")
    Slopes = Np.diff(Deviation) / Intervals
    Cumulative = Np.r_[0.0, Np.cumsum(Intervals * (Deviation[:-1] + Deviation[1:]) / 2.0)]

    def Primitive(Position):
        Position = Np.asarray(Position, dtype=float)
        Indices = Np.searchsorted(TemplatePhase, Position, side="right") - 1
        Clipped = Np.clip(Indices, 0, len(TemplatePhase) - 2)
        Offset = Position - TemplatePhase[Clipped]
        Area = Cumulative[Clipped] + Deviation[Clipped] * Offset + Slopes[Clipped] * Offset ** 2 / 2.0
        return Np.where(Position <= TemplatePhase[0], 0.0,
                        Np.where(Position >= TemplatePhase[-1], Cumulative[-1], Area))

    Left = -Period / 2.0
    OriginArea = float(Primitive(Left))
    CycleArea = float(Primitive(Period / 2.0)) - OriginArea

    def PeriodicPrimitive(Position):
        Cycles = Np.floor((Position - Left) / Period)
        Local = (Position - Left) % Period + Left
        return Cycles * CycleArea + Primitive(Local) - OriginArea

    Width = Exposures[Finite] / 86400.0
    Centers = Wrapped[Finite]
    Result[Finite] = Baseline + (PeriodicPrimitive(Centers + Width / 2.0)
                                - PeriodicPrimitive(Centers - Width / 2.0)) / Width
    return Result


#MARK: core stuffs
def FitObservedModelDuration(Time, Flux, Period, Epoch, SeedDuration, Phase, ModelFlux,
                                ExposureSeconds=None, FluxUncertainty=None):
    """Refit the physical template's width/depth on matched search observations.

    Unlike threshold-based widening, this can shorten or lengthen a duration.
    Known exposure durations are integrated at actual observation midpoints.
    Unknown exposure is explicitly instantaneous; cadence is not exposure.
    This is a conditional template fit, not a new period search or a posterior.
    """
    try:
        from scipy.optimize import least_squares as LeastSquares
    except ImportError:
        return None
    Time = Np.asarray(Time, dtype=float)
    Flux = Np.asarray(Flux, dtype=float)
    Exposures = ExposureArraySeconds(ExposureSeconds, len(Time))
    SuppliedErrors = Np.asarray(FluxUncertainty, dtype=float) if FluxUncertainty is not None else None
    if SuppliedErrors is not None and (SuppliedErrors.ndim != 1 or len(SuppliedErrors) != len(Time)):
        raise ValueError("Flux uncertainties must align with observations.")
    Phase = Np.asarray(Phase, dtype=float)
    ModelFlux = Np.asarray(ModelFlux, dtype=float)
    if len(Time) < 50 or len(Phase) < 5 or SeedDuration <= 0:
        return None
    Order = Np.argsort(Phase)
    Phase, ModelFlux = Phase[Order], ModelFlux[Order]
    Phase, Unique = Np.unique(Phase, return_index=True)
    ModelFlux = ModelFlux[Unique]
    TemplateDepth = float(Np.max(ModelFlux) - Np.min(ModelFlux))
    if TemplateDepth <= 1e-9:
        return None
    UnitDepth = (Np.max(ModelFlux) - ModelFlux) / TemplateDepth
    CadenceSteps = Np.diff(Np.unique(Time))
    CadenceSteps = CadenceSteps[CadenceSteps > 0]
    Cadence = float(Np.median(CadenceSteps)) if CadenceSteps.size else SeedDuration / 20
    Focus = min(Period * 0.35, SeedDuration * 2.5)
    Folded = ((Time - Epoch + Period / 2) % Period) - Period / 2
    # use medians so a few unusual points do not pull each bin around.
    Width = max(SeedDuration / 45.0, Cadence / 3.0)
    Edges = Np.linspace(-Focus, Focus, max(31, min(501, int(2 * Focus / Width))) + 1)
    Bins = Np.digitize(Folded, Edges) - 1
    GlobalSigma = max(1.4826 * Np.median(Np.abs(Flux - Np.median(Flux))), 1e-8)
    X, Y, Errors, SampleGroups = [], [], [], []
    for Index in range(len(Edges) - 1):
        Members = Np.flatnonzero(Bins == Index)
        Values = Flux[Members]
        if len(Values) < 3:
            continue
        Center = float(Np.median(Values))
        Sigma = max(1.4826 * Np.median(Np.abs(Values - Center)), GlobalSigma * 0.25)
        X.append(float(Np.median(Folded[Members])))
        Y.append(Center)
        EmpiricalError = 1.253 * Sigma / Math.sqrt(len(Values))
        MeasurementError = 0.0
        if SuppliedErrors is not None:
            LocalErrors = SuppliedErrors[Members]
            if Np.all(Np.isfinite(LocalErrors)) and Np.all(LocalErrors > 0):
                MeasurementError = 1.253 * float(Np.sqrt(Np.sum(LocalErrors ** 2))) / len(Values)
        Errors.append(max(EmpiricalError, MeasurementError, 1e-8))
        # limit fit time, but keep real sample positions and exposure times.
        if len(Members) > 32:
            Members = Members[Np.linspace(0, len(Members) - 1, 32, dtype=int)]
        SampleGroups.append(Members)
    if len(X) < 20:
        return None
    X, Y, Errors = Np.asarray(X), Np.asarray(Y), Np.asarray(Errors)
    Shoulders = Np.abs(X) > SeedDuration
    Core = Np.abs(X) < SeedDuration * 0.35
    if Np.count_nonzero(Shoulders) < 6 or Np.count_nonzero(Core) < 4:
        return None
    Baseline = float(Np.median(Y[Shoulders]))
    MeasuredDepth = Baseline - float(Np.percentile(Y[Core], 20))
    if MeasuredDepth <= max(float(Np.median(Errors[Core])) * 5.0, 1e-8):
        return None
    SampleIndices = Np.concatenate(SampleGroups)
    SampleStarts = Np.r_[0, Np.cumsum([len(Group) for Group in SampleGroups])]
    SamplePhase = Folded[SampleIndices]
    SampleExposure = Exposures[SampleIndices]

    def Evaluate(Parameters):
        Scale, Shift, Depth, Level = Parameters
        ShapeAtSamples = ExposureIntegratedTemplate(
            (SamplePhase - Shift) / Scale, Phase, UnitDepth, Period / Scale,
            SampleExposure / Scale, Baseline=0.0)
        Shape = Np.asarray([Np.median(ShapeAtSamples[Left:Right])
                            for Left, Right in zip(SampleStarts[:-1], SampleStarts[1:])])
        return Level - Depth * Shape

    Initial = [1.0, 0.0, MeasuredDepth, Baseline]
    Fit = LeastSquares(lambda Pars: (Evaluate(Pars) - Y) / Errors, Initial,
                        bounds=([0.55, -SeedDuration * 0.2, 0, Baseline - MeasuredDepth],
                                [1.8, SeedDuration * 0.2, MeasuredDepth * 3, Baseline + MeasuredDepth]),
                        loss="soft_l1", max_nfev=120)
    if not Fit.success or not Np.all(Np.isfinite(Fit.x)):
        return None
    Scale, Shift, Depth, Level = Fit.x
    if Scale <= 0.56 or Scale >= 1.79 or Depth <= 0:
        return None
    Variance = float(Np.sum(Fit.fun ** 2) / max(len(X) - 4, 1))
    try:
        Covariance = Np.linalg.pinv(Fit.jac.T @ Fit.jac) * max(1.0, Variance)
        DurationError = float(Math.sqrt(max(0.0, Covariance[0, 0])) * SeedDuration)
    except Np.linalg.LinAlgError:
        DurationError = None
    FittedDuration = float(SeedDuration * Scale)
    if DurationError is None or DurationError > FittedDuration * 0.3:
        return None
    KnownCount = int(Np.count_nonzero(Np.isfinite(Exposures)))
    return {"duration": FittedDuration, "duration_uncertainty": max(DurationError, Cadence / Math.sqrt(max(Np.count_nonzero(Core), 1))),
            "epoch_shift": float(Shift), "depth": float(Depth), "baseline": float(Level),
            "bin_count": len(X), "representative_sample_count": len(SampleIndices), "reduced_chi_squared": Variance,
            "method": "robust conditional template fit at observed exposure midpoints",
            "exposure": {"known_rows": KnownCount, "unknown_rows": len(Time) - KnownCount,
                "unit": "seconds", "cadence_is_exposure": False,
                "integration": "exact periodic piecewise-linear template integral for declared finite durations; instantaneous for zero or unknown",
                "unknown_policy": "instantaneous approximation; exposure smearing uncertainty is not included"},
            "uncertainty_basis": "local Jacobian, empirical/input-error bin uncertainties and cadence floor; conditional on period, template, and declared exposure; excludes unknown exposure systematics"}


#MARK: tls funcs
def RunTlsSearch(Time, Flux, Options, ProgressCallback=None, **LegacyOptions):
    ProgressCallback = LegacyOptions.pop("progress_callback", ProgressCallback)
    if LegacyOptions:
        raise TypeError(f"Unknown TLS options: {', '.join(LegacyOptions)}")
    if Transitleastsquares is None:
        Detail = f" ({TLS_IMPORT_ERROR})" if TLS_IMPORT_ERROR else ""
        raise ValueError(
            "TLS mode requires the transitleastsquares package. "
            "Install the project requirements and try again." + Detail
        )

    Time = Np.asarray(Time, dtype=float)
    Flux = Np.asarray(Flux, dtype=float)
    if Time.size < 20 or Flux.size != Time.size:
        raise ValueError("TLS needs at least 20 matching time/flux samples.")

    TimeOrigin = float(Time[0])
    RelativeTime = Time - TimeOrigin
    SuppliedUncertainty = Options.get("_normalized_flux_uncertainty")
    Uncertainty = Np.asarray(SuppliedUncertainty, dtype=float) if SuppliedUncertainty is not None else None
    if Uncertainty is not None and Uncertainty.size == Time.size and Np.all(Np.isfinite(Uncertainty)) and Np.all(Uncertainty > 0):
        Model = Transitleastsquares(RelativeTime, Flux, dy=Uncertainty, verbose=False)
    else:
        Model = Transitleastsquares(RelativeTime, Flux, verbose=False)

    Kwargs = {
        "period_min": float(Options["period_min"]),
        "period_max": float(Options["period_max"]),
        "n_transits_min": int(Options.get("tls_min_transits", 3)),
        "transit_template": Options.get("tls_template", "default"),
        "oversampling_factor": int(Options.get("tls_oversampling", 3)),
        "duration_grid_step": float(Options.get("tls_duration_grid_step", 1.1)),
        "transit_depth_min": float(Options.get("tls_min_depth_ppm", 10.0)) / 1000000.0,
        "use_threads": int(Options.get("tls_threads", 4)),
        "show_progress_bar": False,
        "verbose": False,
    }

    #MARK: stellar priors
    StellarRadius = FiniteNumber(Options.get("stellar_radius"))
    StellarMass = FiniteNumber(Options.get("stellar_mass"))
    if StellarRadius is not None:
        Kwargs.update({
            "R_star": StellarRadius,
            "R_star_min": max(0.1, StellarRadius * 0.7),
            "R_star_max": StellarRadius * 1.3,
        })
    if StellarMass is not None:
        Kwargs.update({
            "M_star": StellarMass,
            "M_star_min": max(0.01, StellarMass * 0.7),
            "M_star_max": StellarMass * 1.3,
        })

    LimbU1 = FiniteNumber(Options.get("limb_darkening_u1"))
    LimbU2 = FiniteNumber(Options.get("limb_darkening_u2"))
    if LimbU1 is not None and LimbU2 is not None:
        Kwargs["u"] = [LimbU1, LimbU2]
        Kwargs["limb_dark"] = "quadratic"

    #MARK: tls funcs
    with MeasuredTlsProgress(ProgressCallback) as ReportsTrials:
        Kwargs["show_progress_bar"] = ReportsTrials
        Results = Model.power(**Kwargs)
    Period = FiniteNumber(getattr(Results, "period", None))
    Duration = FiniteNumber(getattr(Results, "duration", None))
    TransitTimeRelative = FiniteNumber(getattr(Results, "T0", None))
    if Period is None or Duration is None or TransitTimeRelative is None or Period <= 0 or Duration <= 0:
        raise ValueError(
            "TLS did not fit a valid transit. Try a smaller TLS minimum depth, "
            "wider period bounds, or different stellar priors."
        )

    #MARK: period peaks
    Periods = Np.asarray(getattr(Results, "periods", []), dtype=float)
    Lower, Upper = float(Options["period_min"]), float(Options["period_max"])
    Tolerance = max(1e-10, max(abs(Lower), abs(Upper)) * 1e-10)
    if (Period < Lower - Tolerance or Period > Upper + Tolerance
            or Np.any(~Np.isfinite(Periods))
            or Np.any(Periods < Lower - Tolerance) or Np.any(Periods > Upper + Tolerance)):
        # reference tls 1.32 can fall back to its default grid when a requested
        # grid is too small, dropping the caller's bounds in the recursive call.
        raise ValueError("TLS generated periods outside requested bounds; widen the period bounds or increase TLS oversampling and try again.")
    ActualPeriodBounds = {"minimum": float(Np.min(Periods)) if Periods.size else Period,
                            "maximum": float(Np.max(Periods)) if Periods.size else Period,
                            "count": int(Periods.size)}
    power = Np.asarray(getattr(Results, "power", []), dtype=float)
    PowerRaw = Np.asarray(getattr(Results, "power_raw", []), dtype=float)
    SpectrumSize = min(Periods.size, power.size)
    Periods = Periods[:SpectrumSize]
    power = power[:SpectrumSize]
    PowerRaw = PowerRaw[:SpectrumSize]
    SelectedIndex = int(Np.nanargmin(Np.abs(Periods - Period))) if Periods.size else None
    Keep = CompactIndices(power, SelectedIndex=SelectedIndex) if Periods.size else Np.asarray([], dtype=int)

    RawModelTime = Np.asarray(getattr(Results, "model_lightcurve_time", []), dtype=float)
    RawModelFlux = Np.asarray(getattr(Results, "model_lightcurve_model", []), dtype=float)
    TransitTimesRelative = FiniteList(getattr(Results, "transit_times", []))
    ModelTime, ModelFlux = CompactModel(RawModelTime, RawModelFlux)
    FoldedPhase = Np.asarray(getattr(Results, "model_folded_phase", []), dtype=float)
    FoldedModel = Np.asarray(getattr(Results, "model_folded_model", []), dtype=float)
    FoldedPhaseDays = (FoldedPhase - 0.5) * Period if FoldedPhase.size else FoldedPhase
    EngineDuration = Duration
    FoldedEngineDuration = DurationFromFoldedModel(FoldedPhaseDays, FoldedModel, Period)
    UnfoldedPhaseDays, UnfoldedModel = RepresentativeUnfoldedTransit(
        RawModelTime,
        RawModelFlux,
        TransitTimesRelative,
        Period,
    )
    UnfoldedModelDuration = DurationFromFoldedModel(
        UnfoldedPhaseDays,
        UnfoldedModel,
        Period,
    )
    FoldedContactSamples = ModelContactSampleCount(FoldedModel)
    UnfoldedContactSamples = ModelContactSampleCount(UnfoldedModel)
    # gaps can leave the unfolded cycle with very few points.
    # use the engine curve with more actual transit detail before rescaling.
    if FoldedEngineDuration is not None and (UnfoldedModelDuration is None
                                               or FoldedContactSamples >= UnfoldedContactSamples):
        PayloadPhase = FoldedPhaseDays
        PayloadFlux = FoldedModel
        TemplateSource = "engine folded template"
    elif UnfoldedModelDuration is not None:
        PayloadPhase = UnfoldedPhaseDays
        PayloadFlux = UnfoldedModel
        TemplateSource = "engine unfolded cycle"
    else:
        PayloadPhase = FoldedPhaseDays
        PayloadFlux = FoldedModel
        TemplateSource = "engine folded fallback"

    #MARK: model shape
    FillFactor = SamplingFillFactor(RelativeTime)
    UncompressedDuration = (
        EngineDuration / FillFactor
        if FillFactor is not None and FillFactor > 0
        else None
    )
    if (
        UncompressedDuration is not None
        and Math.isfinite(UncompressedDuration)
        and 0 < UncompressedDuration < Period * 0.5
    ):
        CorrectedPhase, CorrectedFlux = RescaleFoldedModelDuration(
            PayloadPhase,
            PayloadFlux,
            UncompressedDuration,
            Period,
        )
        CorrectedModelDuration = DurationFromFoldedModel(
            CorrectedPhase,
            CorrectedFlux,
            Period,
        )
    else:
        CorrectedPhase = Np.asarray([], dtype=float)
        CorrectedFlux = Np.asarray([], dtype=float)
        CorrectedModelDuration = None

    if CorrectedModelDuration is not None:
        Duration = UncompressedDuration
        PayloadPhase = CorrectedPhase
        PayloadFlux = CorrectedFlux
        DurationSource = "TLS duration with sampling-gap compression removed"
    elif UnfoldedModelDuration is not None:
        Duration = UnfoldedModelDuration
        # the unfolded curve can still tell us the width when its shape is sparse.
        if TemplateSource == "engine folded template":
            PayloadPhase, PayloadFlux = RescaleFoldedModelDuration(
                PayloadPhase, PayloadFlux, Duration, Period)
        DurationSource = "unfolded TLS model"
    else:
        if FoldedEngineDuration is not None:
            Duration = FoldedEngineDuration
        DurationSource = "folded TLS model fallback"

    #MARK: core stuffs
    SearchSde = FiniteNumber(getattr(Results, "SDE", None))
    ObservedRefinement = (
        ObservedPhaseFoldedDuration(
            RelativeTime,
            Flux,
            Period,
            TransitTimeRelative,
            Duration,
        )
        if SearchSde is not None and SearchSde >= 5.0
        else None
    )
    # keep the threshold width for comparison; do not use it to force a wider fit.
    ObservedFit = (
        FitObservedModelDuration(RelativeTime, Flux, Period, TransitTimeRelative,
                                    Duration, PayloadPhase, PayloadFlux,
                                    ExposureSeconds=(Options.get("exposure_seconds") if Options.get("exposure_seconds") is not None
                                                      else Options.get("_exposure_seconds")),
                                    FluxUncertainty=Uncertainty)
        if SearchSde is not None and SearchSde >= 7.0 else None
    )
    ObservedModelDuration = None
    if ObservedFit is not None:
        FittedPhase, FittedFlux = RescaleFoldedModelDuration(
            PayloadPhase, PayloadFlux, ObservedFit["duration"], Period)
        OldDepth = float(Np.max(FittedFlux) - Np.min(FittedFlux))
        if OldDepth > 0:
            FittedFlux = ObservedFit["baseline"] - (Np.max(FittedFlux) - FittedFlux) * ObservedFit["depth"] / OldDepth
        Duration = ObservedFit["duration"]
        PayloadPhase, PayloadFlux = FittedPhase, FittedFlux
        TransitTimeRelative += ObservedFit["epoch_shift"]
        TransitTimesRelative = [Value + ObservedFit["epoch_shift"] for Value in TransitTimesRelative]
        ObservedModelDuration = DurationFromFoldedModel(PayloadPhase, PayloadFlux, Period)
        DurationSource = ("observed exposure-integrated physical template fit"
                           if ObservedFit["exposure"]["unknown_rows"] == 0
                           else "observed physical template fit; unknown exposures approximated as instantaneous")
    ModelFoldedPhase, ModelFoldedFlux = CompactFoldedTransitModel(PayloadPhase, PayloadFlux)

    #MARK: run progress
    TransitTimes = [TimeOrigin + Value for Value in TransitTimesRelative]
    TransitFluxLevels = FiniteList(getattr(Results, "transit_depths", []))
    TransitDepthFractions = [max(0.0, 1.0 - Value) for Value in TransitFluxLevels]
    DepthMean = getattr(Results, "depth_mean", None)
    DepthMeanFlux = None
    DepthMeanUncertainty = None
    if isinstance(DepthMean, (tuple, list, Np.ndarray)) and len(DepthMean) >= 2:
        DepthMeanFlux = FiniteNumber(DepthMean[0])
        DepthMeanUncertainty = FiniteNumber(DepthMean[1])
    BottomFlux = FiniteNumber(getattr(Results, "depth", None))

    return {
        "period": Period,
        "period_uncertainty": FiniteNumber(getattr(Results, "period_uncertainty", None)),
        "duration": Duration,
        "engine_duration": EngineDuration,
        "folded_engine_duration": FoldedEngineDuration,
        "unfolded_model_duration": UnfoldedModelDuration,
        "sampling_fill_factor": FillFactor,
        "uncompressed_duration": UncompressedDuration,
        "observed_duration_refinement": ObservedRefinement,
        "duration_fit": ObservedFit,
        "duration_uncertainty": ObservedFit.get("duration_uncertainty") if ObservedFit else None,
        "duration_quality": "conditional_fit" if ObservedFit else "template_estimate",
        "duration_disagreement_fraction": (
            abs(ObservedRefinement["duration"] - Duration) / Duration
            if ObservedRefinement is not None else None
        ),
        "observed_model_duration": ObservedModelDuration,
        "duration_source": DurationSource,
        "template_source": TemplateSource,
        "template_resolution": {"engine_folded_contact_samples": FoldedContactSamples,
                                "engine_unfolded_contact_samples": UnfoldedContactSamples,
                                "retained_contact_samples": ModelContactSampleCount(PayloadFlux),
                                "transported_contact_samples": ModelContactSampleCount(ModelFoldedFlux),
                                "policy": "retain the independently generated engine template with more real in-transit samples before rescaling"},
        "transit_time": TimeOrigin + TransitTimeRelative,
        "power": FiniteNumber(getattr(Results, "SDE_raw", None)),
        "sde": FiniteNumber(getattr(Results, "SDE", None)),
        "sde_raw": FiniteNumber(getattr(Results, "SDE_raw", None)),
        "fap": FiniteNumber(getattr(Results, "FAP", None)),
        "snr": FiniteNumber(getattr(Results, "snr", None)),
        "rp_rs": FiniteNumber(getattr(Results, "rp_rs", None)),
        "odd_even_mismatch_sigma": FiniteNumber(getattr(Results, "odd_even_mismatch", None)),
        "chi_squared": FiniteNumber(getattr(Results, "chi2_min", None)),
        "reduced_chi_squared": FiniteNumber(getattr(Results, "chi2red_min", None)),
        "transit_count": FiniteInt(getattr(Results, "transit_count", None)),
        "distinct_transit_count": FiniteInt(getattr(Results, "distinct_transit_count", None)),
        "empty_transit_count": FiniteInt(getattr(Results, "empty_transit_count", None)),
        "transit_times": TransitTimes,
        "per_transit_count": FiniteList(getattr(Results, "per_transit_count", [])),
        "transit_depth_fractions": TransitDepthFractions,
        "transit_depth_uncertainties": FiniteList(getattr(Results, "transit_depths_uncertainties", [])),
        "snr_per_transit": FiniteList(getattr(Results, "snr_per_transit", [])),
        "snr_pink_per_transit": FiniteList(getattr(Results, "snr_pink_per_transit", [])),
        "depth_fraction": ObservedFit["depth"] if ObservedFit else (None if BottomFlux is None else max(0.0, 1.0 - BottomFlux)),
        "depth_mean_fraction": None if DepthMeanFlux is None else max(0.0, 1.0 - DepthMeanFlux),
        "depth_mean_uncertainty": DepthMeanUncertainty,
        "candidates": DistinctPeriodCandidates(Periods, power, PowerRaw),
        "periodogram": {
            "periods": NullableList(Periods[Keep]),
            "power": NullableList(PowerRaw[Keep] if PowerRaw.size >= SpectrumSize else power[Keep]),
            "sde": NullableList(power[Keep]),
            "raw_sde": NullableList(PowerRaw[Keep]) if PowerRaw.size >= SpectrumSize else [],
            "method": "TLS",
            "selected_period": Period,
            "point_count": int(SpectrumSize),
            "shown_count": int(Keep.size),
        },
        "model": {
            "time": ModelTime,
            "flux": ModelFlux,
            "folded_phase_days": ModelFoldedPhase,
            "folded_flux": ModelFoldedFlux,
            "duration_source": DurationSource,
            "template_source": TemplateSource,
        },
        "engine": TlsEngineVersion(),
        "parameters": Kwargs,
        "actual_period_grid": ActualPeriodBounds,
        "effective_stellar_priors": {
            "radius": {"value": Kwargs.get("R_star", 1.0), "min": Kwargs.get("R_star_min", 0.13), "max": Kwargs.get("R_star_max", 3.5), "source": "explicit" if StellarRadius is not None else "TLS default"},
            "mass": {"value": Kwargs.get("M_star", 1.0), "min": Kwargs.get("M_star_min", 0.1), "max": Kwargs.get("M_star_max", 1.0), "source": "explicit" if StellarMass is not None else "TLS default"},
            "limb_darkening": {"coefficients": [0.0] if Kwargs["transit_template"] == "box" else Kwargs.get("u", [0.4804, 0.1867]),
                               "law": "linear" if Kwargs["transit_template"] == "box" else "quadratic",
                               "source": "box template override" if Kwargs["transit_template"] == "box" else ("explicit" if LimbU1 is not None else "TLS default")},
        },
    }


#MARK: old calls
def run_tls_search(time, flux, options, progress_callback=None):
    return RunTlsSearch(time, flux, options, ProgressCallback=progress_callback)
