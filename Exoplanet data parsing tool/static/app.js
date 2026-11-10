//MARK: core stuffs
const CurveFilesInput = document.getElementById("CurveFilesInput");
const FileDropThing = document.getElementById("FileDropThing");
const AnalyzeButton = document.getElementById("AnalyzeButton");
const CancelAnalysisButton = document.getElementById("CancelAnalysisButton");
const StatusEl = document.getElementById("Status");
const AnalysisProgressEl = document.getElementById("AnalysisProgress");
const RunStatusSection = document.getElementById("RunStatusSection");
const AssessmentEl = document.getElementById("Assessment");
const MetricsEl = document.getElementById("Metrics");
const WarningsEl = document.getElementById("Warnings");
const PeriodCandidatesEl = document.getElementById("PeriodCandidates");
const ChartTitleEl = document.getElementById("ChartTitle");
const SubtitleEl = document.getElementById("Subtitle");
const SessionIndicatorEl = document.getElementById("SessionIndicator");
const SaveLocationFormEl = document.getElementById("SaveLocationForm");
const CacheFolderThing = document.getElementById("CacheFolderThing");
const SaveLocationButtonEl = document.getElementById("SaveLocationButton");
const SaveLocationFileEl = document.getElementById("SaveLocationFile");
const CachePickThing = document.getElementById("CachePickThing");
const LoadCacheButtonEl = document.getElementById("LoadCacheButton");
const RefreshCachesButtonEl = document.getElementById("RefreshCachesButton");
const LoadCacheStatusEl = document.getElementById("LoadCacheStatus");
const EmptyEl = document.getElementById("Empty");
const RowsEl = document.getElementById("TransitRows");
const FluxChart = document.getElementById("FluxChart");
const FluxPen = FluxChart.getContext('2d');
const ViewButtons = [...document.querySelectorAll(".ViewButton[data-view]") ];
const StrictnessInput = document.getElementById("StrictnessInput");
const StrictnessValue = document.getElementById("StrictnessValue");
const SmoothingInput = document.getElementById("SmoothingInput");
const SmoothingValue = document.getElementById("SmoothingValue");
const SearchModeInput = document.getElementById("SearchModeInput");
const TlsOptionsEl = document.getElementById("TlsOptions");
const TlsTemplateInput = document.getElementById("TlsTemplateInput");
const StellarRadiusInput = document.getElementById("StellarRadiusInput");
const StellarMassInput = document.getElementById("StellarMassInput");
const LimbDarkeningU1Input = document.getElementById("LimbDarkeningU1Input");
const LimbDarkeningU2Input = document.getElementById("LimbDarkeningU2Input");
const TlsOversamplingInput = document.getElementById("TlsOversamplingInput");
const TlsMinTransitsInput = document.getElementById("TlsMinTransitsInput");
const TlsMinDepthPpmInput = document.getElementById("TlsMinDepthPpmInput");
const TlsThreadsInput = document.getElementById("TlsThreadsInput");
const TlsDurationGridStepInput = document.getElementById("TlsDurationGridStepInput");
const MinDepthInput = document.getElementById("MinDepthInput");
const MinDurationInput = document.getElementById("MinDurationInput");
const MaxDurationInput = document.getElementById("MaxDurationInput");
const MinPeriodInput = document.getElementById("MinPeriodInput");
const MaxPeriodInput = document.getElementById("MaxPeriodInput");
const ResetDetectionButton = document.getElementById("ResetDetectionButton");
const ExportCsvButton = document.getElementById("ExportCsvButton");
const ExportPngButton = document.getElementById("ExportPngButton");
const ExportJsonButton = document.getElementById("ExportJsonButton");
const ExportAnalysisPdfButton = document.getElementById("ExportAnalysisPdfButton");
const ExportBatchPdfButton = document.getElementById("ExportBatchPdfButton");
const ResultSelect = document.getElementById("ResultSelect");
const BatchCount = document.getElementById("BatchCount");
const CurvePickThing = document.getElementById("CurvePickThing");
const BatchPickerButton = document.getElementById("BatchPickerButton");
const BatchPickerTitle = document.getElementById("BatchPickerTitle");
const BatchPickerMeta = document.getElementById("BatchPickerMeta");
const BatchPickerList = document.getElementById("BatchPickerList");
const TlsMaxSignalsInput = document.getElementById("TlsMaxSignalsInput");
const PerFileSettingsInput = document.getElementById("PerFileSettings");
const BatchSortInput = document.getElementById("BatchSort");
const ReconnectJobButton = document.getElementById("ReconnectJobButton");
const MetadataEl = document.getElementById("AnalysisMetadata");
const SignalPickThing = document.getElementById("SignalPickThing");
const ShowModelInput = document.getElementById("ShowModel");
const ShowLocalDipsInput = document.getElementById("ShowLocalDips");
const PhaseScopeInput = document.getElementById("PhaseScope");
const StackEventInput = document.getElementById("StackEvent");
const StackGroupInput = document.getElementById("StackGroup");
const StackIsolateInput = document.getElementById("StackIsolate");
const StackMedianInput = document.getElementById("StackMedian");
const StackRecenterInput = document.getElementById("StackRecenter");
const CsvTimeFormatInput = document.getElementById("CsvTimeFormat");
const CsvTimeScaleInput = document.getElementById("CsvTimeScale");
const CsvTimeUnitInput = document.getElementById("CsvTimeUnit");
const ExposureSecondsInput = document.getElementById("ExposureSecondsInput");

//MARK: search controls
//  reset and restored sessions should use the same defaults.
const DetectionControls = [
  {key : 'strictness', input : StrictnessInput, defaultValue : '1', read : Number},
  {key : 'smoothing', input : SmoothingInput, defaultValue : '1', read : Number},
  {key : 'searchMode', input : SearchModeInput, defaultValue : 'tls', read : String},
  {key : 'tlsTemplate', input : TlsTemplateInput, defaultValue : 'default', read : String},
  {key : 'stellarRadius', input : StellarRadiusInput, defaultValue : ''},
  {key : 'stellarMass', input : StellarMassInput, defaultValue : ''},
  {key : 'limbDarkeningU1', input : LimbDarkeningU1Input, defaultValue : ''},
  {key : 'limbDarkeningU2', input : LimbDarkeningU2Input, defaultValue : ''},
  {key : 'tlsOversampling', input : TlsOversamplingInput, defaultValue : '3'},
  {key : 'tlsMinTransits', input : TlsMinTransitsInput, defaultValue : '3'},
  {key : 'tlsMinDepthPpm', input : TlsMinDepthPpmInput, defaultValue : '10'},
  {key : 'tlsThreads', input : TlsThreadsInput, defaultValue : '4'},
  {key : 'tlsDurationGridStep', input : TlsDurationGridStepInput, defaultValue : '1.1'},
  {
    key : 'tlsMaxSignals',
    input : TlsMaxSignalsInput,
    defaultValue : '1',
    read : Value => NullableNumber(Value) ?? 1
  },
  {key : 'csvTimeFormat', input : CsvTimeFormatInput, defaultValue : 'unknown', read : String},
  {key : 'csvTimeScale', input : CsvTimeScaleInput, defaultValue : 'unknown', read : String},
  {key : 'csvTimeUnit', input : CsvTimeUnitInput, defaultValue : 'days', read : String},
  {key : 'exposureSeconds', input : ExposureSecondsInput, defaultValue : ''},
  {key : 'minDepth', input : MinDepthInput, defaultValue : ''},
  {key : 'minDuration', input : MinDurationInput, defaultValue : ''},
  {key : 'maxDuration', input : MaxDurationInput, defaultValue : ''},
  {key : 'minPeriod', input : MinPeriodInput, defaultValue : ''},
  {key : 'maxPeriod', input : MaxPeriodInput, defaultValue : ''},
];

const AppShell = document.querySelector('main');
const MaxBatchFiles = 100;
const JobPollIntervalMs = 750;
const DefaultSidebarWidth = 390;
const MinSidebarWidth = 320;
const MaxSidebarWidth = 560;
const SessionQueryKey = 'session';
const SessionIdPattern = /^[a-zA-Z0-9_-]{8,80}$/;
const SessionSaveDelayMs = 350;
const SessionViews =
    new Set([ 'zoom', 'clean', 'raw', 'phase', 'stack', 'periodogram', 'audit', 'comparison' ]);
//MARK: current run
let CurveFiles = [];
let CurrFile = null;
let FileResults = [];
let CurrFileIndex = -1;
let BatchInProgress = false;
let RunningJobId = null;
let AnalysisCancelRequested = false;
let ProgressTimer = null;
let ProgressValues = [];
let ProgressElapsedStates = [];
let CurrResult = null;
let MainResult = null;
let RunningFileIndex = null;
let BatchRunId = null;
let PendingBatchFiles = [];
let JobConnectionLost = false;
let RequestId = null;
let ResultViewports = new Map();
let CurrView = 'zoom';
let CurrViewport = null;
let DragState = null;
let HoverThingy = null;
let SessionId = null;
let SessionInitialized = false;
let RestoringSession = false;
let SessionSaveTimer = null;
let SessionSaveChain = Promise.resolve();
let SessionReadyPromise = null;
let KnownSessionCaches = [];
const ChartPad = {
  left : 72,
  right : 48,
  top : 42,
  bottom : 66
};

//MARK: curve funcs
//  run a curve, show its results, then draw the selected view.
//MARK: run funcs
async function RunCurve(CurveFile, Options, OnJobUpdate = () =>
{
}, ExistingJobId = null)
{
  // keep the same request id if an upload response gets lost.
  RequestId = ExistingJobId ? (RequestId || `${BatchRunId}:${RunningFileIndex}`)
                            : `${BatchRunId}:${RunningFileIndex}`;
  await SaveRunNow();
  const UploadForm = new FormData();
  if (!ExistingJobId)
    UploadForm.append('datafile', CurveFile);
  UploadForm.append('batchId', BatchRunId || '');
  UploadForm.append('analysisRequestId', RequestId);
  AppendDetectionOptions(UploadForm, Options);
  //MARK: submit job
  let SubmittedJob = {job_id : ExistingJobId, status : 'running'};
  if (!ExistingJobId)
  {
    let Reply;
    for (let Attempt = 0; Attempt < 3; Attempt++)
    {
      try
      {
        Reply = await fetch('/analysis-jobs', {method : 'POST', body : UploadForm});
        SubmittedJob = await ReadJsonResponse(Reply);
        break;
      }
      catch (RunError)
      {
        if (Attempt === 2)
        {
          const Lookup = await LookupRequest(RequestId).catch(() => null);
          if (Lookup)
          {
            SubmittedJob = Lookup;
            Reply = {ok : true};
            break;
          }
          JobConnectionLost = true;
          throw new AnalysisDisconnectedError(
              'Submission response was lost. Reconnect to resolve this request before starting another search.');
        }
        await Wait(JobPollIntervalMs);
      }
    }
    if (!Reply.ok)
      throw new Error(SubmittedJob.error || 'Analysis could not be started.');
  }
  if (!SubmittedJob.job_id)
    throw new Error('Server did not return an analysis job ID.');

  const JobId = SubmittedJob.job_id;
  RunningJobId = JobId;
  JobConnectionLost = false;
  ReconnectJobButton.hidden = true;
  await SaveRunNow();
  CancelAnalysisButton.disabled = false;
  OnJobUpdate(SubmittedJob);

  try
  {
    if (AnalysisCancelRequested)
    {
      await RequestJobCancellation(JobId);
      throw new AnalysisCancelledError();
    }

    //MARK: wait for job
    let FailedPolls = 0;
    while (true)
    {
      let JobResponse;
      let Job;
      try
      {
        JobResponse = await fetch(`/analysis-jobs/${encodeURIComponent(JobId)}`, {cache : 'no-store'});
        Job = await ReadJsonResponse(JobResponse);
        if (!JobResponse.ok)
          throw new Error(Job.error || 'Could not read analysis status.');
        FailedPolls = 0;
      }
      catch (RunError)
      {
        FailedPolls += 1;
        if (FailedPolls >= 5)
        {
          JobConnectionLost = true;
          throw new AnalysisDisconnectedError(
              `Connection lost. Reconnect to the existing job; it may still be running. ${RunError.message}`);
        }
        await Wait(JobPollIntervalMs);
        continue;
      }

      OnJobUpdate(Job);
      //MARK: finished curve
      if (Job.status === 'completed')
      {
        const Payload = Job.result;
        if (!Payload)
          throw new Error('Completed analysis did not include a result.');
        Payload.source_file = CurveFile.name;
        return Payload;
      }
      if (Job.status === 'failed')
        throw new Error(Job.error || 'Analysis failed.');
      if (Job.status === 'cancelled')
        throw new AnalysisCancelledError();
      if (AnalysisCancelRequested && Job.status !== 'cancelling')
      {
        await RequestJobCancellation(JobId);
        throw new AnalysisCancelledError();
      }
      await Wait(JobPollIntervalMs);
    }
  }
  finally
  {
    if (RunningJobId === JobId && !JobConnectionLost)
    {
      RunningJobId = null;
      RequestId = null;
    }
  }
}

//MARK: show results
function ShowCurveResult(Result)
{
  EmptyEl.style.display = 'none';
  RenderMetadata();
  RenderSignalPicker();
  RenderStackEvents();
  RenderMetrics();
  UpdateChartHeading();
  SyncExportButtons();
  RenderTransitRows();
  DrawFlux();
}

//MARK: plot stuffs
function DrawFlux()
{
  ResizeCanvas();
  const Geo = GetChartGeometry();
  const Width = Geo.width;
  const Height = Geo.height;
  FluxPen.clearRect(0, 0, Width, Height);
  if (!CurrResult)
    return;

  if (CurrView === 'comparison')
  {
    DrawComparisonChart(Geo);
    return;
  }

  if (CurrView === 'periodogram')
  {
    DrawPeriodogramChart(Geo);
    return;
  }

  if (CurrView === 'phase')
  {
    DrawPhaseChart(Geo);
    return;
  }

  if (CurrView === 'stack')
  {
    DrawTransitStackChart(Geo);
    return;
  }

  const Times = CurrResult.plot.time;
  const RawFlux = CurrResult.plot.raw_flux;
  const SmoothFlux = CurrResult.plot.smooth_flux;
  const Flux = CurrView === 'raw' ? RawFlux : SmoothFlux;
  if (!Times.length)
    return;

  const Pad = Geo.pad;
  const InnerW = Geo.innerW;
  const InnerH = Geo.innerH;
  const Viewport = GetViewport();
  const XMin = Viewport.xMin;
  const XMax = Viewport.xMax;
  const YMin = Viewport.yMin;
  const YMax = Viewport.yMax;
  const XScale = Value => Pad.left + ((Value - XMin) / (XMax - XMin || 1)) * InnerW;
  const YScale = Value => Pad.top + (1 - ((Value - YMin) / (YMax - YMin || 1))) * InnerH;

  FluxPen.fillStyle = '#fbfcfd';
  FluxPen.fillRect(0, 0, Width, Height);
  const AuditMetrics = CurrView === 'audit' ? CurrentAnalysisMetrics() : null;
  if (CurrView === 'audit' &&
      (!IsFiniteNumber(AuditMetrics.period) || !IsFiniteNumber(AuditMetrics.periodEpoch)))
  {
    DrawNotice('Ephemeris audit needs a recovered period and epoch.', Width, Height);
    return;
  }
  if (CurrView === 'audit')
  {
    DrawAuditPredictions(Geo, Viewport, AuditMetrics, XScale);
  }

  FluxPen.save();
  ClipToChartPlot(Geo);
  //MARK: predicted boxes
  CurrResult.transits.forEach((T, Index) =>
  {
    const BoxStart = T.start;
    const BoxEnd = T.end;
    if (BoxEnd < XMin || BoxStart > XMax)
      return;
    const Range = TransitFluxRange(T, Flux);
    if (!Range)
      return;
    const X1 = Math.max(Pad.left, XScale(BoxStart));
    const X2 = Math.min(Width - Pad.right, XScale(BoxEnd));
    const Y1 = Math.max(Pad.top, Math.min(Pad.top + InnerH, YScale(Range.high)));
    const Y2 = Math.max(Pad.top, Math.min(Pad.top + InnerH, YScale(Range.low)));
    const BoxWidth = Math.max(0.7, X2 - X1);
    const BoxTop = Math.min(Y1, Y2);
    const BoxHeight = Math.max(8, Math.abs(Y2 - Y1));
    const AuditClassification = AuditMetrics ? ClassifyTransitForEphemeris(T, AuditMetrics) : null;
    const AuditMatched = AuditClassification && AuditClassification.status === 'matched';
    const AuditOffPeriod = AuditClassification && AuditClassification.status === 'off';
    FluxPen.fillStyle = AuditMatched
                            ? 'rgba(21, 128, 61, 0.2)'
                            : (AuditOffPeriod ? 'rgba(180, 35, 24, 0.18)' : 'rgba(180, 83, 9, 0.22)');
    FluxPen.fillRect(X1, BoxTop, BoxWidth, BoxHeight);
    FluxPen.strokeStyle = AuditMatched ? 'rgba(21, 128, 61, 1)'
                                       : (AuditOffPeriod ? 'rgba(180, 35, 24, 1)' : 'rgba(180, 83, 9, 1)');
    FluxPen.lineWidth = 1.5;
    FluxPen.setLineDash(IsTentativeModel() ? [ 5, 4 ] : []);
    FluxPen.strokeRect(X1, BoxTop, BoxWidth, BoxHeight);
    FluxPen.setLineDash([]);
    FluxPen.fillStyle = AuditMatched ? '#166534' : (AuditOffPeriod ? '#991b1b' : '#8a3f06');
    FluxPen.font = '700 12px system-ui, sans-serif';
    FluxPen.textAlign = 'left';
    FluxPen.textBaseline = 'top';
    if (BoxWidth > 18 || CurrView === 'zoom')
    {
      FluxPen.fillText(`W${Index + 1}`, Math.max(Pad.left + 4, X1 + 5), Math.max(Pad.top + 4, BoxTop + 5));
    }
  });
  //MARK: local dips
  if (ShowLocalDipsInput.checked)
  {
    const Dips = MainResult?.exploratory_dips || CurrResult.exploratory_dips || [];
    FluxPen.strokeStyle = 'rgba(124,58,237,.65)';
    FluxPen.lineWidth = 1.1;
    FluxPen.setLineDash([ 3, 4 ]);
    Dips.forEach((Dip, Index) =>
    {
      if (Dip.end < Viewport.xMin || Dip.start > Viewport.xMax)
        return;
      const Range = TransitFluxRange(Dip, Flux);
      if (!Range)
        return;
      const Left = XScale(Dip.start), Right = XScale(Dip.end), Top = YScale(Range.high),
            Bottom = YScale(Range.low);
      FluxPen.strokeRect(Left, Math.min(Top, Bottom), Math.max(.7, Right - Left),
                         Math.max(2, Math.abs(Bottom - Top)));
      if (CurrView === 'zoom' && Right - Left > 12)
      {
        FluxPen.fillStyle = '#7c3aed';
        FluxPen.textAlign = 'left';
        FluxPen.font = '10px system-ui,sans-serif';
        FluxPen.fillText(`D${Index + 1}`, Left + 2, Math.min(Top, Bottom) - 3);
      }
    });
    FluxPen.setLineDash([]);
  }
  FluxPen.restore();

  DrawChartAxes(Geo, Viewport, {
    xDigits : 4,
    yDigits : 4,
    xLabel : TimeAxisLabel(),
    yLabel : CurrView === 'raw' ? 'Flux' : (CurrView === 'audit' ? 'Ephemeris audit' : 'Smoothed flux'),
  });

  FluxPen.save();
  ClipToChartPlot(Geo);
  if (CurrView !== 'raw')
  {
    FluxPen.strokeStyle = 'rgba(15,118,110,.16)';
    FluxPen.lineWidth = 1;
    DrawSeriesPath(Times, RawFlux, XScale, YScale, Viewport,
                   {breakIndices : CurrResult.plot.break_indices || [], timeSeries : true});
  }
  FluxPen.strokeStyle = CurrView === 'raw' ? '#0f766e' : '#063f3b';
  FluxPen.lineWidth = CurrView === 'raw' ? 1.2 : 2.4;
  DrawSeriesPath(Times, Flux, XScale, YScale, Viewport,
                 {breakIndices : CurrResult.plot.break_indices || [], timeSeries : true});
  if (HasTransitModel() && CurrView !== 'raw')
  {
    ApplyModelStyle(1.8);
    DrawSeriesPath(CurrResult.transit_model.time, CurrResult.transit_model.flux, XScale, YScale, Viewport,
                   {timeSeries : true});
  }
  FluxPen.restore();

  if (CurrView === 'audit')
  {
    DrawAuditResiduals(Geo, Viewport, AuditMetrics, XScale);
    DrawAuditLegend(Geo, AuditMetrics);
  }

  UpdateCanvasCursor(HoverThingy);
}

//MARK: control funcs
//MARK: status colors
//  result status values stay unchanged; only their css names use capitals.
function CssTag(Value)
{
  return String(Value)
      .split(/[-_]+/)
      .filter(Boolean)
      .map(Part => Part[0].toUpperCase() + Part.slice(1))
      .join('');
}

//MARK: number checks
function NullableNumber(Value)
{
  // missing measurements should stay missing instead of turning into 0.
  if (Value === null || Value === undefined || typeof Value === 'boolean' ||
      (typeof Value === 'string' && !Value.trim()))
    return null;
  if (typeof Value !== 'number' && typeof Value !== 'string')
    return null;
  const NumericValue = Number(Value);
  return Number.isFinite(NumericValue) ? NumericValue : null;
}

//MARK: valid numbers
function IsFiniteNumber(Value)
{
  return NullableNumber(Value) !== null;
}

//MARK: duration text
function DurationLabel(Days)
{
  const Value = NullableNumber(Days);
  if (Value === null)
    return '-';
  return Math.abs(Value) < 1 / 24 ? `${Fmt(Value * 1440, 2)} min` : `${Fmt(Value * 24, 3)} h`;
}

//MARK: time reference text
function FmtReference(Value)
{
  const NumericValue = NullableNumber(Value);
  return NumericValue === null ? '-' : NumericValue.toFixed(8).replace(/\.?0+$/, '');
}

//MARK: number text
const Fmt = (Value, Digits = 6) =>
{
  if (Value === null || Value === undefined || !IsFiniteNumber(Value))
    return '-';
  const N = Number(Value);
  if (Math.abs(N) >= 1000000 || (Math.abs(N) > 0 && Math.abs(N) < 0.001))
    return N.toExponential(3);
  return Number.parseFloat(N.toFixed(Digits)).toString();
};

//MARK: percent text
const FmtPercent = Value =>
{
  if (Value === null || Value === undefined || !IsFiniteNumber(Value))
    return '-';
  const Percent = Number(Value) * 100;
  if (Percent === 0)
    return '< 1e-12%';
  if (Percent > 0 && Percent < 0.000001)
    return '< 0.000001%';
  return `${Fmt(Percent, 6)}%`;
};

//MARK: depth text
const FmtDepthPercent = Value =>
{
  if (Value === null || Value === undefined || !IsFiniteNumber(Value))
    return '-';
  return `${Fmt(Number(Value) * 100, 6)}%`;
};

//MARK: ppm text
const FmtPpm = Value =>
{
  if (Value === null || Value === undefined || !IsFiniteNumber(Value))
    return '-';
  return Fmt(Number(Value), 1);
};

//MARK: html text
function EscapeHtml(Value)
{
  return String(Value).replace(/[&<>"']/g, Character => ({
                                             '&' : '&amp;',
                                             '<' : '&lt;',
                                             '>' : '&gt;',
                                             '"' : '&quot;',
                                             "'" : '&#39;',
                                           }[Character]));
}

//MARK: mean
function Average(Values)
{
  if (!Values.length)
    return null;
  return Values.reduce((Sum, Value) => Sum + Value, 0) / Values.length;
}

//MARK: flux spread
function StandardDeviation(Values, Center = Average(Values))
{
  if (!Values.length || Center === null)
    return null;
  const Variance = Values.reduce((Sum, Value) => Sum + (Value - Center) ** 2, 0) / Values.length;
  return Math.sqrt(Variance);
}

//MARK: middle value
function Median(Values)
{
  const Clean = Values.filter(Value => Number.isFinite(Value)).sort((A, B) => A - B);
  if (!Clean.length)
    return null;
  const Middle = Math.floor(Clean.length / 2);
  return Clean.length % 2 ? Clean[Middle] : (Clean[Middle - 1] + Clean[Middle]) / 2;
}

//MARK: relative spread
function CoefficientOfVariation(Values)
{
  const Clean = Values.filter(Value => Number.isFinite(Value) && Value >= 0);
  const Center = Median(Clean);
  if (Center === null || Center <= 0 || Clean.length < 2)
    return null;
  return StandardDeviation(Clean, Average(Clean)) / Center;
}

//MARK: error function
function ErfcApprox(X)
{
  const Z = Math.abs(X);
  const T = 1 / (1 + Z / 2);
  const R =
      T * Math.exp(-Z * Z - 1.26551223 +
                   T * (1.00002368 +
                        T * (0.37409196 +
                             T * (0.09678418 +
                                  T * (-0.18628806 +
                                       T * (0.27886807 +
                                            T * (-1.13520398 +
                                                 T * (1.48851587 + T * (-0.82215223 + T * 0.17087277)))))))));
  return X >= 0 ? R : 2 - R;
}

//MARK: chi-square p-value
function ChiSquareOneDegreePValue(DeltaChiSquared)
{
  if (!Number.isFinite(DeltaChiSquared) || DeltaChiSquared < 0)
    return null;
  return Math.max(0, Math.min(1, ErfcApprox(Math.sqrt(DeltaChiSquared / 2))));
}

//MARK: observed ranges
function ObservationRangesForResult(Result, FallbackDomain = null)
{
  const SegmentRanges = Result?.normalization?.segment_time_ranges || [];
  const Ranges = SegmentRanges
                     .map(Segment =>
                     {
                       const Start = Number(Segment.start_day ?? Segment.start);
                       const End = Number(Segment.end_day ?? Segment.end);
                       if (!Number.isFinite(Start) || !Number.isFinite(End))
                         return null;
                       return Start <= End ? {start : Start, end : End} : {start : End, end : Start};
                     })
                     .filter(Boolean);
  if (Ranges.length)
    return Ranges;

  const Domain = FallbackDomain || Result?.domain;
  const Start = Number(Domain?.time_min);
  const End = Number(Domain?.time_max);
  return Number.isFinite(Start) && Number.isFinite(End)
             ? [ {start : Math.min(Start, End), end : Math.max(Start, End)} ]
             : [];
}

//MARK: covered cycles
function EphemerisCyclesInObservedRanges(Period, Epoch, Tolerance, ObservedRanges)
{
  const PeriodValue = Number(Period);
  const EpochValue = Number(Epoch);
  const ToleranceValue = Number(Tolerance);
  if (!Number.isFinite(PeriodValue) || PeriodValue <= 0 || !Number.isFinite(EpochValue) ||
      !Number.isFinite(ToleranceValue))
  {
    return new Set();
  }

  const Cycles = new Set();
  (ObservedRanges || []).forEach(Range =>
  {
    const Start = Number(Range.start);
    const End = Number(Range.end);
    if (!Number.isFinite(Start) || !Number.isFinite(End))
      return;
    const FirstCycle = Math.ceil((Math.min(Start, End) - ToleranceValue - EpochValue) / PeriodValue);
    const LastCycle = Math.floor((Math.max(Start, End) + ToleranceValue - EpochValue) / PeriodValue);
    if (LastCycle < FirstCycle)
      return;
    for (let Cycle = FirstCycle; Cycle <= LastCycle; Cycle += 1)
    {
      Cycles.add(Cycle);
    }
  });
  return Cycles;
}

//MARK: sidebar stuffs
function FinishAccordionAnimation(Section, Body)
{
  Section.classList.remove("IsOpening", "IsClosing");
  delete Section.dataset.animating;
  Body.style.height = '';
  Body.style.opacity = '';
  Body.style.transform = '';
  Body.style.marginTop = '';
}

//MARK: open panel
function AnimateAccordionOpen(Section, Body)
{
  Section.open = true;
  Section.dataset.animating = 'true';
  Section.classList.add("IsOpening");
  Section.classList.remove("IsClosing");
  Body.style.height = '0px';
  Body.style.opacity = '0';
  Body.style.transform = 'translateY(-4px)';
  Body.style.marginTop = '0';
  Body.offsetHeight;

  window.requestAnimationFrame(() =>
  {
    Body.style.height = `${Body.scrollHeight}px`;
    Body.style.opacity = '1';
    Body.style.transform = 'translateY(0)';
    Body.style.marginTop = '9px';
  });

  let Complete = false;
  const Finish = () =>
  {
    if (Complete)
      return;
    Complete = true;
    Body.removeEventListener('transitionend', OnTransitionEnd);
    FinishAccordionAnimation(Section, Body);
  };
  const OnTransitionEnd = UiEvent =>
  {
    if (UiEvent.target === Body && UiEvent.propertyName === 'height')
      Finish();
  };
  Body.addEventListener('transitionend', OnTransitionEnd);
  window.setTimeout(Finish, 360);
}

//MARK: close panel
function AnimateAccordionClose(Section, Body)
{
  Section.dataset.animating = 'true';
  Section.classList.add("IsClosing");
  Section.classList.remove("IsOpening");
  Body.style.height = `${Body.scrollHeight}px`;
  Body.style.opacity = '1';
  Body.style.transform = 'translateY(0)';
  Body.style.marginTop = '9px';
  Body.offsetHeight;

  window.requestAnimationFrame(() =>
  {
    Body.style.height = '0px';
    Body.style.opacity = '0';
    Body.style.transform = 'translateY(-4px)';
    Body.style.marginTop = '0';
  });

  let Complete = false;
  const Finish = () =>
  {
    if (Complete)
      return;
    Complete = true;
    Body.removeEventListener('transitionend', OnTransitionEnd);
    Section.open = false;
    FinishAccordionAnimation(Section, Body);
  };
  const OnTransitionEnd = UiEvent =>
  {
    if (UiEvent.target === Body && UiEvent.propertyName === 'height')
      Finish();
  };
  Body.addEventListener('transitionend', OnTransitionEnd);
  window.setTimeout(Finish, 360);
}

//MARK: panel clicks
function SetupAccordions()
{
  const ReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  document.querySelectorAll(".AccordionSection").forEach(Section =>
  {
    const Summary = Section.querySelector('summary');
    const Body = Section.querySelector(".AccordionBody");
    if (!Summary || !Body)
      return;

    Summary.addEventListener('click', UiEvent =>
    {
      if (ReducedMotion.matches)
        return;
      UiEvent.preventDefault();
      if (Section.dataset.animating === 'true')
        return;
      if (Section.open)
      {
        AnimateAccordionClose(Section, Body);
      }
      else
      {
        AnimateAccordionOpen(Section, Body);
      }
    });
  });
}

SetupAccordions();

//MARK: open a section
function OpenAccordionSection(Section)
{
  if (!Section || Section.open || Section.dataset.animating === 'true')
    return;
  const Body = Section.querySelector(".AccordionBody");
  if (!Body || window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  {
    Section.open = true;
    return;
  }
  AnimateAccordionOpen(Section, Body);
}

//MARK: show run status
function ShowRunStatus()
{
  OpenAccordionSection(RunStatusSection);
}

//MARK: filename width
function SidebarWidthForFiles(Files)
{
  const Names = Array.from(Files || []).map(CurveFile => String(CurveFile.name || '')).filter(Boolean);
  if (!Names.length)
    return DefaultSidebarWidth;

  const LongestName = Math.max(...Names.map(Name => Name.length));
  const LongestSegment =
      Math.max(...Names.flatMap(Name => (Name.split(/[\s._()-]+/).map(Part => Part.length))));
  const WidthForWrappedName = 255 + Math.min(LongestName, 90) * 3.4;
  const WidthForLongSegment = 250 + Math.min(LongestSegment, 56) * 5.4;
  const PreferredWidth = Math.max(DefaultSidebarWidth, WidthForWrappedName, WidthForLongSegment);
  return Math.round(Math.max(MinSidebarWidth, Math.min(MaxSidebarWidth, PreferredWidth)));
}

//MARK: sidebar width
function UpdateSidebarWidth(Files = CurveFiles)
{
  if (!AppShell)
    return;
  if (!Files || !Files.length)
  {
    AppShell.style.removeProperty('--sidebar-width');
    return;
  }
  AppShell.style.setProperty('--sidebar-width', `${SidebarWidthForFiles(Files)}px`);
}

//MARK: status text
function SetStatus(Message, IsError = false)
{
  StatusEl.textContent = Message;
  StatusEl.className = IsError ? "Status Error" : "Status";
}

//MARK: cache files
function NewRunId()
{
  if (window.crypto && typeof window.crypto.randomUUID === 'function')
  {
    return window.crypto.randomUUID();
  }
  const Bytes = new Uint8Array(16);
  window.crypto.getRandomValues(Bytes);
  const Random = Array.from(Bytes, Value => Value.toString(16).padStart(2, '0')).join('');
  return `session_${Date.now().toString(36)}_${Random}`;
}

//MARK: run url
function EnsureSessionId()
{
  const Url = new URL(window.location.href);
  const Requested = Url.searchParams.get(SessionQueryKey);
  SessionId = Requested && SessionIdPattern.test(Requested) ? Requested : NewRunId();
  if (Requested !== SessionId)
  {
    Url.searchParams.set(SessionQueryKey, SessionId);
    window.history.replaceState(null, '', `${Url.pathname}${Url.search}${Url.hash}`);
  }
  return SessionId;
}

//MARK: short run id
function ShortSessionId()
{
  return SessionId ? SessionId.slice(0, 8) : '--------';
}

//MARK: cache status
function SetSessionIndicator(Message, State = '', Title = '')
{
  if (!SessionIndicatorEl)
    return;
  SessionIndicatorEl.textContent = Message;
  SessionIndicatorEl.className = `SessionIndicator${State ? ` ${CssTag(State)}` : ''}`;
  SessionIndicatorEl.title = Title;
}

//MARK: cache folder
function SetSaveFileLocation(Directory, CacheFile = '')
{
  if (!CacheFolderThing || !SaveLocationFileEl || !Directory)
    return;
  const NormalizedDirectory = String(Directory).replace(/\/$/, '');
  const FullCacheFile = CacheFile || `${NormalizedDirectory}/session-${SessionId}.json`;
  const Filename = FullCacheFile.split('/').pop() || `session-${SessionId}.json`;
  CacheFolderThing.value = NormalizedDirectory;
  CacheFolderThing.title = NormalizedDirectory;
  SaveLocationFileEl.textContent = `Current file: ${Filename}`;
  SaveLocationFileEl.className = "SaveLocationFile";
  SaveLocationFileEl.title = FullCacheFile;
}

//MARK: folder feedback
function SetSaveLocationFeedback(Message, IsError = false)
{
  if (!SaveLocationFileEl)
    return;
  SaveLocationFileEl.textContent = Message;
  SaveLocationFileEl.className = `SaveLocationFile${IsError ? ' Error' : ''}`;
}

//MARK: cache size text
function FormatCacheBytes(Value)
{
  const Bytes = Math.max(0, Number(Value) || 0);
  if (Bytes < 1024)
    return `${Bytes} B`;
  if (Bytes < 1024 * 1024)
    return `${(Bytes / 1024).toFixed(1)} KB`;
  return `${(Bytes / (1024 * 1024)).toFixed(1)} MB`;
}

//MARK: cache date text
function FormatCacheDate(Value)
{
  const ParsedDate = new Date(Value);
  if (!Number.isFinite(ParsedDate.getTime()))
    return 'unknown date';
  return ParsedDate.toLocaleString([], {
    month : 'short',
    day : 'numeric',
    hour : 'numeric',
    minute : '2-digit',
  });
}

//MARK: load button
function UpdateLoadCacheButton()
{
  if (!CachePickThing || !LoadCacheButtonEl)
    return;
  const Selected = KnownSessionCaches.find(Item => Item.session_id === CachePickThing.value);
  LoadCacheButtonEl.disabled = !Selected || !Selected.loadable || Selected.session_id === SessionId;
}

//MARK: saved run list
function RenderSessionCacheList()
{
  if (!CachePickThing || !LoadCacheStatusEl)
    return;
  CachePickThing.replaceChildren();
  if (!KnownSessionCaches.length)
  {
    const Option = document.createElement('option');
    Option.textContent = 'No saved sessions found';
    Option.value = '';
    CachePickThing.append(Option);
    CachePickThing.disabled = true;
    LoadCacheStatusEl.textContent = 'Run an analysis to create a cache you can reopen here.';
    UpdateLoadCacheButton();
    return;
  }

  KnownSessionCaches.forEach(Item =>
  {
    const Option = document.createElement('option');
    const Current = Item.session_id === SessionId ? ' · current' : '';
    const Unavailable = Item.loadable ? '' : ' · too large';
    Option.value = Item.session_id;
    Option.textContent = `${Item.session_id.slice(0, 12)} · ${FormatCacheDate(Item.modified_at)} · ${
        FormatCacheBytes(Item.size_bytes)}${Current}${Unavailable}`;
    Option.title = Item.cache_file || Item.cache_directory || '';
    Option.disabled = !Item.loadable;
    Option.selected = Item.session_id === SessionId;
    CachePickThing.append(Option);
  });
  CachePickThing.disabled = false;
  if (!CachePickThing.value)
  {
    const FirstLoadable = KnownSessionCaches.find(Item => Item.loadable);
    if (FirstLoadable)
      CachePickThing.value = FirstLoadable.session_id;
  }
  LoadCacheStatusEl.textContent = `${KnownSessionCaches.length} saved session${
      KnownSessionCaches.length === 1 ? '' : 's'} found, newest first.`;
  LoadCacheStatusEl.className = "LoadCacheStatus";
  UpdateLoadCacheButton();
}

//MARK: refresh caches
async function RefreshSessionCacheList()
{
  if (!CachePickThing || !LoadCacheStatusEl)
    return;
  RefreshCachesButtonEl.disabled = true;
  CachePickThing.disabled = true;
  LoadCacheStatusEl.textContent = 'Refreshing saved sessions…';
  LoadCacheStatusEl.className = "LoadCacheStatus";
  try
  {
    const Reply = await fetch('/analysis-sessions', {cache : 'no-store'});
    const Payload = await ReadJsonResponse(Reply);
    if (!Reply.ok)
      throw new Error(Payload.error || 'Could not find saved sessions.');
    KnownSessionCaches = Array.isArray(Payload.sessions) ? Payload.sessions : [];
    RenderSessionCacheList();
  }
  catch (RunError)
  {
    console.error('[session cache] list failed', RunError);
    KnownSessionCaches = [];
    CachePickThing.replaceChildren();
    const Option = document.createElement('option');
    Option.textContent = 'Saved sessions unavailable';
    CachePickThing.append(Option);
    LoadCacheStatusEl.textContent = RunError.message;
    LoadCacheStatusEl.className = "LoadCacheStatus Error";
    UpdateLoadCacheButton();
  }
  finally
  {
    RefreshCachesButtonEl.disabled = false;
  }
}

//MARK: pack run state
function PackRunState()
{
  // results can be saved, but the original file objects cannot.
  return {
    ui_schema_version : 2,
    current_batch_index : CurrFileIndex,
    current_view : CurrView,
    current_viewport : CurrViewport,
    phase_scope : PhaseScopeInput.value,
    current_signal_index : MainResult?.signals?.indexOf(CurrResult) ?? -1,
    current_signal_selection : SignalPickThing.value,
    active_job_id : RunningJobId,
    active_request_id : RequestId,
    active_file_index : RunningFileIndex,
    batch_id : BatchRunId,
    pending_files : PendingBatchFiles,
    per_file_settings : PerFileSettingsInput.value,
    detection_options : DetectionOptions(),
    //MARK: saved curves
    results : FileResults.map(Item => ({
                                file_name : String(Item.file?.name || Item.result?.source_file || 'unknown'),
                                file_size : Number(Item.file?.size) || 0,
                                file_last_modified : Number(Item.file?.lastModified) || null,
                                result : Item.result || null,
                                error : Item.error || null,
                                status : Item.status || (Item.result  ? 'completed'
                                                         : Item.error ? 'failed'
                                                                      : 'pending'),
                              })),
  };
}

//MARK: save run
function SaveRunNow()
{
  if (!SessionInitialized || RestoringSession || !SessionId)
    return Promise.resolve(false);
  if (SessionSaveTimer !== null)
  {
    window.clearTimeout(SessionSaveTimer);
    SessionSaveTimer = null;
  }
  const Snapshot = PackRunState();
  SetSessionIndicator(`Session ${ShortSessionId()} · saving cache…`, 'saving');
  // keep saves in order so an older request cannot replace a newer view.
  SessionSaveChain = SessionSaveChain.catch(() => false).then(async () =>
  {
    try
    {
      const Reply = await fetch(`/analysis-sessions/${encodeURIComponent(SessionId)}`, {
        method : 'POST',
        headers : {'Content-Type' : 'application/json'},
        body : JSON.stringify(Snapshot),
      });
      const Payload = await ReadJsonResponse(Reply);
      if (!Reply.ok)
        throw new Error(Payload.error || 'Could not save this analysis session.');
      SetSaveFileLocation(Payload.cache_directory, Payload.cache_file);
      SetSessionIndicator(`Session ${ShortSessionId()} · cache saved`, '',
                          Payload.cache_file || Payload.cache_directory || '');
      return true;
    }
    catch (RunError)
    {
      console.error('[session cache] save failed', RunError);
      SetSessionIndicator(`Session ${ShortSessionId()} · cache save failed`, 'error', RunError.message);
      return false;
    }
  });
  return SessionSaveChain;
}

//MARK: queue save
function QueueSessionSave()
{
  // several quick changes can share one save request.
  if (!SessionInitialized || RestoringSession)
    return;
  if (SessionSaveTimer !== null)
    window.clearTimeout(SessionSaveTimer);
  SessionSaveTimer = window.setTimeout(() =>
  {
    SessionSaveTimer = null;
    SaveRunNow();
  }, SessionSaveDelayMs);
}

//MARK: saved settings
function ApplySavedDetectionOptions(Options)
{
  if (!Options || typeof Options !== 'object')
    return;
  for (const {key : Key, input : Input, defaultValue : DefaultValue} of DetectionControls)
  {
    const Value = Options[Key];
    Input.value = Value === null || Value === undefined ? DefaultValue : String(Value);
  }
  UpdateDetectionReadouts();
}

//MARK: restore run
function RestoreSessionState(State)
{
  // restore the view without starting another search.
  if (!State || typeof State !== 'object' || !Array.isArray(State.results))
    return 0;
  RestoringSession = true;
  try
  {
    CurveFiles = [];
    CurrFile = null;
    FileResults =
        State.results.slice(0, MaxBatchFiles)
            .map(Item => ({
                   file : {
                     name : String(Item.file_name || Item.result?.source_file || 'restored-analysis'),
                     size : Number(Item.file_size) || 0,
                     lastModified : Number(Item.file_last_modified) || 0,
                     restored : true,
                   },
                   result : Item.result && typeof Item.result === 'object' ? Item.result : null,
                   error : Item.error ? String(Item.error) : null,
                   status : Item.status || (Item.result  ? 'completed'
                                            : Item.error ? 'failed'
                                                         : 'pending'),
                 }));
    ApplySavedDetectionOptions(State.detection_options);
    PerFileSettingsInput.value = typeof State.per_file_settings === 'string' ? State.per_file_settings : '';
    //MARK: restore connection
    RunningJobId = typeof State.active_job_id === 'string' ? State.active_job_id : null;
    RequestId = typeof State.active_request_id === 'string' ? State.active_request_id : null;
    RunningFileIndex = Number.isInteger(State.active_file_index) ? State.active_file_index : null;
    BatchRunId = State.batch_id || null;
    PendingBatchFiles = Array.isArray(State.pending_files) ? State.pending_files : [];
    JobConnectionLost = Boolean(RunningJobId || RequestId);
    ReconnectJobButton.hidden = !JobConnectionLost;
    PhaseScopeInput.value = State.phase_scope === 'orbit' ? 'orbit' : 'focus';
    //MARK: restore view
    CurrView = SessionViews.has(State.current_view) ? State.current_view : 'zoom';
    ViewButtons.forEach(Button => Button.classList.toggle("Active", Button.dataset.view === CurrView));
    CurrFileIndex = Number.isInteger(State.current_batch_index) ? State.current_batch_index : -1;
    if (!FileResults[CurrFileIndex]?.result)
    {
      CurrFileIndex = FileResults.findIndex(Item => Item.result);
    }
    UpdateSidebarWidth(FileResults.map(Item => Item.file));
    ResetAnalysisProgress();
    RenderBatchSelect();
    if (CurrFileIndex >= 0)
    {
      const Item = FileResults[CurrFileIndex];
      CurrFile = Item.file;
      MainResult = Item.result;
      CurrResult = Item.result.signals?.[State.current_signal_index] || Item.result;
      CurrViewport = ValidViewport(State.current_viewport) ? State.current_viewport : null;
      ShowCurveResult(CurrResult);
      if (State.current_signal_selection === 'combined' && MainResult.joint_model_comparison)
      {
        SignalPickThing.value = 'combined';
        CurrViewport = null;
        UpdateChartHeading();
        DrawFlux();
      }
    }
    else
    {
      ClearResultView();
    }
    AnalyzeButton.disabled = true;
    CurveFilesInput.disabled = JobConnectionLost;
    FileDropThing.setAttribute('aria-disabled', String(JobConnectionLost));
    return FileResults.length;
  }
  finally
  {
    RestoringSession = false;
  }
}

//MARK: open run
async function OpenRun()
{
  EnsureSessionId();
  SetSessionIndicator(`Session ${ShortSessionId()} · checking saved cache…`, 'saving');
  try
  {
    const Reply = await fetch(`/analysis-sessions/${encodeURIComponent(SessionId)}`, {cache : 'no-store'});
    const Payload = await ReadJsonResponse(Reply);
    if (!Reply.ok)
      throw new Error(Payload.error || 'Could not load this analysis session.');
    SetSaveFileLocation(Payload.cache_directory, Payload.cache_file);
    SessionInitialized = true;
    if (Payload.exists)
    {
      const RestoredCount = RestoreSessionState(Payload.state);
      SetSessionIndicator(`Session ${ShortSessionId()} · restored from cache`, '',
                          Payload.cache_directory || '');
      SetStatus(
          RestoredCount
              ? `Restored ${RestoredCount} processed file${RestoredCount === 1 ? '' : 's'} from this session.`
              : 'This session is ready. No files have been processed yet.');
      return;
    }
    await SaveRunNow();
  }
  catch (RunError)
  {
    SessionInitialized = true;
    console.error('[session cache] load failed', RunError);
    SetSessionIndicator(`Session ${ShortSessionId()} · cache unavailable`, 'error', RunError.message);
  }
  finally
  {
    await RefreshSessionCacheList();
  }
}

if (SaveLocationFormEl)
{
  SaveLocationFormEl.addEventListener('submit', async UiEvent =>
  {
    UiEvent.preventDefault();
    await SessionReadyPromise;
    const Directory = CacheFolderThing.value.trim();
    if (!Directory)
    {
      SetSaveLocationFeedback('Enter a save folder.', true);
      CacheFolderThing.focus();
      return;
    }

    SaveLocationButtonEl.disabled = true;
    SetSaveLocationFeedback('Updating this session’s save folder…');
    try
    {
      const Reply = await fetch(`/analysis-sessions/${encodeURIComponent(SessionId)}/location`, {
        method : 'POST',
        headers : {'Content-Type' : 'application/json'},
        body : JSON.stringify({directory : Directory}),
      });
      const Payload = await ReadJsonResponse(Reply);
      if (!Reply.ok)
        throw new Error(Payload.error || 'Could not update the save location.');
      SetSaveFileLocation(Payload.cache_directory, Payload.cache_file);
      const Saved = await SaveRunNow();
      if (Saved)
      {
        SetSessionIndicator(
            `Session ${ShortSessionId()} · ${Payload.moved ? 'cache moved' : 'save location updated'}`, '',
            Payload.cache_file || Payload.cache_directory || '');
        await RefreshSessionCacheList();
      }
    }
    catch (RunError)
    {
      console.error('[session cache] location update failed', RunError);
      SetSaveLocationFeedback(RunError.message, true);
    }
    finally
    {
      SaveLocationButtonEl.disabled = false;
    }
  });
}

if (CachePickThing)
{
  CachePickThing.addEventListener('change', UpdateLoadCacheButton);
}

if (RefreshCachesButtonEl)
{
  RefreshCachesButtonEl.addEventListener('click', RefreshSessionCacheList);
}

if (LoadCacheButtonEl)
{
  LoadCacheButtonEl.addEventListener('click', async () =>
  {
    await SessionReadyPromise;
    const SelectedSessionId = CachePickThing.value;
    const Selected = KnownSessionCaches.find(Item => Item.session_id === SelectedSessionId);
    if (!Selected || !Selected.loadable || SelectedSessionId === SessionId)
      return;
    if (BatchInProgress)
    {
      LoadCacheStatusEl.textContent =
          'Wait for the active analysis to finish, or cancel it before loading another cache.';
      LoadCacheStatusEl.className = "LoadCacheStatus Error";
      return;
    }

    LoadCacheButtonEl.disabled = true;
    LoadCacheStatusEl.textContent = `Saving this session before loading ${SelectedSessionId.slice(0, 12)}…`;
    const Saved = await SaveRunNow();
    if (!Saved)
    {
      LoadCacheStatusEl.textContent = 'This session could not be saved, so the other cache was not loaded.';
      LoadCacheStatusEl.className = "LoadCacheStatus Error";
      UpdateLoadCacheButton();
      return;
    }

    const Url = new URL(window.location.href);
    Url.searchParams.set(SessionQueryKey, SelectedSessionId);
    window.location.assign(`${Url.pathname}${Url.search}${Url.hash}`);
  });
}

//MARK: progress stuffs
function ClampProgress(Value)
{
  if (!IsFiniteNumber(Value))
    return 0;
  return Math.max(0, Math.min(100, Number(Value)));
}

//MARK: stop clock
function StopProgressTimer()
{
  if (ProgressTimer !== null)
  {
    window.clearInterval(ProgressTimer);
    ProgressTimer = null;
  }
}

//MARK: elapsed text
function RenderProgressElapsed(Index)
{
  if (!AnalysisProgressEl)
    return;
  const Row = AnalysisProgressEl.querySelector(`[data-progress-index="${Index}"]`);
  const ElapsedEl = Row?.querySelector('[data-progress-elapsed]');
  const State = ProgressElapsedStates[Index];
  if (!ElapsedEl || !State)
    return;
  ElapsedEl.hidden = !State.visible;
  if (!State.visible)
    return;
  const LiveSeconds = State.seconds + (State.ticking ? Math.max(0, Date.now() - State.updatedAt) / 1000 : 0);
  ElapsedEl.textContent = `${State.label || 'Elapsed'} ${FormatJobElapsed(LiveSeconds)}`;
}

//MARK: start clock
function StartProgressTimer()
{
  StopProgressTimer();
  ProgressTimer = window.setInterval(() =>
  {
    ProgressElapsedStates.forEach((State, Index) =>
    {
      if (State?.visible)
        RenderProgressElapsed(Index);
    });
  }, 250);
}

//MARK: elapsed time
function SetProgressElapsed(Index, Seconds, Ticking = true, Visible = true)
{
  ProgressElapsedStates[Index] = {
    seconds : Math.max(0, Number(Seconds) || 0),
    updatedAt : Date.now(),
    ticking : Ticking,
    visible : Visible,
  };
  RenderProgressElapsed(Index);
}

//MARK: pause clock
function PauseProgressElapsed(Index)
{
  const State = ProgressElapsedStates[Index];
  if (!State)
    return;
  const Seconds = State.seconds + (State.ticking ? Math.max(0, Date.now() - State.updatedAt) / 1000 : 0);
  SetProgressElapsed(Index, Seconds, false, State.visible);
}

//MARK: clear progress
function ResetAnalysisProgress()
{
  StopProgressTimer();
  ProgressValues = [];
  ProgressElapsedStates = [];
  if (AnalysisProgressEl)
  {
    AnalysisProgressEl.hidden = true;
    AnalysisProgressEl.innerHTML = '';
  }
}

//MARK: progress rows
function RenderProgressRows(Files)
{
  StopProgressTimer();
  ProgressValues = Files.map(() => 0);
  ProgressElapsedStates = Files.map(() => ({
                                      seconds : 0,
                                      updatedAt : Date.now(),
                                      ticking : false,
                                      visible : false,
                                    }));
  if (!AnalysisProgressEl)
    return;
  UpdateSidebarWidth(Files);
  AnalysisProgressEl.hidden = Files.length === 0;
  AnalysisProgressEl.innerHTML =
      Files
          .map((CurveFile, Index) => `
    <div class="ProgressItem Pending" data-progress-index="${Index}">
      <div class="ProgressHeader">
        <span title="${EscapeHtml(CurveFile.name)}">${Index + 1}. ${EscapeHtml(CurveFile.name)}</span>
        <span data-progress-percent>Pending</span>
      </div>
      <div class="ProgressElapsed" data-progress-elapsed hidden>Elapsed 0s</div>
      <div class="ProgressEta" data-progress-eta></div>
      <div class="ProgressTrack" role="progressbar" aria-label="Analysis progress for ${
                   EscapeHtml(CurveFile.name)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
        <div class="ProgressFill"></div>
      </div>
    </div>
  `).join('');
  if (Files.length)
    StartProgressTimer();
  ShowRunStatus();
}

//MARK: curve progress
function SetFileProgress(Index, Value, Label, State = 'active')
{
  if (!AnalysisProgressEl)
    return;
  ShowRunStatus();
  const Row = AnalysisProgressEl.querySelector(`[data-progress-index="${Index}"]`);
  if (!Row)
    return;
  const ProgressValue = ClampProgress(Value);
  ProgressValues[Index] = ProgressValue;
  Row.className = `ProgressItem ${CssTag(State)}`;
  Row.querySelector('[data-progress-percent]').textContent = Label || `${Math.round(ProgressValue)}%`;
  Row.querySelector('[role="progressbar"]').setAttribute('aria-valuenow', String(Math.round(ProgressValue)));
  Row.querySelector(".ProgressFill").style.width = `${ProgressValue}%`;
}

//MARK: start upload
function BeginFileProgress(Index)
{
  ShowRunStatus();
  SetIndeterminateFileProgress(Index, 'Uploading');
  SetProgressElapsed(Index, 0, true, true);
}

//MARK: unknown progress
function SetIndeterminateFileProgress(Index, Label)
{
  if (!AnalysisProgressEl)
    return;
  ShowRunStatus();
  const Row = AnalysisProgressEl.querySelector(`[data-progress-index="${Index}"]`);
  if (!Row)
    return;
  Row.className = "ProgressItem Active";
  Row.querySelector('[data-progress-percent]').textContent = Label;
  Row.querySelector('[role="progressbar"]').removeAttribute('aria-valuenow');
  Row.querySelector(".ProgressFill").style.width = '100%';
}

//MARK: finish progress
function FinishFileProgress(Index, Outcome = 'complete')
{
  SetProgressEta(Index, '');
  PauseProgressElapsed(Index);
  const Labels = {complete : 'Complete', failed : 'Failed', cancelled : 'Cancelled'};
  SetFileProgress(Index, Outcome === 'cancelled' ? 0 : 100, Labels[Outcome] || 'Failed', Outcome);
}

//MARK: curve summary
function BatchResultDetail(Item)
{
  if (!Item)
  {
    return {
      label : 'No file selected',
      meta : 'Run analysis to populate this list.',
      status : 'pending',
      score : null,
      transits : null,
    };
  }
  if (Item.error)
  {
    const Cancelled = Item.error === 'Cancelled';
    return {
      label : Cancelled ? 'Cancelled' : 'Failed',
      meta : Item.error,
      status : Cancelled ? 'cancelled' : 'failed',
      score : null,
      transits : null,
    };
  }
  if (!Item.result)
    return {
      label : Item.status || 'Pending',
      meta : 'No completed result',
      status : 'pending',
      score : null,
      transits : null
    };
  const Assessment = AssessmentForResult(Item.result);
  const TransitCount = Item.result.transits.length;
  return {
    label : Assessment.shortLabel,
    meta : `${Item.result.observed_events?.length ?? '-'} supported / ${TransitCount} windows · P ${
        Fmt(Item.result.period, 5)} d · SDE ${Fmt(Item.result.period_sde, 1)} · SNR ${
        Fmt(Item.result.tls_snr ?? Item.result.detection_snr,
            1)} · ${DurationLabel(Item.result.period_duration)}${
        Item.result.warnings?.some(W => W.severity === 'danger') ? ' · review warnings' : ''}`,
    status : Assessment.status,
    score : Assessment.candidateScore,
    transits : TransitCount,
  };
}

//MARK: close curve picker
function CloseBatchPicker()
{
  if (!BatchPickerList || !BatchPickerButton)
    return;
  BatchPickerList.hidden = true;
  BatchPickerButton.setAttribute('aria-expanded', 'false');
}

//MARK: toggle curve picker
function ToggleBatchPicker()
{
  if (!BatchPickerList || !BatchPickerButton || BatchPickerButton.disabled)
    return;
  const WillOpen = BatchPickerList.hidden;
  BatchPickerList.hidden = !WillOpen;
  BatchPickerButton.setAttribute('aria-expanded', WillOpen ? 'true' : 'false');
}

//MARK: curve picker
function RenderBatchPicker()
{
  if (!CurvePickThing || !BatchPickerButton || !BatchPickerTitle || !BatchPickerMeta || !BatchPickerList)
    return;
  const SuccessCount = FileResults.filter(Item => Item.result).length;
  const ActiveItem = CurrFileIndex >= 0 ? FileResults[CurrFileIndex] : null;
  const ActiveDetail = BatchResultDetail(ActiveItem);
  const Disabled = SuccessCount === 0;

  CurvePickThing.hidden = false;
  BatchPickerButton.disabled = Disabled;
  BatchPickerButton.className = `BatchPickerButton ${CssTag(ActiveDetail.status)}`;
  BatchPickerTitle.textContent =
      ActiveItem ? ActiveItem.file.name
                 : (FileResults.length ? 'No successful file selected' : 'No processed files');
  BatchPickerMeta.textContent =
      ActiveItem
          ? `${ActiveDetail.score === null ? 'No score' : `${ActiveDetail.score}/100 candidate score`} · ${
                ActiveDetail.label} · ${ActiveDetail.meta}`
          : (FileResults.length && SuccessCount === 0 ? 'All processed files failed.'
                                                      : 'Run analysis to populate this list.');
  BatchPickerList.hidden = BatchPickerList.hidden || Disabled;
  BatchPickerButton.setAttribute('aria-expanded', BatchPickerList.hidden ? 'false' : 'true');
  const FocusIndex = document.activeElement?.dataset?.batchIndex;
  const ScrollTop = BatchPickerList.scrollTop;
  BatchPickerList.innerHTML =
      SortedBatchEntries()
          .map(({item : Item, index : Index}) =>
          {
            const Selected = Index === CurrFileIndex;
            const Detail = BatchResultDetail(Item);
            const DisabledAttribute = !Item.result ? ' disabled aria-disabled="true"' : '';
            const ScoreHtml =
                Detail.score === null
                    ? ''
                    : `<span class="BatchScore ${CssTag(Detail.status)}" aria-label="Candidate score ${
                          Detail.score} out of 100">${Detail.score}/100</span>`;
            return `
      <button
        class="BatchOption ${CssTag(Detail.status)}${Selected ? ' Selected' : ''}"
        type="button"
        role="option"
        aria-selected="${Selected ? 'true' : 'false'}"
        data-batch-index="${Index}"
        title="${EscapeHtml(Item.file.name)}"
        ${DisabledAttribute}
      >
        <span class="BatchOptionIndex">${Index + 1}</span>
        <span class="BatchOptionBody">
          <span class="BatchOptionName">${EscapeHtml(Item.file.name)}</span>
          <span class="BatchOptionMeta">
            ${ScoreHtml}
            <span class="BatchBadge ${CssTag(Detail.status)}">${EscapeHtml(Detail.label)}</span>
            <span>${EscapeHtml(Detail.meta)}</span>
          </span>
        </span>
      </button>
    `;
          })
          .join('');
  BatchPickerList.scrollTop = ScrollTop;
  if (FocusIndex !== undefined && !BatchPickerList.hidden)
    BatchPickerList.querySelector(`[data-batch-index="${FocusIndex}"]`)?.focus({preventScroll : true});
}

//MARK: sort curves
function SortedBatchEntries()
{
  const Entries = FileResults.map((Item, Index) => ({item : Item, index : Index}));
  const Sort = BatchSortInput?.value || 'index';
  return Entries.sort((A, B) =>
  {
    if (Sort === 'name')
      return A.item.file.name.localeCompare(B.item.file.name);
    if (Sort === 'score')
      return (AssessmentForResult(B.item.result)?.candidateScore ?? -1) -
             (AssessmentForResult(A.item.result)?.candidateScore ?? -1);
    if (Sort === 'period')
      return (NullableNumber(A.item.result?.period) ?? Infinity) -
             (NullableNumber(B.item.result?.period) ?? Infinity);
    return A.index - B.index;
  });
}

//MARK: processed curves
function RenderBatchSelect()
{
  const SuccessCount = FileResults.filter(Item => Item.result).length;
  BatchCount.value = `${SuccessCount}/${FileResults.length || CurveFiles.length || 0}`;
  if (!FileResults.length)
  {
    ResultSelect.disabled = true;
    ResultSelect.innerHTML = '<option>No processed files</option>';
    RenderBatchPicker();
    SyncExportButtons();
    return;
  }

  ResultSelect.disabled = SuccessCount === 0;
  ResultSelect.innerHTML =
      FileResults
          .map((Item, Index) =>
          {
            const Selected = Index === CurrFileIndex ? ' selected' : '';
            const Disabled = !Item.result ? ' disabled' : '';
            const Detail = !Item.result ? (Item.error ? (Item.error === 'Cancelled' ? 'cancelled' : 'failed')
                                                      : (Item.status || 'pending').replaceAll('_', ' '))
                                        : `${AssessmentForResult(Item.result).shortLabel}; ${
                                              Item.result.transits.length} covered windows`;
            return `<option value="${Index}"${Selected}${Disabled}>${Index + 1}. ${
                EscapeHtml(Item.file.name)} (${Detail})</option>`;
          })
          .join('');
  RenderBatchPicker();
  SyncExportButtons();
}

//MARK: choose files
function SetFiles(FileList)
{
  if (BatchInProgress || RunningJobId || JobConnectionLost)
  {
    SetStatus(
        'Reconnect to or cancel the current job before replacing files. Completed results remain available below.');
    return;
  }
  const Files = Array.from(FileList || []);
  CurveFiles = Files.slice(0, MaxBatchFiles);
  RenderPerFileTarget();
  UpdateSidebarWidth(CurveFiles);
  CurrFile = CurveFiles[0] || null;
  FileResults = [];
  CurrFileIndex = -1;
  ResetAnalysisProgress();
  RenderBatchSelect();
  ClearResultView();
  AnalyzeButton.disabled = !CurveFiles.length;
  if (!CurveFiles.length)
  {
    SetStatus('No file selected.');
  }
  else if (Files.length > MaxBatchFiles)
  {
    SetStatus(`Selected first ${MaxBatchFiles} of ${Files.length} files.`);
  }
  else
  {
    SetStatus(CurveFiles.length === 1 ? CurveFiles[0].name : `${CurveFiles.length} files selected.`);
  }
  QueueSessionSave();
}

//MARK: optional inputs
function OptionalNumber(Input)
{
  return NullableNumber(Input?.value);
}

//MARK: read settings
function DetectionOptions()
{
  // blank optional fields stay null. zero is still a real setting.
  const Options = {};
  for (const {key : Key, input : Input, read : Read = NullableNumber} of DetectionControls)
  {
    Options[Key] = Read(Input.value);
  }
  return Options;
}

//MARK: settings readouts
function UpdateDetectionReadouts()
{
  StrictnessValue.value = `${Number(StrictnessInput.value).toFixed(2)}x`;
  SmoothingValue.value = `${Number(SmoothingInput.value).toFixed(2)}x`;
  const TlsMode = SearchModeInput.value === 'tls';
  TlsOptionsEl.hidden = !TlsMode;
  [StrictnessInput, MinDepthInput, MinDurationInput, MaxDurationInput].forEach(
      Input =>
      {
        Input.disabled = false;
      });
}

//MARK: reset settings
function ResetDetectionControls()
{
  for (const {input : Input, defaultValue : DefaultValue} of DetectionControls)
  {
    Input.value = DefaultValue;
  }
  UpdateDetectionReadouts();
}

//MARK: changed settings
function MarkDetectionControlsChanged()
{
  if (CurrResult && CurveFiles.length)
  {
    SetStatus('Detection controls changed. Run Analyze files to apply.');
  }
  QueueSessionSave();
}

//MARK: export buttons
function SyncExportButtons()
{
  const Disabled = !CurrResult;
  ExportCsvButton.disabled = Disabled;
  ExportPngButton.disabled = Disabled;
  ExportJsonButton.disabled = Disabled;
  ExportAnalysisPdfButton.disabled = Disabled;
  ExportBatchPdfButton.disabled = !FileResults.some(Item => Item.result);
}

//MARK: clear results
function ClearResultView()
{
  CurrResult = null;
  MainResult = null;
  UpdateInspectorControls();
  CurrViewport = null;
  EmptyEl.style.display = 'grid';
  AssessmentEl.innerHTML = `
    <div class="AssessmentCard Pending">
      <div class="AssessmentHead">
        <strong>No dataset analyzed</strong>
        <span>-</span>
      </div>
      <p>Candidate verdict appears after analysis.</p>
    </div>
  `;
  MetricsEl.innerHTML = `
    <div class="Metric"><span>Data points</span><span>-</span></div>
    <div class="Metric"><span>Transits</span><span>-</span></div>
    <div class="Metric"><span>Orbital period</span><span>-</span></div>
    <div class="Metric"><span>Period uncertainty</span><span>-</span></div>
    <div class="Metric"><span>Local median depth</span><span>-</span></div>
    <div class="Metric"><span>Radius ratio</span><span>-</span></div>
    <div class="Metric"><span>Depth SNR</span><span>-</span></div>
    <div class="Metric"><span>Period SDE</span><span>-</span></div>
    <div class="Metric"><span>TLS false-alarm probability</span><span>-</span></div>
    <div class="Metric"><span>Measured timing agreement</span><span>-</span></div>
    <div class="Metric"><span>Approx. model-vs-flat p-value</span><span>-</span></div>
    <div class="Metric"><span>Reduced chi-sq</span><span>-</span></div>
    <div class="Metric"><span>Time reference</span><span>-</span></div>
    <div class="Metric"><span>Median flux</span><span>-</span></div>
    <div class="Metric"><span>Noise</span><span>-</span></div>
  `;
  PeriodCandidatesEl.innerHTML = `
    <div class="WarningItem Info">
      <strong>No candidates yet</strong>
      <span>Period search results appear after analysis.</span>
    </div>
  `;
  WarningsEl.innerHTML = `
    <div class="WarningItem Info">
      <strong>No analysis yet</strong>
      <span>Candidate checks appear after upload.</span>
    </div>
  `;
  RowsEl.innerHTML =
      '<tr><td colspan="10" style="text-align:left;color:#60656f;">No transit candidates yet.</td></tr>';
  UpdateChartHeading();
  SyncExportButtons();
  DrawFlux();
}

//MARK: upload settings
function AppendDetectionOptions(UploadForm, Options)
{
  UploadForm.append('strictness', Options.strictness);
  UploadForm.append('smoothing', Options.smoothing);
  UploadForm.append('searchMode', Options.searchMode);
  UploadForm.append('tlsTemplate', Options.tlsTemplate);
  if (Options.stellarRadius !== null)
    UploadForm.append('stellarRadius', Options.stellarRadius);
  if (Options.stellarMass !== null)
    UploadForm.append('stellarMass', Options.stellarMass);
  if (Options.limbDarkeningU1 !== null)
    UploadForm.append('limbDarkeningU1', Options.limbDarkeningU1);
  if (Options.limbDarkeningU2 !== null)
    UploadForm.append('limbDarkeningU2', Options.limbDarkeningU2);
  if (Options.tlsOversampling !== null)
    UploadForm.append('tlsOversampling', Options.tlsOversampling);
  if (Options.tlsMinTransits !== null)
    UploadForm.append('tlsMinTransits', Options.tlsMinTransits);
  if (Options.tlsMinDepthPpm !== null)
    UploadForm.append('tlsMinDepthPpm', Options.tlsMinDepthPpm);
  if (Options.tlsThreads !== null)
    UploadForm.append('tlsThreads', Options.tlsThreads);
  if (Options.tlsDurationGridStep !== null)
    UploadForm.append('tlsDurationGridStep', Options.tlsDurationGridStep);
  UploadForm.append('tlsMaxSignals', Options.tlsMaxSignals ?? 1);
  UploadForm.append('csvTimeFormat', Options.csvTimeFormat || 'unknown');
  UploadForm.append('csvTimeScale', Options.csvTimeScale || 'unknown');
  UploadForm.append('csvTimeUnit', Options.csvTimeUnit || 'days');
  if (Options.exposureSeconds !== null && Options.exposureSeconds !== undefined)
  {
    UploadForm.append('exposureSeconds', Options.exposureSeconds);
  }
  if (Options.minDepth !== null)
    UploadForm.append('minDepth', Options.minDepth);
  if (Options.minDuration !== null)
    UploadForm.append('minDuration', Options.minDuration);
  if (Options.maxDuration !== null)
    UploadForm.append('maxDuration', Options.maxDuration);
  if (Options.minPeriod !== null)
    UploadForm.append('minPeriod', Options.minPeriod);
  if (Options.maxPeriod !== null)
    UploadForm.append('maxPeriod', Options.maxPeriod);
}

//MARK: cancelled job
class AnalysisCancelledError extends Error
{
  constructor(Message = 'Analysis cancelled.')
  {
    super(Message);
    this.name = 'AnalysisCancelledError';
  }
}

//MARK: lost connection
class AnalysisDisconnectedError extends Error
{
}

//MARK: poll delay
function Wait(Milliseconds)
{
  return new Promise(Resolve => window.setTimeout(Resolve, Milliseconds));
}

//MARK: job time text
function FormatJobElapsed(Seconds)
{
  const Total = Math.max(0, Math.floor(Number(Seconds) || 0));
  const Minutes = Math.floor(Total / 60);
  const Remainder = Total % 60;
  return Minutes ? `${Minutes}m ${Remainder}s` : `${Remainder}s`;
}

//MARK: job progress
function UpdateProgressFromJob(Index, Job, SearchMode)
{
  const Active = [ 'queued', 'running', 'cancelling' ].includes(Job.status);
  SetProgressElapsed(Index, Job.elapsed_seconds, Active, true);
  if (Job.status === 'queued')
  {
    if (ProgressElapsedStates[Index])
      ProgressElapsedStates[Index].label = 'Queue wait';
    const Position = NullableNumber(Job.queue_position);
    const Label = Position !== null ? `Queued #${Position}` : 'Queued';
    SetIndeterminateFileProgress(Index, Label);
    SetProgressEta(Index, 'Queue wait is separate from search time.');
    return;
  }
  if (ProgressElapsedStates[Index])
    ProgressElapsedStates[Index].label = 'Elapsed';
  const Engine = SearchMode === 'tls' ? 'TLS' : 'Analysis';
  if (Job.status === 'cancelling')
  {
    SetIndeterminateFileProgress(Index, Job.stage_label || 'Cancelling…');
  }
  else if (Job.status === 'running')
  {
    SetIndeterminateFileProgress(Index, Job.stage_label || `${Engine} running`);
  }
  const Progress = {...Job, ...(Job.progress_details || Job.progress || {})};
  const Completed = NullableNumber(Progress.completed_trials ?? Progress.work_completed);
  const Total = NullableNumber(Progress.total_trials ?? Progress.work_total);
  const Counts = Completed !== null && Total > 0
                     ? `${Completed.toLocaleString()} / ${Total.toLocaleString()} period trials. `
                     : '';
  if (!Active || Job.status === 'cancelling')
    SetProgressEta(Index, '');
  else if (Job.stage === 'tls_finalizing' || Progress.search_complete)
    SetProgressEta(Index, 'Finalizing the model and diagnostics; completion ETA unavailable.');
  else if (Job.status === 'running')
    SetProgressEta(Index, `${Counts}${SearchEtaText(Progress, Job)}`);
}

//MARK: search eta
function SearchEtaText(Progress, Job)
{
  const Estimate = NullableNumber(Progress.estimated_remaining_seconds);
  const Range =
      Progress.remaining_seconds_range || [ Progress.eta_lower_seconds, Progress.eta_upper_seconds ];
  const Low = NullableNumber(Range?.[0]), High = NullableNumber(Range?.[1]);
  const IsSearch = /search|TLS|period/i.test(Job.stage_label || '') || Job.stage === 'tls_search';
  if (Job.stage === 'tls_finalizing' || Progress.search_complete)
    return 'Finalizing the model and diagnostics; completion ETA unavailable.';
  if (Progress.eta_state === 'estimating' || Estimate === null || Estimate < 0 || Low === null ||
      High === null || High < Low || High > Math.max(Low * 2, 120))
  {
    return IsSearch ? 'Search ETA: estimating…' : 'Finalization in progress; completion ETA unavailable.';
  }
  if (Estimate < 60)
    return 'Search time remaining: less than a minute.';
  const Minutes = Math.max(1, Math.round(Estimate / 60));
  const Lower = Math.max(1, Math.floor(Low / 60)), Upper = Math.max(Lower, Math.ceil(High / 60));
  return `Search time remaining: about ${Minutes} min${
      Lower < Upper ? ` (range ${Lower}–${Upper} min)` : ''}.`;
}

//MARK: eta text
function SetProgressEta(Index, Label)
{
  const Row = AnalysisProgressEl?.querySelector(`[data-progress-index="${Index}"]`);
  const Element = Row?.querySelector('[data-progress-eta]');
  if (Element)
    Element.textContent = Label;
}

//MARK: read response
async function ReadJsonResponse(Reply)
{
  try
  {
    return await Reply.json();
  }
  catch (RunError)
  {
    throw new Error(`Server returned an unreadable response (${Reply.status}).`);
  }
}

//MARK: cancel request
async function RequestJobCancellation(JobId)
{
  if (!JobId)
    return;
  const Reply = await fetch(`/analysis-jobs/${encodeURIComponent(JobId)}`, {method : 'DELETE'});
  const Payload = await ReadJsonResponse(Reply);
  if (!Reply.ok)
    throw new Error(Payload.error || 'Could not cancel the analysis.');
}

//MARK: saved plot bounds
function ValidViewport(Value)
{
  return Value && [ 'xMin', 'xMax', 'yMin', 'yMax' ].every(K => IsFiniteNumber(Value[K])) &&
         Value.xMax > Value.xMin && Value.yMax > Value.yMin;
}

//MARK: pick processed curve
function SelectBatchResult(Index)
{
  // browsing a finished file must not touch the running job.
  const Item = FileResults[Index];
  if (!Item || !Item.result)
    return;
  if (CurrFileIndex >= 0)
    ResultViewports.set(`${CurrFileIndex}:${CurrView}`, CurrViewport);
  CurrFileIndex = Index;
  CurrFile = Item.file;
  MainResult = Item.result;
  CurrResult = Item.result;
  CurrViewport = ResultViewports.get(`${Index}:${CurrView}`) || null;
  StackEventInput.value = 'all';
  RenderBatchSelect();
  ShowCurveResult(CurrResult);
  if (!BatchInProgress)
    SetStatus(`Showing ${Item.file.name}.`);
  QueueSessionSave();
}

//MARK: run buttons
CurveFilesInput.addEventListener('change', () => SetFiles(CurveFilesInput.files));
for (const {input : Input} of DetectionControls)
{
  if (Input === StrictnessInput || Input === SmoothingInput)
  {
    Input.addEventListener('input', () =>
    {
      UpdateDetectionReadouts();
      MarkDetectionControlsChanged();
    });
  }
  else if (Input === SearchModeInput)
  {
    Input.addEventListener('change', () =>
    {
      UpdateDetectionReadouts();
      MarkDetectionControlsChanged();
    });
  }
  else
  {
    Input.addEventListener('change', MarkDetectionControlsChanged);
  }
}
ResetDetectionButton.addEventListener('click', () =>
{
  ResetDetectionControls();
  MarkDetectionControlsChanged();
});
UpdateDetectionReadouts();

['dragenter', 'dragover'].forEach(Name =>
{
  FileDropThing.addEventListener(Name, UiEvent =>
  {
    UiEvent.preventDefault();
    FileDropThing.classList.add("Dragging");
  });
});

['dragleave', 'drop'].forEach(Name =>
{
  FileDropThing.addEventListener(Name, UiEvent =>
  {
    UiEvent.preventDefault();
    FileDropThing.classList.remove("Dragging");
  });
});

FileDropThing.addEventListener('drop', UiEvent =>
{
  if (BatchInProgress || RunningJobId || JobConnectionLost)
    return;
  if (UiEvent.dataTransfer.files.length)
  {
    CurveFilesInput.files = UiEvent.dataTransfer.files;
    SetFiles(UiEvent.dataTransfer.files);
  }
});

//MARK: cancel run
CancelAnalysisButton.addEventListener('click', async () =>
{
  if ((!BatchInProgress && !RunningJobId && !RequestId) || AnalysisCancelRequested)
    return;
  AnalysisCancelRequested = true;
  CancelAnalysisButton.disabled = true;
  SetStatus('Cancelling the active analysis…');
  try
  {
    if (!RunningJobId && RequestId && !BatchInProgress)
    {
      const Job = await LookupRequest(RequestId);
      if (Job)
        RunningJobId = Job.job_id;
      else
      {
        RequestId = null;
        RunningFileIndex = null;
        JobConnectionLost = false;
        ReconnectJobButton.hidden = true;
        CancelAnalysisButton.hidden = true;
        LockBatchInputs(false);
        SetStatus('No active server job was found. Completed results remain available.');
        await SaveRunNow();
        return;
      }
    }
    if (!RunningJobId)
      return;
    await RequestJobCancellation(RunningJobId);
    if (!BatchInProgress)
    {
      const Item = FileResults[RunningFileIndex];
      if (Item)
      {
        Item.error = 'Cancelled';
        Item.status = 'cancelled';
      }
      RunningJobId = null;
      RunningFileIndex = null;
      RequestId = null;
      JobConnectionLost = false;
      ReconnectJobButton.hidden = true;
      CancelAnalysisButton.hidden = true;
      LockBatchInputs(false);
      RenderBatchSelect();
      await SaveRunNow();
      SetStatus('Cancellation requested. Completed results remain available.');
    }
  }
  catch (RunError)
  {
    AnalysisCancelRequested = false;
    CancelAnalysisButton.disabled = false;
    SetStatus(RunError.message, true);
  }
});

//MARK: read file settings
function ReadPerFileSettings()
{
  const Text = PerFileSettingsInput.value.trim();
  if (!Text)
    return {};
  const Parsed = JSON.parse(Text);
  if (!Parsed || Array.isArray(Parsed) || typeof Parsed !== 'object')
    throw new Error('Per-file settings must be a JSON object keyed by filename.');
  const Allowed = new Set(Object.keys(DetectionOptions()));
  for (const [Filename, Values] of Object.entries(Parsed))
  {
    if (!Values || Array.isArray(Values) || typeof Values !== 'object')
      throw new Error(`Settings for ${Filename} must be an object.`);
    for (const Key of Object.keys(Values))
      if (!Allowed.has(Key))
        throw new Error(`Unknown per-file setting: ${Key}`);
  }
  return Parsed;
}

//MARK: file settings picker
function RenderPerFileTarget()
{
  const Select = document.getElementById("PerFileTarget");
  Select.innerHTML = CurveFiles.length
                         ? CurveFiles
                               .map(CurveFile => `<option value="${EscapeHtml(CurveFile.name)}">${
                                        EscapeHtml(CurveFile.name)}</option>`)
                               .join('')
                         : '<option value="">Choose source files first</option>';
}

//MARK: apply file settings
function UpdatePerFileSettings(Remove = false)
{
  if (BatchInProgress || RunningJobId || JobConnectionLost)
    return;
  const Filename = document.getElementById("PerFileTarget").value;
  if (!Filename)
  {
    SetStatus('Choose source files before assigning per-file settings.');
    return;
  }
  try
  {
    const Overrides = ReadPerFileSettings();
    if (Remove)
      delete Overrides[Filename];
    else
      Overrides[Filename] = DetectionOptions();
    PerFileSettingsInput.value = Object.keys(Overrides).length ? JSON.stringify(Overrides, null, 2) : '';
    document.getElementById("PerFileSettingsStatus").textContent =
        Remove ? `${Filename} will use the batch defaults.`
               : `Current settings saved for ${
                     Filename}. Changes above now affect the remaining batch defaults.`;
    QueueSessionSave();
  }
  catch (RunError)
  {
    SetStatus(RunError.message, true);
  }
}

//MARK: lock uploads
function LockBatchInputs(Locked)
{
  CurveFilesInput.disabled = Locked;
  FileDropThing.setAttribute('aria-disabled', String(Locked));
  AnalyzeButton.disabled = Locked || !CurveFiles.length;
  PerFileSettingsInput.disabled = Locked;
}

//MARK: batch funcs
async function ExecuteBatch(StartIndex = 0, ResumeJobId = null)
{
  if (BatchInProgress)
    return;
  BatchInProgress = true;
  JobConnectionLost = false;
  AnalysisCancelRequested = false;
  LockBatchInputs(true);
  CancelAnalysisButton.hidden = false;
  CancelAnalysisButton.disabled = false;
  ReconnectJobButton.hidden = true;
  RenderBatchSelect();
  try
  {
    //MARK: pending curves
    for (let Index = StartIndex; Index < FileResults.length; Index++)
    {
      const Item = FileResults[Index];
      if (Item.result || Item.error)
        continue;
      const Existing = Index === StartIndex ? ResumeJobId : null;
      //MARK: missing source files
      if (!Existing && !(Item.file instanceof Blob))
      {
        Item.status = 'needs_reselection';
        SetFileProgress(Index, 0, 'Reselect source file', 'pending');
        continue;
      }
      RunningFileIndex = Index;
      Item.status = 'running';
      if (PendingBatchFiles[Index])
        PendingBatchFiles[Index].status = 'running';
      SetStatus(`Analyzing ${Index + 1}/${FileResults.length}: ${Item.file.name}`);
      BeginFileProgress(Index);
      try
      {
        Item.result = await RunCurve(
            Item.file, Item.options || PendingBatchFiles[Index]?.options || DetectionOptions(),
            Job => UpdateProgressFromJob(Index, Job, (Item.options || DetectionOptions()).searchMode),
            Existing);
        Item.status = 'completed';
        Item.error = null;
        FinishFileProgress(Index, 'complete');
        if (CurrFileIndex === -1)
          SelectBatchResult(Index);
      }
      catch (RunError)
      {
        if (RunError instanceof AnalysisDisconnectedError)
        {
          Item.status = 'disconnected';
          SetStatus(RunError.message, true);
          ReconnectJobButton.hidden = false;
          PauseProgressElapsed(Index);
          SetProgressEta(Index, 'Connection lost. Reconnect to update the existing job.');
          break;
        }
        Item.error = RunError instanceof AnalysisCancelledError ? 'Cancelled' : RunError.message;
        Item.status = RunError instanceof AnalysisCancelledError ? 'cancelled' : 'failed';
        FinishFileProgress(Index, Item.status === 'cancelled' ? 'cancelled' : 'failed');
        if (RunError instanceof AnalysisCancelledError)
        {
          for (let J = Index + 1; J < FileResults.length; J++)
          {
            if (!FileResults[J].result)
            {
              FileResults[J].status = 'cancelled';
              FileResults[J].error = 'Cancelled';
              SetFileProgress(J, 0, 'Not started', 'cancelled');
            }
          }
          break;
        }
      }
      if (PendingBatchFiles[Index])
        PendingBatchFiles[Index].status = Item.status;
      RenderBatchSelect();
      await SaveRunNow();
    }
    //MARK: finished batch
    if (!JobConnectionLost)
    {
      const Completed = FileResults.filter(Item => Item.result);
      const Failed = FileResults.filter(Item => Item.error);
      const Remaining = FileResults.filter(Item => !Item.result && !Item.error);
      const Candidates = Completed
                             .filter(Item => ['strong_candidate', 'possible_candidate'].includes(
                                         AssessmentForResult(Item.result).status))
                             .length;
      SetStatus(
          Remaining.length
              ? `${Completed.length} results available. Reselect ${
                    Remaining.length} unsubmitted source file(s) to continue; their bytes were not cached.`
              : `Batch ${AnalysisCancelRequested ? 'cancelled' : 'complete'}: ${Completed.length}/${
                    FileResults.length} processed, ${Candidates} candidate-like${
                    Failed.length ? `, ${Failed.length} failed or cancelled` : ''}.`);
    }
  }
  finally
  {
    StopProgressTimer();
    BatchInProgress = false;
    if (!JobConnectionLost)
    {
      RunningJobId = null;
      RunningFileIndex = null;
      RequestId = null;
    }
    LockBatchInputs(JobConnectionLost);
    CancelAnalysisButton.hidden = !JobConnectionLost;
    CancelAnalysisButton.disabled = false;
    RenderBatchSelect();
    await SaveRunNow();
  }
}

//MARK: start batch
AnalyzeButton.addEventListener('click', async () =>
{
  if (BatchInProgress || RunningJobId || RequestId || !CurveFiles.length)
    return;
  let Overrides;
  try
  {
    Overrides = ReadPerFileSettings();
  }
  catch (RunError)
  {
    SetStatus(RunError.message, true);
    return;
  }
  await SessionReadyPromise;
  if (BatchInProgress || RunningJobId || RequestId)
    return;
  const Options = DetectionOptions();
  BatchRunId = NewRunId();
  FileResults =
      CurveFiles.slice(0, MaxBatchFiles).map(CurveFile => ({
                                               file : CurveFile,
                                               result : null,
                                               error : null,
                                               status : 'pending',
                                               options : {...Options, ...(Overrides[CurveFile.name] || {})}
                                             }));
  PendingBatchFiles = FileResults.map(Item => ({
                                        file_name : Item.file.name,
                                        file_size : Item.file.size,
                                        file_last_modified : Item.file.lastModified,
                                        options : Item.options,
                                        status : 'pending'
                                      }));
  CurrFileIndex = -1;
  ResultViewports.clear();
  RenderProgressRows(FileResults.map(Item => Item.file));
  ClearResultView();
  await ExecuteBatch();
});

//MARK: reconnect run
ReconnectJobButton.addEventListener('click', async () =>
{
  if (BatchInProgress || RunningFileIndex === null)
    return;
  try
  {
    if (!RunningJobId && RequestId)
    {
      const Job = await LookupRequest(RequestId);
      if (Job)
        RunningJobId = Job.job_id;
      else if (!(FileResults[RunningFileIndex]?.file instanceof Blob))
      {
        RequestId = null;
        JobConnectionLost = false;
        ReconnectJobButton.hidden = true;
        LockBatchInputs(false);
        SetStatus(
            'No server job was found for the saved request. Reselect the unsubmitted source file to run it.');
        await SaveRunNow();
        return;
      }
    }
    RenderProgressRows(FileResults.map(Item => Item.file));
    await ExecuteBatch(RunningFileIndex, RunningJobId);
  }
  catch (RunError)
  {
    SetStatus(`Could not reconnect: ${RunError.message}`, true);
  }
});

//MARK: find submitted job
async function LookupRequest(RequestToken)
{
  const Reply =
      await fetch(`/analysis-jobs?request_id=${encodeURIComponent(RequestToken)}`, {cache : 'no-store'});
  if (Reply.status === 404)
    return null;
  const Job = await ReadJsonResponse(Reply);
  if (!Reply.ok)
    throw new Error(Job.error || 'Could not resolve the analysis request.');
  return Job;
}

BatchSortInput.addEventListener('change', RenderBatchPicker);

ResultSelect.addEventListener('change', () =>
{
  SelectBatchResult(Number(ResultSelect.value));
});

if (BatchPickerButton)
{
  BatchPickerButton.addEventListener('click', ToggleBatchPicker);
}

if (BatchPickerList)
{
  BatchPickerList.addEventListener('click', UiEvent =>
  {
    const Option = UiEvent.target.closest('[data-batch-index]');
    if (!Option || Option.disabled)
      return;
    CloseBatchPicker();
    SelectBatchResult(Number(Option.dataset.batchIndex));
  });
}

document.addEventListener('click', UiEvent =>
{
  if (!CurvePickThing || CurvePickThing.hidden || CurvePickThing.contains(UiEvent.target))
    return;
  CloseBatchPicker();
});

document.addEventListener('keydown', UiEvent =>
{
  if (UiEvent.key === 'Escape')
    CloseBatchPicker();
});

//MARK: switch plots
ViewButtons.forEach(Button =>
{
  Button.addEventListener('click', () =>
  {
    ResultViewports.set(`${CurrFileIndex}:${CurrView}`, CurrViewport);
    CurrView = Button.dataset.view;
    if (SignalPickThing.value === 'combined' && CurrView !== 'comparison')
    {
      CurrResult = MainResult?.signals?.[0] || MainResult;
      SignalPickThing.value = '0';
      RenderMetrics();
      RenderSignalPicker();
    }
    CurrViewport = ResultViewports.get(`${CurrFileIndex}:${CurrView}`) || null;
    ViewButtons.forEach(Item => Item.classList.toggle("Active", Item === Button));
    UpdateChartHeading();
    DrawFlux();
    QueueSessionSave();
  });
});

//MARK: plot checks
function HasPhaseFold()
{
  return Boolean(CurrResult && CurrResult.phase_folded && CurrResult.phase_folded.phase.length);
}

//MARK: stack data check
function HasTransitStack()
{
  return Boolean(CurrResult && CurrResult.transit_stack && Array.isArray(CurrResult.transit_stack.traces) &&
                 CurrResult.transit_stack.traces.length);
}

//MARK: model data check
function HasTransitModel()
{
  return Boolean(ShowModelInput.checked && CurrResult && CurrResult.transit_model &&
                 Array.isArray(CurrResult.transit_model.time) && CurrResult.transit_model.time.length);
}

//MARK: period search data
function PeriodogramSeries()
{
  if (!CurrResult || !CurrResult.periodogram)
    return null;
  const Payload = CurrResult.periodogram;
  const Periods = Array.isArray(Payload.periods) ? Payload.periods : [];
  const Powers = Array.isArray(Payload.power) ? Payload.power : [];
  const Sdes = Array.isArray(Payload.sde) ? Payload.sde : [];
  const HasSde = Sdes.some(Value => Value !== null && Value !== undefined && IsFiniteNumber(Value));
  const Points =
      Periods
          .map((Period, Index) =>
          {
            const X = Number(Period);
            const Power = Number(Powers[Index]);
            const Sde = Sdes[Index] === null || Sdes[Index] === undefined ? NaN : Number(Sdes[Index]);
            const Value = HasSde ? Sde : Power;
            return {
              period : X,
              value : Value,
              power : Power,
              sde : Sde,
            };
          })
          .filter(Point => Number.isFinite(Point.period) && Point.period > 0 && Number.isFinite(Point.value))
          .sort((A, B) => A.period - B.period);
  if (!Points.length)
    return null;
  return {
    points : Points,
    yLabel : HasSde ? 'SDE' : 'BLS power',
    valueKey : HasSde ? 'sde' : 'power',
    method : Payload.method || CurrResult.period_method || 'period search',
    fullCount : IsFiniteNumber(Payload.point_count) ? Number(Payload.point_count) : Points.length,
    shownCount : IsFiniteNumber(Payload.shown_count) ? Number(Payload.shown_count) : Points.length,
  };
}

//MARK: period plot check
function HasPeriodogram()
{
  const Series = PeriodogramSeries();
  return Boolean(Series && Series.points.length);
}

//MARK: period plot bounds
function DomainForPeriodogram()
{
  const Series = PeriodogramSeries();
  if (!Series)
    return null;
  const XValues = Series.points.map(Point => Point.period);
  const YValues = Series.points.map(Point => Point.value);
  const XMin = Math.min(...XValues);
  const XMax = Math.max(...XValues);
  const YMinRaw = Math.min(...YValues, 0);
  const YMaxRaw = Math.max(...YValues, 0);
  const XPad = Math.max((XMax - XMin) * 0.015, XMax * 0.001, 1e-6);
  const YPad = Math.max((YMaxRaw - YMinRaw) * 0.12, 0.5);
  return {
    xMin : Math.max(0, XMin - XPad),
    xMax : XMax + XPad,
    yMin : YMinRaw - YPad,
    yMax : YMaxRaw + YPad,
  };
}

//MARK: plot title
function UpdateChartHeading()
{
  UpdateInspectorControls();
  if (!CurrResult)
  {
    ChartTitleEl.textContent = 'Flux Over Time';
    SubtitleEl.textContent = 'Transit boxes appear after analysis.';
    return;
  }

  if (CurrView === 'phase')
  {
    ChartTitleEl.textContent = 'Phase-Folded Light Curve';
    if (HasPhaseFold())
    {
      SubtitleEl.textContent = `Global periodic-signal check: ${
          CurrResult.phase_folded.phase.length.toLocaleString()} folded samples at P = ${
          Fmt(CurrResult.phase_folded
                  .period)} days. Use Full orbit to inspect secondary dips and orbital trends.`;
    }
    else
    {
      SubtitleEl.textContent = 'Phase folding needs a detected orbital period.';
    }
    return;
  }

  if (CurrView === 'stack')
  {
    ChartTitleEl.textContent = 'Transit Stack Inspector';
    if (HasTransitStack())
    {
      const TraceCount = CurrResult.transit_stack.traces.length;
      SubtitleEl.textContent = `Event-by-event consistency: ${
          TraceCount
              .toLocaleString()} local windows aligned on the ephemeris. Select an event to inspect depth, coverage, and timing. This is not an independent periodic-signal confirmation.`;
    }
    else
    {
      SubtitleEl.textContent =
          'Transit stacking needs detected transits; reanalyze older saved results to generate it.';
    }
    return;
  }

  if (CurrView === 'periodogram')
  {
    ChartTitleEl.textContent = 'Periodogram';
    const Series = PeriodogramSeries();
    if (Series)
    {
      SubtitleEl.textContent = `${Series.shownCount.toLocaleString()} plotted periods from ${
          Series.fullCount.toLocaleString()} searched. Higher ${
          Series.yLabel} means a stronger repeating transit candidate.`;
    }
    else
    {
      SubtitleEl.textContent = 'Periodogram data is not available for this run.';
    }
    return;
  }

  if (CurrView === 'audit')
  {
    ChartTitleEl.textContent = 'Ephemeris Audit';
    const Metrics = CurrentAnalysisMetrics();
    if (!IsFiniteNumber(Metrics.period) || !IsFiniteNumber(Metrics.periodEpoch))
    {
      SubtitleEl.textContent = 'Audit view needs a recovered period and epoch.';
    }
    else if (IsFiniteNumber(Metrics.ephemerisMatchCount) && IsFiniteNumber(Metrics.ephemerisMatchFraction))
    {
      const MatchCount = Number(Metrics.ephemerisMatchCount);
      const Total = CurrResult.transits.length;
      SubtitleEl.textContent = `${MatchCount} independently supported events align with the ${
          Fmt(Metrics.period, 5)} day ephemeris; ${
          Total} predicted windows. Timing is available only where independently measured.`;
    }
    else
    {
      SubtitleEl.textContent = `Predicted windows are shown for the ${Fmt(Metrics.period, 5)} day ephemeris.`;
    }
    return;
  }

  if (CurrView === 'comparison')
  {
    ChartTitleEl.textContent = 'Fit and Residuals';
    SubtitleEl.textContent =
        ComparisonPayload()?.representation ||
        'Matched search data and evaluated model; residuals are observations minus model. Reanalyze legacy caches to generate this view.';
    return;
  }
  ChartTitleEl.textContent = 'Flux Over Time';
  SubtitleEl.textContent = `${CurrResult.plot.time.length.toLocaleString()} plotted points from ${
      CurrResult.total_points.toLocaleString()} samples. Days since ${
      FmtReference(CurrResult.time_reference)}; ${
      CurrResult.input_metadata?.time_format || 'time convention unverified'}.`;
}

//MARK: timing checks
function EphemerisDiagnosticsForTransits(Transits, Period, Epoch, Duration, ExpectedCount,
                                         ObservedRanges = null)
{
  const Centers =
      Transits.map(Transit => NullableNumber(Transit.center)).filter(Value => Number.isFinite(Value));
  const Durations = Transits.map(Transit => NullableNumber(Transit.duration))
                        .filter(Value => Number.isFinite(Value) && Value > 0);
  const PeriodValue = Number(Period);
  const EpochValue = Number(Epoch);
  const DurationValue = Number(Duration);
  const ExpectedValue = Number(ExpectedCount);
  const Empty = {
    ephemerisMatchCount : null,
    ephemerisMatchFraction : null,
    ephemerisEventMatchCount : null,
    ephemerisEventMatchFraction : null,
    offEphemerisTransitCount : null,
    offEphemerisFraction : null,
    expectedTransitCount : Number.isFinite(ExpectedValue) ? ExpectedValue : null,
    expectedTransitCoverage : null,
    timingResidualMedian : null,
    timingResidualMax : null,
    timingResidualTolerance : null,
    timingResidualRatio : null,
  };

  if (!Centers.length || !Number.isFinite(PeriodValue) || PeriodValue <= 0 || !Number.isFinite(EpochValue))
  {
    return Empty;
  }

  const MedianDuration = Median(Durations);
  const DurationScale =
      Math.max(Number.isFinite(DurationValue) ? DurationValue : 0, MedianDuration || 0, PeriodValue * 0.035);
  const Tolerance = Math.min(Math.max(DurationScale * 1.5, PeriodValue * 0.025), PeriodValue * 0.18);
  if (!Number.isFinite(Tolerance) || Tolerance <= 0)
    return Empty;

  const Residuals = Centers.map(Center =>
  {
    const Cycles = Math.round((Center - EpochValue) / PeriodValue);
    return Math.abs(Center - (EpochValue + Cycles * PeriodValue));
  });
  const MatchedCycles = new Set();
  const MatchedResiduals = [];
  Residuals.forEach((Residual, Index) =>
  {
    if (Residual <= Tolerance)
    {
      MatchedResiduals.push(Residual);
      MatchedCycles.add(Math.round((Centers[Index] - EpochValue) / PeriodValue));
    }
  });
  const MatchCount = MatchedResiduals.length;
  const EventMatchCount = MatchedCycles.size;
  const OffCount = Centers.length - MatchCount;
  const ResidualMedian = Median(Residuals);
  const ObservedCycles = EphemerisCyclesInObservedRanges(PeriodValue, EpochValue, Tolerance, ObservedRanges);
  const ExpectedObservedCount =
      ObservedCycles.size || (Number.isFinite(ExpectedValue) && ExpectedValue > 0 ? ExpectedValue : null);
  const ExpectedCoverage =
      ExpectedObservedCount ? Math.min(1, EventMatchCount / ExpectedObservedCount) : null;

  return {
    ephemerisMatchCount : MatchCount,
    ephemerisMatchFraction : MatchCount / Centers.length,
    ephemerisEventMatchCount : EventMatchCount,
    ephemerisEventMatchFraction : ExpectedObservedCount ? EventMatchCount / ExpectedObservedCount : null,
    offEphemerisTransitCount : OffCount,
    offEphemerisFraction : OffCount / Centers.length,
    expectedTransitCount : ExpectedObservedCount || (Number.isFinite(ExpectedValue) ? ExpectedValue : null),
    expectedTransitCoverage : ExpectedCoverage,
    timingResidualMedian : ResidualMedian,
    timingResidualMax : Residuals.length ? Math.max(...Residuals) : null,
    timingResidualTolerance : Tolerance,
    timingResidualRatio : ResidualMedian === null ? null : ResidualMedian / Tolerance,
  };
}

//MARK: timing tolerance
function EphemerisTolerance(Period, Duration, Transits)
{
  const PeriodValue = Number(Period);
  if (!Number.isFinite(PeriodValue) || PeriodValue <= 0)
    return null;
  const DurationValue = Number(Duration);
  const TransitDurations = (Transits || [])
                               .map(Transit => NullableNumber(Transit.duration))
                               .filter(Value => Number.isFinite(Value) && Value > 0);
  const MedianDuration = Median(TransitDurations);
  const DurationScale =
      Math.max(Number.isFinite(DurationValue) ? DurationValue : 0, MedianDuration || 0, PeriodValue * 0.035);
  const Tolerance = Math.min(Math.max(DurationScale * 1.5, PeriodValue * 0.025), PeriodValue * 0.18);
  return Number.isFinite(Tolerance) && Tolerance > 0 ? Tolerance : null;
}

//MARK: close timing match
function IsDenseRegularityMatch(MatchCount, EventCount, ExpectedCoverage, TransitCount)
{
  if (!IsFiniteNumber(MatchCount) || !IsFiniteNumber(EventCount) || !IsFiniteNumber(ExpectedCoverage) ||
      !IsFiniteNumber(TransitCount) || Number(TransitCount) < 12)
  {
    return false;
  }
  const Total = Number(TransitCount);
  const DenseBoxFloor = Math.max(6, Math.ceil(Total * 0.35));
  return (Number(MatchCount) >= DenseBoxFloor && Number(EventCount) >= 3 &&
          Number(MatchCount) / Total >= 0.35 && Number(ExpectedCoverage) >= 0.3);
}

//MARK: timing offset
function EphemerisResidual(Center, Period, Epoch)
{
  const CenterValue = Number(Center);
  const PeriodValue = Number(Period);
  const EpochValue = Number(Epoch);
  if (!Number.isFinite(CenterValue) || !Number.isFinite(PeriodValue) || PeriodValue <= 0 ||
      !Number.isFinite(EpochValue))
  {
    return null;
  }
  const Cycles = Math.round((CenterValue - EpochValue) / PeriodValue);
  const PredictedCenter = EpochValue + Cycles * PeriodValue;
  return {
    cycles : Cycles,
    predictedCenter : PredictedCenter,
    residual : Math.abs(CenterValue - PredictedCenter),
  };
}

//MARK: event timing status
function ClassifyTransitForEphemeris(Transit, Metrics = CurrentAnalysisMetrics())
{
  // a predicted center is not an independently measured event time.
  const MeasuredCenter = NullableNumber(Transit.measured_center);
  if (MeasuredCenter === null && (Transit.source === 'TLS model' || Transit.state))
  {
    return {status : 'unknown', residual : null, tolerance : null, predictedCenter : null};
  }
  const Tolerance =
      EphemerisTolerance(Metrics.period, Metrics.periodDuration, CurrResult ? CurrResult.transits : []);
  const Residual = EphemerisResidual(MeasuredCenter ?? Transit.center, Metrics.period, Metrics.periodEpoch);
  if (!Residual || Tolerance === null)
  {
    return {status : 'unknown', residual : null, tolerance : null, predictedCenter : null};
  }
  return {
    status : Residual.residual <= Tolerance ? 'matched' : 'off',
    residual : Residual.residual,
    tolerance : Tolerance,
    predictedCenter : Residual.predictedCenter,
  };
}

//MARK: predicted cycles
function PredictedEphemerisEvents(Metrics, Domain = CurrResult ? CurrResult.domain : null)
{
  if (!Domain)
    return [];
  const Period = Number(Metrics.period);
  const Epoch = Number(Metrics.periodEpoch);
  if (!Number.isFinite(Period) || Period <= 0 || !Number.isFinite(Epoch))
    return [];
  const Tolerance =
      EphemerisTolerance(Metrics.period, Metrics.periodDuration, CurrResult ? CurrResult.transits : []);
  const ObservedRanges = ObservationRangesForResult(CurrResult, Domain);
  const FirstCycle = Math.ceil((Domain.time_min - Epoch) / Period) - 1;
  const LastCycle = Math.floor((Domain.time_max - Epoch) / Period) + 1;
  const Events = [];
  for (let Cycle = FirstCycle; Cycle <= LastCycle; Cycle++)
  {
    const Center = Epoch + Cycle * Period;
    if (Center < Domain.time_min - Period || Center > Domain.time_max + Period)
      continue;
    const EventStart = Tolerance === null ? Center : Center - Tolerance;
    const EventEnd = Tolerance === null ? Center : Center + Tolerance;
    const OverlapsObservedData =
        !ObservedRanges.length ||
        ObservedRanges.some(Range => (EventEnd >= Range.start && EventStart <= Range.end));
    if (!OverlapsObservedData)
      continue;
    Events.push({
      cycle : Cycle,
      center : Center,
      start : EventStart,
      end : EventEnd,
    });
  }
  return Events;
}

//MARK: curve measurements
function CurrentAnalysisMetrics()
{
  const DepthFractions = CurrResult.transits.map(EventSignedDepthFraction).filter(Number.isFinite);
  const RadiusRatios = CurrResult.transits.map(Transit => NullableNumber(Transit.radius_ratio))
                           .filter(Value => Number.isFinite(Value) && Value >= 0);
  const TransitPoints = CurrResult.transits.map(Transit => NullableNumber(Transit.points))
                            .filter(Value => Number.isFinite(Value) && Value >= 0);
  const Metrics = {
    period : CurrResult.period,
    periodMethod : CurrResult.period_method,
    periodScatter : CurrResult.period_scatter,
    periodUncertainty : CurrResult.period_uncertainty,
    periodMatchCount : CurrResult.period_match_count,
    pValue : CurrResult.p_value,
    deltaChiSquared : CurrResult.delta_chi_squared,
    reducedChiSquared : CurrResult.reduced_chi_squared_box,
    periodEpoch : IsFiniteNumber(CurrResult.period_epoch)
                      ? Number(CurrResult.period_epoch) - Number(CurrResult.time_reference || 0)
                      : null,
    periodDuration : CurrResult.period_duration,
    periodSde : CurrResult.period_sde,
    tlsSdeRaw : CurrResult.tls_sde_raw,
    tlsFap : CurrResult.tls_fap,
    tlsSnr : CurrResult.tls_snr,
    tlsOddEvenMismatchSigma : CurrResult.tls?.odd_even_mismatch_sigma ?? null,
    medianDepthFraction : Median(DepthFractions),
    medianRadiusRatio : Median(RadiusRatios),
    detectionSnr : CurrResult.detection_snr,
    oddEvenDepthMismatch : CurrResult.odd_even_depth_mismatch,
    depthScatterRatio : CurrResult.depth_scatter_ratio,
    medianTransitPoints : Median(TransitPoints),
    maxRadiusRatio : RadiusRatios.length ? Math.max(...RadiusRatios) : null,
  };

  //MARK: saved diagnostics
  const Diagnostics = CurrResult.diagnostics || {};
  const Keys = {
    ephemeris_match_count : 'ephemerisMatchCount',
    ephemeris_match_fraction : 'ephemerisMatchFraction',
    ephemeris_event_match_count : 'ephemerisEventMatchCount',
    ephemeris_event_match_fraction : 'ephemerisEventMatchFraction',
    off_ephemeris_transit_count : 'offEphemerisTransitCount',
    off_ephemeris_fraction : 'offEphemerisFraction',
    expected_transit_count : 'expectedTransitCount',
    expected_transit_coverage : 'expectedTransitCoverage',
    timing_residual_median : 'timingResidualMedian',
    timing_residual_tolerance : 'timingResidualTolerance',
    timing_residual_ratio : 'timingResidualRatio',
  };
  for (const [Source, Destination] of Object.entries(Keys))
    Metrics[Destination] = NullableNumber(Diagnostics[Source]);
  Metrics.observedEventCount =
      Array.isArray(CurrResult.observed_events) ? CurrResult.observed_events.length : null;
  if (Metrics.periodMethod === 'TLS' && !Array.isArray(CurrResult.observed_events))
  {
    Metrics.ephemerisMatchCount = null;
    Metrics.ephemerisMatchFraction = null;
  }

  return Metrics;
}

//MARK: curve warnings
function CurrentWarnings()
{
  if (!CurrResult)
    return [];
  return Array.isArray(CurrResult.warnings) ? CurrResult.warnings : [
    {
      severity : 'info',
      title : 'Legacy analysis',
      detail : 'Saved warnings are unavailable. Reanalyze to run current checks.'
    },
  ];
}

//MARK: saved verdict
function CurrentPlanetAssessment(Metrics = null, Warnings = null)
{
  if (!CurrResult)
    return null;
  // reopening a result should show its saved verdict, not score it again.
  const Saved = CurrResult.planet_assessment;
  if (!Saved || typeof Saved !== 'object')
    return {
      status : 'legacy_unknown',
      title : 'Legacy analysis — assessment unavailable',
      shortLabel : 'Legacy / unassessed',
      candidateScore : null,
      summary : 'This cache has no saved backend assessment. Its measurements remain available.',
      recommendation : 'Reanalyze the source file to apply current checks.',
      supportingEvidence : [],
      limitingEvidence : [],
    };
  return {
    ...Saved,
    shortLabel : Saved.short_label || Saved.shortLabel || Saved.title || 'Unassessed',
    candidateScore : NullableNumber(Saved.candidate_score ?? Saved.candidateScore),
    supportingEvidence : Saved.supporting_evidence || Saved.supportingEvidence || [],
    limitingEvidence : Saved.limiting_evidence || Saved.limitingEvidence || [],
    summary : Saved.summary || '',
    recommendation : Saved.recommendation || '',
  };
}

//MARK: read verdict
function AssessmentForResult(Result)
{
  if (!Result)
    return {shortLabel : 'Pending', candidateScore : null, status : 'pending'};
  const PreviousResult = CurrResult;
  CurrResult = Result;
  try
  {
    const Metrics = CurrentAnalysisMetrics();
    return CurrentPlanetAssessment(Metrics, CurrentWarnings(Metrics));
  }
  finally
  {
    CurrResult = PreviousResult;
  }
}

//MARK: evidence text
function EvidenceListHtml(Items)
{
  return Items.slice(0, 6)
      .map(Item => `
    <div>
      <strong>${EscapeHtml(Item.title)}</strong>
      <span>${EscapeHtml(Item.detail)}</span>
    </div>
  `).join('');
}

//MARK: verdict card
function RenderAssessment(Metrics = null, Warnings = null)
{
  if (!CurrResult)
    return;
  const ResolvedMetrics = Metrics || CurrentAnalysisMetrics();
  const ResolvedWarnings = Warnings || CurrentWarnings(ResolvedMetrics);
  const Assessment = CurrentPlanetAssessment(ResolvedMetrics, ResolvedWarnings);
  const EvidenceHtml = EvidenceListHtml([...Assessment.limitingEvidence, ...Assessment.supportingEvidence ]);
  AssessmentEl.innerHTML = `
    <div class="AssessmentCard ${CssTag(Assessment.status)}">
      <div class="AssessmentHead">
        <strong>${EscapeHtml(Assessment.title)}</strong>
        <span>${
      Assessment.candidateScore === null ? 'Unscored'
                                         : `Candidate score ${Assessment.candidateScore}/100`}</span>
      </div>
      <p>${EscapeHtml(Assessment.summary)}</p>
      <div class="ScoreTrack" aria-label="Candidate score">
        <div class="ScoreFill" style="width: ${Assessment.candidateScore ?? 0}%;"></div>
      </div>
      <p>${EscapeHtml(Assessment.recommendation)}</p>
      ${EvidenceHtml ? `<div class="AssessmentEvidence">${EvidenceHtml}</div>` : ''}
    </div>
  `;
}

//MARK: warning cards
function RenderWarnings(Warnings = null)
{
  if (!CurrResult)
    return;
  const ResolvedWarnings = Warnings || CurrentWarnings();
  if (!ResolvedWarnings.length)
  {
    WarningsEl.innerHTML = `
      <div class="WarningItem Info">
        <strong>No major warnings</strong>
        <span>These checks are heuristic and do not prove the candidate is planetary.</span>
      </div>
    `;
    return;
  }
  WarningsEl.innerHTML = ResolvedWarnings
                             .map(Warning => `
    <div class="WarningItem ${CssTag(Warning.severity)}">
      <strong>${EscapeHtml(Warning.title)}</strong>
      <span>${EscapeHtml(Warning.detail)}</span>
    </div>
  `).join('');
}

//MARK: other periods
function RenderPeriodCandidates()
{
  if (!CurrResult)
    return;
  const Candidates = (CurrResult.period_candidates || []).slice(0, 5);
  if (!Candidates.length)
  {
    PeriodCandidatesEl.innerHTML = `
      <div class="WarningItem Info">
        <strong>No period grid</strong>
        <span>Only candidate-box spacing is available for this run.</span>
      </div>
    `;
    return;
  }
  PeriodCandidatesEl.innerHTML = Candidates
                                     .map((Candidate, Index) => `
    <div class="WarningItem ${Index === 0 ? 'Info' : 'Caution'}">
      <strong>${Fmt(Candidate.period, 4)} days</strong>
      <span>${Candidate.method ? `${EscapeHtml(Candidate.method)}; ` : ''}Power ${Fmt(Candidate.power, 2)}${
                                              Candidate.sde === null || Candidate.sde === undefined
                                                  ? ''
                                                  : `, SDE ${Fmt(Candidate.sde, 2)}`}</span>
    </div>
  `).join('');
}

//MARK: measurement rows
function RenderMetrics()
{
  if (!CurrResult)
    return;
  const Metrics = CurrentAnalysisMetrics();
  const Warnings = CurrentWarnings(Metrics);
  const Period =
      Metrics.period === null || Metrics.period === undefined
          ? 'Not enough transits'
          : `${Fmt(Metrics.period)} days${Metrics.periodMethod ? ` (${Metrics.periodMethod})` : ''}`;
  const EphemerisFit =
      (Metrics.ephemerisMatchCount === null || Metrics.ephemerisMatchCount === undefined ||
       Metrics.ephemerisMatchFraction === null || Metrics.ephemerisMatchFraction === undefined)
          ? '-'
          : `${Metrics.ephemerisMatchCount}/${CurrResult.transits.length} (${
                Fmt(Metrics.ephemerisMatchFraction * 100, 0)}%)`;

  RenderAssessment(Metrics, Warnings);
  MetricsEl.innerHTML = `
    <div class="Metric"><span>Data points</span><span>${CurrResult.total_points.toLocaleString()}</span></div>
    <div class="Metric"><span>Supported events / covered windows</span><span>${
      Metrics.observedEventCount ?? 'unverified'} / ${CurrResult.transits.length}</span></div>
    <div class="Metric"><span>All predicted windows</span><span>${
      CurrResult.predicted_windows?.length ?? 'not recorded'}</span></div>
    <div class="Metric"><span>Orbital period</span><span>${Period}</span></div>
    <div class="Metric"><span>Period uncertainty</span><span>${
      Metrics.periodUncertainty === null || Metrics.periodUncertainty === undefined
          ? '-'
          : `± ${Fmt(Metrics.periodUncertainty, 6)} days`}</span></div>
    <div class="Metric"><span>Local median depth</span><span>${
      FmtDepthPercent(Metrics.medianDepthFraction)} / ${
      FmtPpm(Metrics.medianDepthFraction === null ? null
                                                  : Metrics.medianDepthFraction * 1000000)} ppm</span></div>
    <div class="Metric"><span>Radius ratio</span><span>${Fmt(Metrics.medianRadiusRatio)}</span></div>
    <div class="Metric"><span>${Metrics.periodMethod === 'TLS' ? 'TLS SNR' : 'Depth SNR'}</span><span>${
      Fmt(Metrics.detectionSnr, 2)}</span></div>
    <div class="Metric"><span>Period SDE</span><span>${Fmt(Metrics.periodSde, 2)}</span></div>
    <div class="Metric"><span>TLS false-alarm probability</span><span>${
      Metrics.periodMethod === 'TLS' ? FmtPercent(Metrics.tlsFap) : '-'}</span></div>
    <div class="Metric"><span>Measured timing agreement</span><span>${EphemerisFit}</span></div>
    <div class="Metric"><span>Approx. model-vs-flat p-value</span><span>${
      FmtPercent(Metrics.pValue)}</span></div>
    <div class="Metric"><span>Reduced chi-sq</span><span>${Fmt(Metrics.reducedChiSquared, 3)}</span></div>
    <div class="Metric"><span>Time reference</span><span>${
      FmtReference(CurrResult.time_reference)}</span></div>
    <div class="Metric"><span>Median flux</span><span>${Fmt(CurrResult.median_flux)}</span></div>
    <div class="Metric"><span>Noise</span><span>${Fmt(CurrResult.robust_noise)}</span></div>
  `;
  RenderPeriodCandidates();
  RenderWarnings(Warnings);
}

//MARK: event rows
function RenderTransitRows()
{
  if (!CurrResult)
    return;
  RowsEl.innerHTML =
      CurrResult.transits.length
          ? CurrResult.transits
                .map((T, Index) => `
    <tr>
      <td>Window ${Index + 1}<br><small>${EscapeHtml(T.state || 'Legacy: unverified support')}</small></td>
      <td>${Fmt(T.start)}</td>
      <td>${Fmt(T.center)}</td>
      <td>${Fmt(T.end)}</td>
      <td>${DurationLabel(T.duration)}</td>
      <td>${Fmt(T.depth)}</td>
      <td>${FmtDepthPercent(EventSignedDepthFraction(T))}</td>
      <td>${FmtPpm(EventSignedDepthFraction(T) === null ? null : EventSignedDepthFraction(T) * 1000000)}</td>
      <td>${Fmt(T.radius_ratio)}</td>
      <td>${Fmt(T.points, 0)}</td>
    </tr>
  `).join('')
          : '<tr><td colspan="10" style="text-align:left;color:#60656f;">No statistically strong transit candidates found.</td></tr>';
}

//MARK: signed event depth
function EventSignedDepthFraction(UiEvent)
{
  // keep brightenings negative instead of dropping them from the summary.
  const Signed = NullableNumber(UiEvent.signed_depth);
  const Baseline = NullableNumber(UiEvent.local_baseline) ?? NullableNumber(CurrResult?.median_flux);
  if (Signed !== null && Baseline > 0)
    return Signed / Baseline;
  return NullableNumber(UiEvent.depth_fraction);
}

//MARK: exposure text
function ExposureSummary(Metadata)
{
  // the gap between samples does not tell us how long the exposure was.
  if (!Metadata)
    return 'Not recorded; cadence is not a verified exposure duration';
  const Known = NullableNumber(Metadata.known_rows) || 0;
  const Unknown = NullableNumber(Metadata.unknown_rows) || 0;
  if (!Known)
    return 'Unknown; template evaluated as instantaneous. Exposure smearing uncertainty is not included.';
  const Low = NullableNumber(Metadata.minimum_seconds), High = NullableNumber(Metadata.maximum_seconds);
  const Duration = Low === High ? `${Fmt(Low, 2)} s` : `${Fmt(Low, 2)}–${Fmt(High, 2)} s`;
  return `${Duration}; ${Known.toLocaleString()} declared samples (${
             Metadata.source || 'source unspecified'})` +
         (Unknown ? `; ${Unknown.toLocaleString()} unknown samples use the instantaneous approximation` : '');
}

//MARK: run details
function RenderMetadata()
{
  if (!CurrResult || !MetadataEl)
    return;
  const Result = CurrResult;
  const Provenance = Result.provenance || {};
  const Settings =
      Result.effective_settings || Provenance.effective_settings || Result.detection_options || {};
  const Cleaning = Result.cleaning || Result.cleaning_report || {};
  const Input = Result.input_metadata || {};
  const Pairs = [
    [ 'Analyzed at', Result.analyzed_at || Provenance.analyzed_at || 'Unknown (legacy analysis)' ],
    [
      'Local dips (unvalidated)',
      `${
          MainResult?.exploratory_dips?.length ?? Result.exploratory_dips?.length ??
          'not recorded'}; these do not count as detected planets or supported events`
    ],
    [
      'Analysis version',
      Provenance.analysis_version || Result.analysis_version || 'Unknown (legacy analysis)'
    ],
    [ 'Result schema', Result.result_schema_version ?? Provenance.result_schema_version ?? 'Legacy' ],
    [ 'Time format / scale', `${Input.time_format || 'unknown'} / ${Input.time_scale || 'unknown'}` ],
    [ 'Exposure', ExposureSummary(Result.exposure_metadata) ],
    [ 'Normalization', Result.normalization?.method || 'Unknown' ],
    [ 'Local depth', 'Median measured event depth; signed depths and uncertainty are retained per event.' ],
    [ 'Model depth', FmtDepthPercent(Result.tls?.depth_fraction) ],
    [
      'Duration / source',
      `${DurationLabel(Result.period_duration)} / ${Result.tls?.duration_source || 'not recorded'}`
    ],
  ];
  const ObjectRows = (Label, DataObject) =>
      Object.keys(DataObject).length ? `<details><summary>${EscapeHtml(Label)}</summary><pre>${
                                           EscapeHtml(JSON.stringify(DataObject, null, 2))}</pre></details>`
                                     : '';
  MetadataEl.innerHTML =
      Pairs
          .map(([ Key, Value ]) => `<div class="Metric"><span>${EscapeHtml(Key)}</span><span>${
                   EscapeHtml(Value)}</span></div>`)
          .join('') +
      "<p class=\"MetadataNote\">The approximate model-vs-flat p-value is not a search-wide false-alarm probability. Candidate scores are not probabilities.</p>" +
      ObjectRows('Cleaning report', Cleaning) + ObjectRows('Effective search settings', Settings) +
      ObjectRows('Input metadata', Input) + ObjectRows('Exposure details', Result.exposure_metadata || {}) +
      ObjectRows('Execution and ETA audit', Result.execution || {}) +
      ObjectRows('Search sample context', Result.search_context || {}) +
      ObjectRows('Dependency versions', Provenance.dependency_versions || {});
}

//MARK: signal picker
function RenderSignalPicker()
{
  const Signals = MainResult?.signals || [];
  document.getElementById("SignalControl").hidden = Signals.length < 2;
  const Previous = SignalPickThing.value;
  SignalPickThing.innerHTML =
      Signals
          .map((S, I) => `<option value="${I}">${EscapeHtml(S.label || `Signal ${I + 1}`)} · ${
                   Fmt(S.period, 5)} d</option>`)
          .join('');
  if (MainResult?.joint_model_comparison)
    SignalPickThing.innerHTML += '<option value="combined">Combined fit and residuals</option>';
  if (Previous === 'combined' && CurrResult === MainResult)
  {
    SignalPickThing.value = 'combined';
    return;
  }
  SignalPickThing.value = Signals.some((S, I) => String(I) === Previous && S === CurrResult)
                              ? Previous
                              : String(Math.max(0, Signals.indexOf(CurrResult)));
}

//MARK: stack event index
function TraceEventIndex(Trace, Fallback)
{
  const Value = NullableNumber(Trace?.transit_index);
  return Value === null ? Fallback : Math.max(0, Value - 1);
}

//MARK: stack event list
function RenderStackEvents()
{
  const Selected = StackEventInput.value;
  const Traces = CurrResult?.transit_stack?.traces || [];
  StackEventInput.innerHTML =
      '<option value="all">All events</option>' +
      Traces
          .map((Trace, Index) =>
          {
            const UiEvent = CurrResult.transits?.[TraceEventIndex(Trace, Index)];
            return `<option value="${Index}">Window ${(TraceEventIndex(Trace, Index)) + 1} · day ${
                Fmt(UiEvent?.center, 3)} · ${EscapeHtml(UiEvent?.state || 'support unverified')}</option>`;
          })
          .join('');
  StackEventInput.value = Selected !== 'all' && Number(Selected) < Traces.length ? Selected : 'all';
}

//MARK: inspector controls
function UpdateInspectorControls()
{
  document.getElementById("PhaseScopeControl").hidden = CurrView !== 'phase';
  document.getElementById("StackControls").hidden = CurrView !== 'stack';
  document.getElementById("LocalDipsControl").hidden =
      !['zoom', 'clean', 'raw', 'audit'].includes(CurrView) ||
      !(MainResult?.exploratory_dips?.length || CurrResult?.exploratory_dips?.length);
  const Quality = CurrResult?.fit_quality;
  document.getElementById("FitQualityLabel").textContent =
      !CurrResult ? ''
                  : (Quality?.label ||
                     (IsTentativeModel() ? 'Tentative fit — below candidate threshold' : 'Fitted model'));
  const Element = document.getElementById("EventInspection");
  Element.hidden = CurrView !== 'stack';
  const Trace = CurrResult?.transit_stack?.traces?.[Number(StackEventInput.value)];
  const UiEvent = StackEventInput.value === 'all'
                      ? null
                      : CurrResult?.transits?.[TraceEventIndex(Trace, Number(StackEventInput.value))];
  Element.textContent =
      UiEvent
          ? `Window ${Number(StackEventInput.value) + 1}: cycle ${UiEvent.cycle_number ?? 'unknown'}; ${
                UiEvent.state || 'support unverified'}; signed depth ${
                FmtDepthPercent(UiEvent.signed_depth ?? UiEvent.depth_fraction)} ± ${
                FmtDepthPercent(
                    UiEvent.depth_uncertainty)}; local SNR ${Fmt(UiEvent.local_snr, 2)}; coverage ${
                IsFiniteNumber(UiEvent.coverage_fraction)
                    ? Fmt(UiEvent.coverage_fraction * 100, 0) + '%'
                    : 'unknown'}; measured center ${Fmt(UiEvent.measured_center)} d ± ${
                DurationLabel(
                    UiEvent
                        .timing_uncertainty)}. Recentring shifts only the display; fitted ephemeris is unchanged.`
          : 'Select an event to highlight its measurements. Odd/even groups use orbital cycle number. Legacy events without cycle metadata remain unclassified.';
}

//MARK: tentative model check
function IsTentativeModel()
{
  if (CurrResult?.fit_quality)
    return CurrResult.fit_quality.state !== 'accepted';
  return !['strong_candidate', 'possible_candidate'].includes(CurrResult?.planet_assessment?.status);
}

//MARK: model line style
function ApplyModelStyle(Width = 2)
{
  FluxPen.strokeStyle = IsTentativeModel() ? '#9c8979' : '#b45309';
  FluxPen.lineWidth = Width;
  FluxPen.setLineDash(IsTentativeModel() ? [ 6, 5 ] : []);
}

//MARK: line gaps
function DrawSeriesPath(Xs, Ys, XScale, YScale, Viewport,
                        {breakIndices : BreakIndices = [], timeSeries : TimeSeries = false} = {})
{
  // missing samples and observing gaps need a new path, not a connecting line.
  const Breaks = new Set(BreakIndices);
  const Positive = [];
  if (!TimeSeries)
    for (let I = 1; I < Xs.length; I++)
      if (IsFiniteNumber(Xs[I]) && IsFiniteNumber(Xs[I - 1]) && Xs[I] > Xs[I - 1])
        Positive.push(Xs[I] - Xs[I - 1]);
  const Gap = Median(Positive) * 8;
  const Ranges = TimeSeries ? ObservationRangesForResult(CurrResult) : [];
  let Open = false;
  let Previous = null;
  FluxPen.beginPath();
  for (let I = 0; I < Math.min(Xs.length, Ys.length); I++)
  {
    const X = NullableNumber(Xs[I]), Y = NullableNumber(Ys[I]);
    if (X === null || Y === null || X < Viewport.xMin || X > Viewport.xMax)
    {
      Open = false;
      Previous = null;
      continue;
    }
    const CrossesGap = Previous !== null &&
                       (TimeSeries ? Ranges.some(R => Previous <= R.end && X > R.end && Previous >= R.start)
                                   : (Gap > 0 && X - Previous > Gap));
    if (!Open || Breaks.has(I) || CrossesGap)
      FluxPen.moveTo(XScale(X), YScale(Y));
    else
      FluxPen.lineTo(XScale(X), YScale(Y));
    Open = true;
    Previous = X;
  }
  FluxPen.stroke();
}

//MARK: export funcs
function ExportBaseName()
{
  const FileStem = CurrFile ? CurrFile.name.replace(/\.[^/.]+$/, '') : 'transit-analysis';
  const SafeStem = FileStem.replace(/[^a-z0-9_-]+/gi, '-').replace(/^-+|-+$/g, '');
  return SafeStem || 'transit-analysis';
}

//MARK: download file
function DownloadBlob(Content, Filename, Type)
{
  const DownloadData = Content instanceof Blob ? Content : new Blob([ Content ], {type : Type});
  const Url = URL.createObjectURL(DownloadData);
  const Link = document.createElement('a');
  Link.href = Url;
  Link.download = Filename;
  document.body.appendChild(Link);
  Link.click();
  Link.remove();
  URL.revokeObjectURL(Url);
}

//MARK: csv text
function CsvCell(Value)
{
  if (Value === null || Value === undefined)
    return '';
  const Text = String(Value);
  return /[",\n]/.test(Text) ? `"${Text.replace(/"/g, '""')}"` : Text;
}

//MARK: csv event rows
function TransitRowsForExport()
{
  // relative days are still usable when the absolute time format is unknown.
  return CurrResult.transits.map((Transit, Index) => ({
                                   transit : Index + 1,
                                   start_day : Transit.start,
                                   center_day : Transit.center,
                                   end_day : Transit.end,
                                   start_jd : [ 'jd', 'bjd', 'mjd', 'bkjd', 'btjd' ].includes(
                                                  CurrResult.input_metadata?.time_format?.toLowerCase())
                                                  ? CurrResult.time_reference + Transit.start
                                                  : null,
                                   center_jd : [ 'jd', 'bjd', 'mjd', 'bkjd', 'btjd' ].includes(
                                                   CurrResult.input_metadata?.time_format?.toLowerCase())
                                                   ? CurrResult.time_reference + Transit.center
                                                   : null,
                                   end_jd : [ 'jd', 'bjd', 'mjd', 'bkjd', 'btjd' ].includes(
                                                CurrResult.input_metadata?.time_format?.toLowerCase())
                                                ? CurrResult.time_reference + Transit.end
                                                : null,
                                   duration_days : Transit.duration,
                                   depth : Transit.depth,
                                   depth_fraction : Transit.depth_fraction,
                                   depth_percent : Transit.depth_percent,
                                   depth_ppm : Transit.depth_ppm,
                                   radius_ratio : Transit.radius_ratio,
                                   depth_basis : Transit.depth_basis,
                                   points : Transit.points,
                                   state : Transit.state || 'legacy_unverified',
                                   cycle_number : Transit.cycle_number ?? null,
                                   signed_depth : Transit.signed_depth ?? null,
                                   signed_depth_fraction : EventSignedDepthFraction(Transit),
                                   depth_uncertainty : Transit.depth_uncertainty ?? null,
                                   measured_center_day : Transit.measured_center ?? null,
                                   timing_uncertainty_days : Transit.timing_uncertainty ?? null,
                                   local_snr : Transit.local_snr ?? null,
                                   coverage_fraction : Transit.coverage_fraction ?? null,
                                   time_reference : CurrResult.time_reference,
                                   time_format : CurrResult.input_metadata?.time_format || 'unknown',
                                   time_scale : CurrResult.input_metadata?.time_scale || 'unknown',
                                 }));
}

//MARK: export csv
function ExportTransitCsv()
{
  if (!CurrResult)
    return;
  const Rows = TransitRowsForExport();
  const HttpHeaders = [
    'transit',
    'start_day',
    'center_day',
    'end_day',
    'start_jd',
    'center_jd',
    'end_jd',
    'duration_days',
    'depth',
    'depth_fraction',
    'depth_percent',
    'depth_ppm',
    'radius_ratio',
    'depth_basis',
    'points',
    'state',
    'cycle_number',
    'signed_depth',
    'signed_depth_fraction',
    'depth_uncertainty',
    'measured_center_day',
    'timing_uncertainty_days',
    'local_snr',
    'coverage_fraction',
    'time_reference',
    'time_format',
    'time_scale',
  ];
  const Csv = [
    HttpHeaders.join(','),
    ...Rows.map(Row => HttpHeaders.map(Header => CsvCell(Row[Header])).join(',')),
  ].join('\n');
  DownloadBlob(Csv, `${ExportBaseName()}-transits.csv`, 'text/csv;charset=utf-8');
  SetStatus('Transit CSV exported.');
}

//MARK: json fields
function SummaryForExport()
{
  // export the settings used for this result, not the current control values.
  const Metrics = CurrentAnalysisMetrics();
  const Warnings = CurrentWarnings(Metrics);
  const PlanetAssessment = CurrentPlanetAssessment(Metrics, Warnings);
  return {
    exported_at : new Date().toISOString(),
    source_file : CurrFile ? CurrFile.name : null,
    chart_view : CurrView,
    total_points : CurrResult.total_points,
    time_reference : CurrResult.time_reference,
    time_reference_jd :
        [ 'jd', 'bjd', 'mjd', 'bkjd', 'btjd' ].includes(CurrResult.input_metadata?.time_format?.toLowerCase())
            ? CurrResult.time_reference
            : null,
    time_unit : CurrResult.time_unit,
    flux_unit : CurrResult.flux_unit,
    normalization : CurrResult.normalization,
    detection_options : CurrResult.detection_options,
    planet_assessment : CurrResult.planet_assessment || PlanetAssessment,
    result_schema_version : CurrResult.result_schema_version ?? null,
    provenance : CurrResult.provenance || {analysis_version : 'unknown', analyzed_at : null, legacy : true},
    analyzed_at : CurrResult.analyzed_at ?? CurrResult.provenance?.analyzed_at ?? null,
    input_metadata : CurrResult.input_metadata || {time_format : 'unknown', time_scale : 'unknown'},
    cleaning : CurrResult.cleaning || CurrResult.cleaning_report || null,
    effective_settings : CurrResult.effective_settings || null,
    exposure_metadata : CurrResult.exposure_metadata || null,
    execution : CurrResult.execution || MainResult?.execution || null,
    template_resolution : CurrResult.tls?.template_resolution || null,
    actual_period_grid : CurrResult.tls?.actual_period_grid || null,
    fit_quality : CurrResult.fit_quality || null,
    model_comparison : CurrResult.model_comparison || null,
    joint_model_comparison : MainResult?.joint_model_comparison || null,
    predicted_windows : CurrResult.predicted_windows || null,
    observed_events : CurrResult.observed_events || null,
    exploratory_dips : MainResult?.exploratory_dips || CurrResult.exploratory_dips || [],
    signals : MainResult?.signals || [],
    warnings : Warnings,
    diagnostics : {
      detection_snr : Metrics.detectionSnr,
      tls_snr : Metrics.tlsSnr,
      tls_fap : Metrics.tlsFap,
      tls_odd_even_mismatch_sigma : Metrics.tlsOddEvenMismatchSigma,
      odd_even_depth_mismatch : Metrics.oddEvenDepthMismatch,
      depth_scatter_ratio : Metrics.depthScatterRatio,
      ephemeris_match_count : Metrics.ephemerisMatchCount,
      ephemeris_match_fraction : Metrics.ephemerisMatchFraction,
      ephemeris_event_match_count : Metrics.ephemerisEventMatchCount,
      ephemeris_event_match_fraction : Metrics.ephemerisEventMatchFraction,
      off_ephemeris_transit_count : Metrics.offEphemerisTransitCount,
      off_ephemeris_fraction : Metrics.offEphemerisFraction,
      expected_transit_count : Metrics.expectedTransitCount,
      expected_transit_coverage : Metrics.expectedTransitCoverage,
      timing_residual_median : Metrics.timingResidualMedian,
      timing_residual_tolerance : Metrics.timingResidualTolerance,
      timing_residual_ratio : Metrics.timingResidualRatio,
    },
    metrics : {
      transit_count : CurrResult.transits.length,
      covered_window_count : CurrResult.transits.length,
      predicted_window_count : CurrResult.predicted_windows?.length ?? null,
      observed_event_count : CurrResult.observed_events?.length ?? null,
      orbital_period_days : Metrics.period,
      orbital_period_method : Metrics.periodMethod,
      orbital_period_scatter : Metrics.periodScatter,
      orbital_period_uncertainty : Metrics.periodUncertainty,
      harmonic_alias_corrected : Boolean(CurrResult.harmonic_alias_corrected),
      harmonic_alias_period : CurrResult.harmonic_alias_period ?? null,
      harmonic_alias_factor : CurrResult.harmonic_alias_factor ?? null,
      harmonic_alias_power_ratio : CurrResult.harmonic_alias_power_ratio ?? null,
      period_sample_count : Metrics.periodMatchCount,
      median_depth_fraction : Metrics.medianDepthFraction,
      median_depth_percent : Metrics.medianDepthFraction === null ? null : Metrics.medianDepthFraction * 100,
      median_depth_ppm : Metrics.medianDepthFraction === null ? null : Metrics.medianDepthFraction * 1000000,
      median_radius_ratio : Metrics.medianRadiusRatio,
      chi_square_p_value : Metrics.pValue,
      chi_square_p_value_percent :
          Metrics.pValue === null || Metrics.pValue === undefined ? null : Metrics.pValue * 100,
      delta_chi_squared : Metrics.deltaChiSquared,
      reduced_chi_squared : Metrics.reducedChiSquared,
      detection_snr : Metrics.detectionSnr,
      period_sde : Metrics.periodSde,
      tls_sde_raw : Metrics.tlsSdeRaw,
      tls_fap : Metrics.tlsFap,
      tls_snr : Metrics.tlsSnr,
      ephemeris_match_count : Metrics.ephemerisMatchCount,
      ephemeris_match_fraction : Metrics.ephemerisMatchFraction,
      ephemeris_event_match_count : Metrics.ephemerisEventMatchCount,
      ephemeris_event_match_fraction : Metrics.ephemerisEventMatchFraction,
      off_ephemeris_transit_count : Metrics.offEphemerisTransitCount,
      off_ephemeris_fraction : Metrics.offEphemerisFraction,
      median_flux : CurrResult.median_flux,
      robust_noise : CurrResult.robust_noise,
    },
    period_candidates : CurrResult.period_candidates || [],
    period_search : CurrResult.period_search || null,
    periodogram : CurrResult.periodogram || null,
    tls : CurrResult.tls || null,
    transits : TransitRowsForExport(),
  };
}

//MARK: export measurements
function MetricsForResult(Result)
{
  const PreviousResult = CurrResult;
  CurrResult = Result;
  try
  {
    return CurrentAnalysisMetrics();
  }
  finally
  {
    CurrResult = PreviousResult;
  }
}

const AnalysisPdfColumns = [
  {key : 'file', label : 'File', width : 200, align : 'left'},
  {key : 'assessment', label : 'Assessment', width : 160, align : 'left'},
  {key : 'score', label : 'Cand. score', width : 70, align : 'right'},
  {key : 'points', label : 'Samples', width : 75, align : 'right'},
  {key : 'supported', label : 'Supported', width : 75, align : 'right'},
  {key : 'transits', label : 'Windows', width : 75, align : 'right'},
  {key : 'period', label : 'Period (d)', width : 110, align : 'right'},
  {key : 'duration', label : 'Duration', width : 90, align : 'right'},
  {key : 'depthPercent', label : 'Local depth', width : 95, align : 'right'},
  {key : 'sde', label : 'SDE', width : 85, align : 'right'},
  {key : 'snr', label : 'Search SNR', width : 85, align : 'right'},
];

//MARK: pdf summary row
function AnalysisPdfRow(FileName, Result)
{
  const Metrics = MetricsForResult(Result);
  const Assessment = AssessmentForResult(Result);
  const DepthPpm = Metrics.medianDepthFraction === null || Metrics.medianDepthFraction === undefined
                       ? null
                       : Metrics.medianDepthFraction * 1000000;
  const PValuePercent = Metrics.pValue === null || Metrics.pValue === undefined ? null : Metrics.pValue * 100;
  return {
    file : FileName || Result.source_file || 'analysis',
    assessment : Assessment.shortLabel,
    score : Assessment.candidateScore === null ? '-' : Assessment.candidateScore.toString(),
    points : Result.total_points.toLocaleString(),
    transits : Result.transits.length.toString(),
    supported : Result.observed_events?.length?.toString() ?? 'unverified',
    duration : DurationLabel(Result.period_duration),
    ephemerisFit : (Metrics.ephemerisMatchCount === null || Metrics.ephemerisMatchCount === undefined ||
                    Metrics.ephemerisMatchFraction === null || Metrics.ephemerisMatchFraction === undefined)
                       ? '-'
                       : `${Metrics.ephemerisMatchCount}/${Result.transits.length}`,
    period : Fmt(Metrics.period, 6),
    method : Metrics.periodMethod || '-',
    depthPercent : FmtDepthPercent(Metrics.medianDepthFraction),
    depthPpm : FmtPpm(DepthPpm),
    radiusRatio : Fmt(Metrics.medianRadiusRatio, 6),
    snr : Fmt(Metrics.detectionSnr, 2),
    sde : Fmt(Metrics.periodSde, 2),
    pValue : PValuePercent === null ? '-' : `${Fmt(PValuePercent, 6)}%`,
    reducedChi : Fmt(Metrics.reducedChiSquared, 3),
    jdStart : FmtReference(Result.time_reference),
    medianFlux : Fmt(Result.median_flux, 6),
    noise : Fmt(Result.robust_noise, 6),
    detailResult : Result,
  };
}

//MARK: pdf characters
function PdfSafeText(Value)
{
  return String(Value ?? '-')
      .replace(/[^\x20-\x7E]/g, '?')
      .replace(/\\/g, '\\\\')
      .replace(/\(/g, '\\(')
      .replace(/\)/g, '\\)');
}

//MARK: fit pdf text
function FitPdfText(Value, MaxChars)
{
  const Text = String(Value ?? '-').replace(/\s+/g, ' ').trim();
  return Text.length > MaxChars ? `${Text.slice(0, Math.max(0, MaxChars - 1))}...` : Text;
}

//MARK: write pdf text
function PdfText(X, Y, Text, Size = 7, Font = 'F1')
{
  return `BT /${Font} ${Size} Tf ${X.toFixed(2)} ${Y.toFixed(2)} Td (${PdfSafeText(Text)}) Tj ET\n`;
}

//MARK: pdf lines
function PdfLine(X1, Y1, X2, Y2)
{
  return `${X1.toFixed(2)} ${Y1.toFixed(2)} m ${X2.toFixed(2)} ${Y2.toFixed(2)} l S\n`;
}

//MARK: pdf boxes
function PdfRect(X, Y, Width, Height)
{
  return `${X.toFixed(2)} ${Y.toFixed(2)} ${Width.toFixed(2)} ${Height.toFixed(2)} re S\n`;
}

//MARK: pack pdf
function BuildPdfBlob(PageContents, PageWidth, PageHeight)
{
  const Objects = [ null ];
  Objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
  Objects[2] = '';
  Objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>';
  Objects[4] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>';
  const PageIds = [];

  PageContents.forEach(Content =>
  {
    const ContentId = Objects.length;
    Objects.push(`<< /Length ${Content.length} >>\nstream\n${Content}endstream`);
    const PageId = Objects.length;
    PageIds.push(PageId);
    Objects.push(`<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PageWidth} ${
        PageHeight}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${ContentId} 0 R >>`);
  });

  Objects[2] =
      `<< /Type /Pages /Kids [${PageIds.map(Id => `${Id} 0 R`).join(' ')}] /Count ${PageIds.length} >>`;

  let Pdf = '%PDF-1.4\n';
  const Offsets = [ 0 ];
  for (let Index = 1; Index < Objects.length; Index++)
  {
    Offsets[Index] = Pdf.length;
    Pdf += `${Index} 0 obj\n${Objects[Index]}\nendobj\n`;
  }
  const XrefStart = Pdf.length;
  Pdf += `xref\n0 ${Objects.length}\n0000000000 65535 f \n`;
  for (let Index = 1; Index < Objects.length; Index++)
  {
    Pdf += `${String(Offsets[Index]).padStart(10, '0')} 00000 n \n`;
  }
  Pdf += `trailer\n<< /Size ${Objects.length} /Root 1 0 R >>\nstartxref\n${XrefStart}\n%%EOF`;
  return new Blob([ Pdf ], {type : 'application/pdf'});
}

//MARK: build report
function BuildAnalysisPdf(Rows, Title)
{
  const PageWidth = 1224;
  const PageHeight = 792;
  const Margin = 24;
  const TableWidth = AnalysisPdfColumns.reduce((Sum, Column) => Sum + Column.width, 0);
  const RowHeight = 36;
  const HeaderHeight = 30;
  const RowsPerPage = Math.max(1, Math.floor((PageHeight - 96 - HeaderHeight) / RowHeight));
  const Pages = [];
  const PageCount = Math.max(1, Math.ceil(Rows.length / RowsPerPage));

  //MARK: summary pages
  for (let PageIndex = 0; PageIndex < PageCount; PageIndex++)
  {
    const PageRows = Rows.slice(PageIndex * RowsPerPage, (PageIndex + 1) * RowsPerPage);
    let Content = '0.8 w\n';
    const TitleY = PageHeight - Margin - 12;
    Content += PdfText(Margin, TitleY, Title, 16, 'F2');
    Content += PdfText(PageWidth - Margin - 118, TitleY, `Summary ${PageIndex + 1}/${PageCount}`, 8, 'F1');
    Content += PdfText(Margin, TitleY - 16, `Generated ${new Date().toLocaleString()}`, 8, 'F1');

    let Y = PageHeight - Margin - 54;
    let X = Margin;
    Content += PdfRect(Margin, Y - HeaderHeight + 4, TableWidth, HeaderHeight);
    AnalysisPdfColumns.forEach(Column =>
    {
      Content += PdfLine(X, Y + 4, X, Y - HeaderHeight + 4);
      Content += PdfText(X + 3, Y - 11, Column.label, 9, 'F2');
      X += Column.width;
    });
    Content += PdfLine(Margin + TableWidth, Y + 4, Margin + TableWidth, Y - HeaderHeight + 4);
    Y -= HeaderHeight;

    PageRows.forEach(Row =>
    {
      X = Margin;
      Content += PdfRect(Margin, Y - RowHeight + 4, TableWidth, RowHeight);
      AnalysisPdfColumns.forEach(Column =>
      {
        const RawValue = Row[Column.key] ?? '-';
        const MaxChars = Math.max(4, Math.floor(Column.width / 5.3));
        const Value = FitPdfText(RawValue, MaxChars);
        const TextWidth = Value.length * 4.8;
        const TextX = Column.align === 'right' ? Math.max(X + 3, X + Column.width - TextWidth - 4) : X + 3;
        Content += PdfLine(X, Y + 4, X, Y - RowHeight + 4);
        Content += PdfText(TextX, Y - 13, Value, 10, 'F1');
        X += Column.width;
      });
      Content += PdfLine(Margin + TableWidth, Y + 4, Margin + TableWidth, Y - RowHeight + 4);
      Y -= RowHeight;
    });

    Pages.push(Content);
  }

  //MARK: curve detail pages
  for (const Row of Rows)
  {
    const Lines = PdfAnalysisDetails(Row);
    for (let Offset = 0; Offset < Lines.length; Offset += 43)
    {
      let Content = PdfText(Margin, PageHeight - Margin - 12, 'Transit Finder: ' + Row.file, 16, 'F2');
      Content += PdfLine(Margin, PageHeight - Margin - 25, PageWidth - Margin, PageHeight - Margin - 25);
      Lines.slice(Offset, Offset + 43).forEach((Line, Index) =>
      {
        Content += PdfText(Margin, PageHeight - Margin - 48 - Index * 15, Line.text, Line.heading ? 12 : 11,
                           Line.heading ? 'F2' : 'F1');
      });
      Content +=
          PdfText(Margin, 20,
                  `Analysis details ${Math.floor(Offset / 43) + 1}/${Math.ceil(Lines.length / 43)}`, 9, 'F1');
      Pages.push(Content);
    }
  }

  return BuildPdfBlob(Pages, PageWidth, PageHeight);
}

//MARK: readable pdf values
function PdfPlainText(Value)
{
  return String(Value ?? '-')
      .replace(/±/g, '+/-')
      .replace(/[–—]/g, '-')
      .replace(/σ/g, 'sigma')
      .replace(/☉/g, 'sun')
      .replace(/[^\x20-\x7E]/g, ' ');
}

//MARK: wrap pdf lines
function PdfWrap(Value, MaxLength = 160)
{
  const Words = PdfPlainText(Value).replace(/\s+/g, ' ').trim().split(' '), Lines = [];
  let Line = '';
  for (const Word of Words)
  {
    if (Line.length + Word.length + 1 > MaxLength)
    {
      Lines.push(Line);
      Line = '';
    }
    if (Word.length > MaxLength)
    {
      if (Line)
      {
        Lines.push(Line);
        Line = '';
      }
      for (let I = 0; I < Word.length; I += MaxLength)
        Lines.push(Word.slice(I, I + MaxLength));
    }
    else
      Line += (Line ? ' ' : '') + Word;
  }
  if (Line)
    Lines.push(Line);
  return Lines;
}

//MARK: pdf settings
function PdfSettingPairs(DataObject, Prefix = '')
{
  const Pairs = [];
  for (const [Key, Value] of Object.entries(DataObject || {}))
  {
    const Label = (Prefix ? Prefix + ' / ' : '') +
                  Key.replaceAll('_', ' ').replace(/([a-z])([A-Z])/g, '$1 $2').toLowerCase();
    if (Value && typeof Value === 'object' && !Array.isArray(Value))
      Pairs.push(...PdfSettingPairs(Value, Label));
    else
      Pairs.push(`${Label}: ${
          Value === null         ? 'not specified'
          : Array.isArray(Value) ? JSON.stringify(Value)
                                 : Value}`);
  }
  return Pairs;
}

//MARK: report details
function PdfAnalysisDetails(Row)
{
  const Result = Row.detailResult;
  if (!Result)
    return [];
  const Lines = [];
  const Add = (Text, Heading = false) =>
      PdfWrap(Text).forEach(Text => Lines.push({text : Text, heading : Heading}));
  const Section = Name =>
  {
    if (Lines.length)
      Lines.push({text : '', heading : false});
    Add(Name, true);
  };
  const Packed = Pairs =>
  {
    let Text = '';
    for (const Pair of Pairs)
    {
      if (Text.length + Pair.length + 3 > 150)
      {
        Add(Text);
        Text = '';
      }
      Text += (Text ? ';  ' : '') + Pair;
    }
    if (Text)
      Add(Text);
  };
  Section('RESULT AND EVIDENCE');
  Add(`Assessment: ${Row.assessment}. Candidate score: ${Row.score}/100 (not a probability).`);
  Add(`Supported events: ${Row.supported}; covered windows: ${Row.transits}; all predicted windows: ${
      Result.predicted_windows?.length ?? 'not recorded'}. Measured timing agreement: ${Row.ephemerisFit}.`);
  Add(`Period: ${Fmt(Result.period, 9)} +/- ${Fmt(Result.period_uncertainty, 9)} days (${
      Result.period_method || 'unknown method'}). SDE: ${Row.sde}; search SNR: ${Row.snr}.`);
  Add(`Duration: ${Row.duration}. Source: ${Result.tls?.duration_source || 'not recorded'}. Fit quality: ${
      Result.fit_quality?.label || 'legacy / unverified'}.`);
  Add(`Local measured depth: ${Row.depthPercent} (${Row.depthPpm} ppm). Model depth: ${
      FmtDepthPercent(Result.tls?.depth_fraction)}. These are different estimators.`);
  Add(`Local Rp/Rstar: ${Row.radiusRatio}; median flux: ${Row.medianFlux}; robust noise: ${Row.noise}.`);
  Add(`Approximate model-vs-flat p-value: ${Row.pValue}; reduced chi-square: ${
      Row.reducedChi}. This p-value is not a search-wide false-alarm probability.`);
  const Assessment = Result.planet_assessment || {};
  if (Assessment.summary)
    Add(Assessment.summary);
  if (Assessment.recommendation)
    Add(Assessment.recommendation);
  if (Result.multi_signal_search?.joint_fit)
    Packed(PdfSettingPairs(Result.multi_signal_search.joint_fit, 'Joint fit'));
  Section('ANALYSIS PROVENANCE');
  const Provenance = Result.provenance || {};
  Add(`Analyzed: ${
      Result.analyzed_at || Provenance.analyzed_at ||
      'unknown (legacy analysis)'}. Analysis version: ${Provenance.analysis_version || 'unknown'}; app: ${
      Provenance.app_version || 'unknown'}; result schema: ${
      Result.result_schema_version ?? Provenance.result_schema_version ?? 'legacy'}.`);
  const Dependencies = Object.entries(Provenance.dependency_versions || {})
                           .map(([ Key, Value ]) => `${Key} ${Value}`)
                           .join('; ');
  if (Dependencies)
    Add('Software: ' + Dependencies);
  Section('INPUT AND CLEANING');
  if (Result.exposure_metadata)
    Packed(PdfSettingPairs(Result.exposure_metadata, 'Exposure'));
  Add(`Time reference: ${FmtReference(Result.time_reference)} days. Format: ${
      Result.input_metadata?.time_format || 'unknown'}; scale: ${
      Result.input_metadata?.time_scale || 'unknown'}; flux unit: ${Result.flux_unit || 'not specified'}.`);
  Packed(PdfSettingPairs(Result.input_metadata || {}));
  const Cleaning = Result.cleaning || Result.cleaning_report;
  if (Cleaning)
    Packed(PdfSettingPairs(Cleaning));
  else
    Add('Cleaning counts were not recorded in this legacy result.');
  Add(`Normalization: ${Result.normalization?.method || 'unknown'}. Segments: ${
      Result.normalization?.segment_count ?? 'not recorded'}.`);
  Section('EFFECTIVE SEARCH SETTINGS');
  Packed(PdfSettingPairs(Result.effective_settings || Provenance.effective_settings ||
                         Result.detection_options || {}));
  if (!(Result.effective_settings || Provenance.effective_settings))
    Add('Legacy controls are recorded above; exact engine defaults and dependency versions may be unknown.');
  Section('WARNINGS');
  if (!Result.warnings?.length)
    Add('No saved major warnings. This does not establish that the signal is planetary.');
  for (const Warning of Result.warnings || [])
    Add(`${Warning.severity}: ${Warning.title}. ${Warning.detail}`);
  return Lines;
}

//MARK: completed curves
function SuccessfulBatchItems()
{
  return FileResults.filter(Item => Item.result);
}

//MARK: export curve pdf
function ExportAnalysisPdf()
{
  if (!CurrResult)
    return;
  const FileName = CurrFile ? CurrFile.name : CurrResult.source_file;
  const Rows = [ AnalysisPdfRow(FileName, CurrResult) ];
  const Pdf = BuildAnalysisPdf(Rows, 'Transit Finder Analysis');
  DownloadBlob(Pdf, `${ExportBaseName()}-analysis.pdf`, 'application/pdf');
  SetStatus('Analysis PDF exported.');
}

//MARK: export batch pdf
function ExportBatchAnalysisPdf()
{
  const Items = SuccessfulBatchItems();
  if (!Items.length)
    return;
  const Rows = Items.map(Item => AnalysisPdfRow(Item.file.name, Item.result));
  const Pdf = BuildAnalysisPdf(Rows, 'Transit Finder Batch Analysis');
  DownloadBlob(Pdf, `${ExportBaseName()}-batch-analysis.pdf`, 'application/pdf');
  SetStatus(`Batch analysis PDF exported for ${Rows.length} file${Rows.length === 1 ? '' : 's'}.`);
}

//MARK: export json
function ExportSummaryJson()
{
  if (!CurrResult)
    return;
  DownloadBlob(JSON.stringify(SummaryForExport(), null, 2), `${ExportBaseName()}-summary.json`,
               'application/json;charset=utf-8');
  SetStatus('Summary JSON exported.');
}

//MARK: export plot image
function ExportGraphPng()
{
  if (!CurrResult)
    return;
  DrawFlux();
  FluxChart.toBlob(DownloadData =>
  {
    if (!DownloadData)
    {
      SetStatus('Graph PNG export failed.', true);
      return;
    }
    DownloadBlob(DownloadData, `${ExportBaseName()}-${CurrView}-graph.png`, 'image/png');
    SetStatus('Graph PNG exported.');
  }, 'image/png');
}

ExportCsvButton.addEventListener('click', ExportTransitCsv);
ExportPngButton.addEventListener('click', ExportGraphPng);
ExportJsonButton.addEventListener('click', ExportSummaryJson);
ExportAnalysisPdfButton.addEventListener('click', ExportAnalysisPdf);
ExportBatchPdfButton.addEventListener('click', ExportBatchAnalysisPdf);

//MARK: plot dimensions
function ResizeCanvas()
{
  const Rect = FluxChart.getBoundingClientRect();
  const Ratio = window.devicePixelRatio || 1;
  FluxChart.width = Math.max(1, Math.floor(Rect.width * Ratio));
  FluxChart.height = Math.max(1, Math.floor(Rect.height * Ratio));
  FluxPen.setTransform(Ratio, 0, 0, Ratio, 0, 0);
}

//MARK: plot geometry
function GetChartGeometry()
{
  const Width = FluxChart.clientWidth;
  const Height = FluxChart.clientHeight;
  const Pad = {...ChartPad, bottom : [ 'phase', 'stack' ].includes(CurrView) ? 112 : ChartPad.bottom};
  return {
    width : Width,
    height : Height,
    pad : Pad,
    innerW : Math.max(1, Width - Pad.left - Pad.right),
    innerH : Math.max(1, Height - Pad.top - Pad.bottom),
  };
}

//MARK: default plot bounds
function GetInitialDomain()
{
  if (!CurrResult)
    return null;
  if (CurrView === 'comparison')
    return ComparisonDomain();
  if (CurrView === 'stack')
  {
    if (!HasTransitStack())
      return null;
    const StackDomain = CurrResult.transit_stack.domain;
    return {
      xMin : StackDomain.time_min,
      xMax : StackDomain.time_max,
      yMin : StackDomain.flux_min,
      yMax : StackDomain.flux_max,
    };
  }
  if (CurrView === 'phase')
  {
    if (!HasPhaseFold())
      return null;
    const PhaseDomain = PhaseDomainForScope();
    return {
      xMin : PhaseDomain.time_min,
      xMax : PhaseDomain.time_max,
      yMin : PhaseDomain.flux_min,
      yMax : PhaseDomain.flux_max,
    };
  }
  if (CurrView === 'periodogram')
  {
    return DomainForPeriodogram();
  }
  const ZoomReady = CurrView === 'zoom' && CurrResult.zoom_domain;
  const YDomain = ZoomReady ? CurrResult.zoom_domain
                            : (CurrView === 'raw' ? CurrResult.raw_domain : CurrResult.clean_domain);
  return {
    xMin : ZoomReady ? CurrResult.zoom_domain.time_min : CurrResult.domain.time_min,
    xMax : ZoomReady ? CurrResult.zoom_domain.time_max : CurrResult.domain.time_max,
    yMin : YDomain.flux_min,
    yMax : YDomain.flux_max,
  };
}

//MARK: phase bounds
function PhaseDomainForScope()
{
  const Folded = CurrResult.phase_folded;
  if (PhaseScopeInput.value === 'orbit')
    return Folded.domain;
  const Saved = Folded.focus_domain || Folded.domain;
  const Duration = NullableNumber(Folded.duration ?? CurrResult.period_duration);
  if (Duration === null || Duration <= 0)
    return Saved;
  const HalfWidth = Math.min((Folded.domain.time_max - Folded.domain.time_min) / 2, Duration * 1.5);
  return {
    ...Saved,
    time_min : Math.max(Saved.time_min, -HalfWidth),
    time_max : Math.min(Saved.time_max, HalfWidth)
  };
}

//MARK: plot limits
function GetLimitDomain()
{
  if (!CurrResult)
    return null;
  if (CurrView === 'comparison')
    return ComparisonDomain();
  if (CurrView === 'stack')
  {
    if (!HasTransitStack())
      return null;
    const StackDomain = CurrResult.transit_stack.domain;
    return {
      xMin : StackDomain.time_min,
      xMax : StackDomain.time_max,
      yMin : StackDomain.flux_min,
      yMax : StackDomain.flux_max,
    };
  }
  if (CurrView === 'phase')
  {
    if (!HasPhaseFold())
      return null;
    const PhaseDomain = CurrResult.phase_folded.domain;
    return {
      xMin : PhaseDomain.time_min,
      xMax : PhaseDomain.time_max,
      yMin : PhaseDomain.flux_min,
      yMax : PhaseDomain.flux_max,
    };
  }
  if (CurrView === 'periodogram')
  {
    return DomainForPeriodogram();
  }
  const YDomain = CurrView === 'raw' ? CurrResult.raw_domain : CurrResult.clean_domain;
  return {
    xMin : CurrResult.domain.time_min,
    xMax : CurrResult.domain.time_max,
    yMin : YDomain.flux_min,
    yMax : YDomain.flux_max,
  };
}

//MARK: copy plot bounds
function CloneDomain(Domain)
{
  return {xMin : Domain.xMin, xMax : Domain.xMax, yMin : Domain.yMin, yMax : Domain.yMax};
}

//MARK: clamp a range
function ClampRange(Min, Max, LimitMin, LimitMax)
{
  const LimitSpan = Math.max(1e-12, LimitMax - LimitMin);
  let Span = Math.max(1e-12, Max - Min);
  const MinSpan = LimitSpan * 0.0005;
  if (Span < MinSpan)
  {
    const Center = (Min + Max) / 2;
    Span = MinSpan;
    Min = Center - Span / 2;
    Max = Center + Span / 2;
  }
  if (Span >= LimitSpan)
    return [ LimitMin, LimitMax ];
  if (Min < LimitMin)
  {
    Max += LimitMin - Min;
    Min = LimitMin;
  }
  if (Max > LimitMax)
  {
    Min -= Max - LimitMax;
    Max = LimitMax;
  }
  return [ Min, Max ];
}

//MARK: clamp plot bounds
function ClampViewport(Viewport)
{
  const Limit = GetLimitDomain();
  if (!Limit)
    return Viewport;
  const [XMin, XMax] = ClampRange(Viewport.xMin, Viewport.xMax, Limit.xMin, Limit.xMax);
  const [YMin, YMax] = ClampRange(Viewport.yMin, Viewport.yMax, Limit.yMin, Limit.yMax);
  return {xMin : XMin, xMax : XMax, yMin : YMin, yMax : YMax};
}

//MARK: current plot bounds
function GetViewport()
{
  if (!CurrViewport)
  {
    const Initial = GetInitialDomain();
    if (!Initial)
      return null;
    CurrViewport = ClampViewport(CloneDomain(Initial));
  }
  return CurrViewport;
}

//MARK: mouse position
function PointerPosition(UiEvent)
{
  const Rect = FluxChart.getBoundingClientRect();
  return {
    x : UiEvent.clientX - Rect.left,
    y : UiEvent.clientY - Rect.top,
  };
}

//MARK: mouse plot limits
function ClampPointerToPlot(Point)
{
  const Geo = GetChartGeometry();
  return {
    x : Math.min(Geo.width - Geo.pad.right, Math.max(Geo.pad.left, Point.x)),
    y : Math.min(Geo.height - Geo.pad.bottom, Math.max(Geo.pad.top, Point.y)),
  };
}

//MARK: mouse data point
function DataAtCanvasPoint(Point, Viewport)
{
  const Geo = GetChartGeometry();
  const Clamped = ClampPointerToPlot(Point);
  const XRatio = (Clamped.x - Geo.pad.left) / Geo.innerW;
  const YRatio = (Clamped.y - Geo.pad.top) / Geo.innerH;
  return {
    x : Viewport.xMin + XRatio * (Viewport.xMax - Viewport.xMin),
    y : Viewport.yMax - YRatio * (Viewport.yMax - Viewport.yMin),
  };
}

//MARK: mouse zoom
function ZoomAtPointer(Scale, Axis = 'both')
{
  const Viewport = GetViewport();
  if (!Viewport)
    return;
  const Geo = GetChartGeometry();
  const Point = HoverThingy || {
    x : Geo.pad.left + Geo.innerW / 2,
    y : Geo.pad.top + Geo.innerH / 2,
  };
  const Anchor = DataAtCanvasPoint(Point, Viewport);
  CurrViewport = ClampViewport({
    xMin : Axis === 'y' ? Viewport.xMin : Anchor.x - (Anchor.x - Viewport.xMin) * Scale,
    xMax : Axis === 'y' ? Viewport.xMax : Anchor.x + (Viewport.xMax - Anchor.x) * Scale,
    yMin : Axis === 'x' ? Viewport.yMin : Anchor.y - (Anchor.y - Viewport.yMin) * Scale,
    yMax : Axis === 'x' ? Viewport.yMax : Anchor.y + (Viewport.yMax - Anchor.y) * Scale,
  });
  DrawFlux();
}

//MARK: box height
function TransitFluxRange(Transit, Flux)
{
  // use the displayed curve for the box height; raw spikes should not stretch it.
  const Variant = CurrView === 'raw' ? 'raw' : 'clean';
  const Extent = Transit.display_extents?.[Variant] || Transit[`${Variant}_extent`];
  if (Extent && IsFiniteNumber(Extent.low ?? Extent.flux_min) &&
      IsFiniteNumber(Extent.high ?? Extent.flux_max))
    return {low : Extent.low ?? Extent.flux_min, high : Extent.high ?? Extent.flux_max};
  const Values = [];
  for (let I = LowerBoundTime(CurrResult.plot.time, Transit.start); I < CurrResult.plot.time.length; I++)
  {
    const Time = CurrResult.plot.time[I];
    if (Time > Transit.end)
      break;
    const Value = Flux[I];
    if (!Number.isFinite(Value))
      continue;
    Values.push(Value);
  }
  if (!Values.length)
    return null;
  Values.sort((A, B) => A - B);
  const Low = Values[Math.floor((Values.length - 1) * .05)];
  const High = Values[Math.ceil((Values.length - 1) * .95)];
  const Padding = Math.max((High - Low) * 0.22, Math.abs(Transit.depth || 0) * 0.08, 1e-9);
  return {low : Low - Padding, high : High + Padding};
}

//MARK: first visible point
function LowerBoundTime(Times, Target)
{
  let Left = 0, Right = Times.length;
  while (Left < Right)
  {
    const Middle = (Left + Right) >> 1;
    if (Times[Middle] < Target)
      Left = Middle + 1;
    else
      Right = Middle;
  }
  return Left;
}

//MARK: mouse cursor
function UpdateCanvasCursor(Point = HoverThingy)
{
  if (DragState)
  {
    FluxChart.style.cursor = 'grabbing';
    return;
  }
  FluxChart.style.cursor = 'grab';
}

//MARK: plot notice
function DrawNotice(Message, Width, Height)
{
  FluxPen.fillStyle = '#fbfcfd';
  FluxPen.fillRect(0, 0, Width, Height);
  FluxPen.fillStyle = '#60656f';
  FluxPen.font = '700 14px system-ui, sans-serif';
  FluxPen.textAlign = 'center';
  FluxPen.textBaseline = 'middle';
  FluxPen.fillText(Message, Width / 2, Height / 2);
}

//MARK: plot axes
function DrawChartAxes(Geo, Viewport, Options = {})
{
  FluxPen.save();
  const {width : Width, height : Height, pad : Pad, innerW : InnerW, innerH : InnerH} = Geo;
  const {
    xDigits : XDigits = 4,
    yDigits : YDigits = 4,
    xLabel : XLabel = '',
    yLabel : YLabel = '',
  } = Options;
  const XDivisions = Math.max(2, Math.min(6, Math.floor(InnerW / 88)));
  const YDivisions = Math.max(2, Math.min(5, Math.floor(InnerH / 52)));
  const PlotBottom = Pad.top + InnerH;

  FluxPen.strokeStyle = '#d6dde5';
  FluxPen.lineWidth = 1;
  FluxPen.fillStyle = '#5f6874';
  FluxPen.font = '12px system-ui, sans-serif';
  FluxPen.textAlign = 'right';
  FluxPen.textBaseline = 'middle';

  for (let I = 0; I <= YDivisions; I++)
  {
    const Y = Pad.top + (InnerH * I / YDivisions);
    const Value = Viewport.yMax - ((Viewport.yMax - Viewport.yMin) * I / YDivisions);
    FluxPen.beginPath();
    FluxPen.moveTo(Pad.left, Y);
    FluxPen.lineTo(Width - Pad.right, Y);
    FluxPen.stroke();
    FluxPen.fillText(Fmt(Value, YDigits), Pad.left - 9, Y);
  }

  FluxPen.textBaseline = 'top';
  for (let I = 0; I <= XDivisions; I++)
  {
    const X = Pad.left + (InnerW * I / XDivisions);
    const Value = Viewport.xMin + ((Viewport.xMax - Viewport.xMin) * I / XDivisions);
    FluxPen.beginPath();
    FluxPen.moveTo(X, PlotBottom);
    FluxPen.lineTo(X, PlotBottom + 5);
    FluxPen.stroke();
    FluxPen.textAlign = I === 0 ? 'left' : (I === XDivisions ? 'right' : 'center');
    FluxPen.fillText(Fmt(Value, XDigits), X, PlotBottom + 10);
  }

  FluxPen.fillStyle = '#202124';
  FluxPen.font = '700 12px system-ui, sans-serif';
  FluxPen.textAlign = 'left';
  FluxPen.textBaseline = 'top';
  if (YLabel)
  {
    FluxPen.fillText(YLabel, Pad.left, Math.max(8, Pad.top - 27));
  }
  FluxPen.textAlign = 'right';
  if (XLabel)
  {
    const Available = Math.max(80, Width - Pad.left - Pad.right);
    const LabelWidth = FluxPen.measureText(XLabel).width;
    if (LabelWidth > Available)
      FluxPen.font = '600 10px system-ui,sans-serif';
    FluxPen.fillText(XLabel, Width - Pad.right, Height - 23, Math.max(Available, 100));
  }
  FluxPen.restore();
}

//MARK: clip plot drawing
function ClipToChartPlot(Geo)
{
  FluxPen.beginPath();
  FluxPen.rect(Geo.pad.left, Geo.pad.top, Geo.innerW, Geo.innerH);
  FluxPen.clip();
}

//MARK: nearest period point
function NearestPeriodogramPoint(Points, Period)
{
  const Target = Number(Period);
  if (!Number.isFinite(Target) || Target <= 0)
    return null;
  let Nearest = null;
  let NearestDistance = Infinity;
  Points.forEach(Point =>
  {
    const Distance = Math.abs(Point.period - Target);
    if (Distance < NearestDistance)
    {
      NearestDistance = Distance;
      Nearest = Point;
    }
  });
  return Nearest;
}

//MARK: period legend
function DrawPeriodogramLegend(Geo, Series)
{
  const {width : Width, pad : Pad} = Geo;
  const SelectedPeriod = Number(CurrResult.period);
  const Items = [
    {color : '#063f3b', text : Series.yLabel},
    {
      color : '#202124',
      text : Number.isFinite(SelectedPeriod) ? `Selected ${Fmt(SelectedPeriod, 4)} d` : 'Selected period'
    },
    {color : '#b45309', text : 'Top candidates'},
  ];
  FluxPen.save();
  FluxPen.font = '700 11px system-ui, sans-serif';
  FluxPen.textBaseline = 'middle';
  FluxPen.textAlign = 'left';
  const ItemWidths = Items.map(Item => 18 + FluxPen.measureText(Item.text).width + 10);
  const LegendWidth =
      Math.min(Width - Pad.left - Pad.right, ItemWidths.reduce((Sum, Value) => Sum + Value, 0) + 12);
  const XStart = Math.max(Pad.left + 8, Width - Pad.right - LegendWidth - 6);
  let X = XStart + 8;
  const Y = Pad.top + 15;
  FluxPen.fillStyle = 'rgba(251, 252, 253, 0.9)';
  FluxPen.strokeStyle = 'rgba(215, 220, 227, 0.95)';
  FluxPen.lineWidth = 1;
  FluxPen.fillRect(XStart, Pad.top + 4, LegendWidth, 22);
  FluxPen.strokeRect(XStart, Pad.top + 4, LegendWidth, 22);
  Items.forEach(Item =>
  {
    const WidthNeeded = 18 + FluxPen.measureText(Item.text).width + 10;
    if (X + WidthNeeded > XStart + LegendWidth)
      return;
    FluxPen.fillStyle = Item.color;
    FluxPen.fillRect(X, Y - 4, 9, 8);
    FluxPen.fillStyle = '#3f4650';
    FluxPen.fillText(Item.text, X + 14, Y);
    X += WidthNeeded;
  });
  FluxPen.restore();
}

//MARK: period marker
function DrawPeriodogramMarker(Geo, Viewport, XScale, Period, Color, Label, Offset = 0, Dashed = false)
{
  const PeriodValue = Number(Period);
  if (!Number.isFinite(PeriodValue) || PeriodValue <= 0 || PeriodValue < Viewport.xMin ||
      PeriodValue > Viewport.xMax)
    return;
  const {pad : Pad, innerH : InnerH} = Geo;
  const X = XScale(PeriodValue);
  FluxPen.save();
  FluxPen.strokeStyle = Color;
  FluxPen.lineWidth = 1.5;
  if (Dashed)
    FluxPen.setLineDash([ 5, 5 ]);
  FluxPen.beginPath();
  FluxPen.moveTo(X, Pad.top);
  FluxPen.lineTo(X, Pad.top + InnerH);
  FluxPen.stroke();
  FluxPen.setLineDash([]);
  if (Label)
  {
    FluxPen.fillStyle = Color;
    FluxPen.font = '700 11px system-ui, sans-serif';
    FluxPen.textBaseline = 'top';
    const LabelWidth = FluxPen.measureText(Label).width;
    const PlotLeft = Pad.left + 4;
    const PlotRight = Geo.width - Pad.right - 4;
    const FitsRight = X + 6 + LabelWidth <= PlotRight;
    FluxPen.textAlign = FitsRight ? 'left' : 'right';
    const LabelX = FitsRight ? Math.max(PlotLeft, X + 6) : Math.min(PlotRight, X - 6);
    const LabelY = Pad.top + 34 + Offset;
    FluxPen.fillStyle = 'rgba(251, 252, 253, 0.9)';
    FluxPen.fillRect(FitsRight ? LabelX - 2 : LabelX - LabelWidth - 2, LabelY - 1, LabelWidth + 4, 14);
    FluxPen.fillStyle = Color;
    FluxPen.fillText(Label, LabelX, LabelY);
  }
  FluxPen.restore();
}

//MARK: period plot
function DrawPeriodogramChart(Geo)
{
  const Width = Geo.width;
  const Height = Geo.height;
  const Pad = Geo.pad;
  const InnerW = Geo.innerW;
  const InnerH = Geo.innerH;
  const Series = PeriodogramSeries();
  if (!Series)
  {
    DrawNotice('Periodogram data is not available for this run.', Width, Height);
    return;
  }

  const Viewport = GetViewport();
  if (!Viewport)
  {
    DrawNotice('Periodogram data is not available for this run.', Width, Height);
    return;
  }

  const XMin = Viewport.xMin;
  const XMax = Viewport.xMax;
  const YMin = Viewport.yMin;
  const YMax = Viewport.yMax;
  const XScale = Value => Pad.left + ((Value - XMin) / (XMax - XMin || 1)) * InnerW;
  const YScale = Value => Pad.top + (1 - ((Value - YMin) / (YMax - YMin || 1))) * InnerH;

  FluxPen.fillStyle = '#fbfcfd';
  FluxPen.fillRect(0, 0, Width, Height);

  DrawChartAxes(Geo, Viewport, {
    xDigits : 4,
    yDigits : 3,
    xLabel : 'Period days',
    yLabel : Series.yLabel,
  });

  if (YMin < 0 && YMax > 0)
  {
    const ZeroY = YScale(0);
    FluxPen.strokeStyle = 'rgba(95, 104, 116, 0.45)';
    FluxPen.lineWidth = 1.2;
    FluxPen.beginPath();
    FluxPen.moveTo(Pad.left, ZeroY);
    FluxPen.lineTo(Width - Pad.right, ZeroY);
    FluxPen.stroke();
  }

  FluxPen.save();
  FluxPen.beginPath();
  FluxPen.rect(Pad.left, Pad.top, InnerW, InnerH);
  FluxPen.clip();

  FluxPen.strokeStyle = '#063f3b';
  FluxPen.lineWidth = 2.2;
  FluxPen.beginPath();
  let HasLinePoint = false;
  Series.points.forEach(Point =>
  {
    if (Point.period < XMin || Point.period > XMax)
      return;
    const X = XScale(Point.period);
    const Y = YScale(Point.value);
    if (!HasLinePoint)
    {
      FluxPen.moveTo(X, Y);
      HasLinePoint = true;
    }
    else
    {
      FluxPen.lineTo(X, Y);
    }
  });
  if (HasLinePoint)
    FluxPen.stroke();

  FluxPen.fillStyle = 'rgba(15, 118, 110, 0.26)';
  const PointSize = Series.points.length > 1800 ? 1.2 : 1.8;
  Series.points.forEach(Point =>
  {
    if (Point.period < XMin || Point.period > XMax || Point.value < YMin || Point.value > YMax)
      return;
    FluxPen.fillRect(XScale(Point.period) - PointSize / 2, YScale(Point.value) - PointSize / 2, PointSize,
                     PointSize);
  });

  const SelectedPeriod = Number(CurrResult.period);
  const Candidates =
      (CurrResult.period_candidates || [])
          .map(Candidate => Number(Candidate.period))
          .filter(Period => Number.isFinite(Period) && Period > 0)
          .filter(Period =>
                      (!Number.isFinite(SelectedPeriod) ||
                       Math.abs(Period - SelectedPeriod) / Math.max(Period, SelectedPeriod, 1e-9) >= 0.001))
          .filter((Period, Index, Periods) =>
                      Periods.findIndex(Other => Math.abs(Other - Period) / Math.max(Period, 1e-9) <
                                                 0.001) === Index)
          .slice(0, 6);
  Candidates.forEach((Period, Index) =>
  {
    const Nearest = NearestPeriodogramPoint(Series.points, Period);
    if (!Nearest || Nearest.period < XMin || Nearest.period > XMax || Nearest.value < YMin ||
        Nearest.value > YMax)
      return;
    const X = XScale(Nearest.period);
    const Y = YScale(Nearest.value);
    FluxPen.fillStyle = Index === 0 ? '#0f766e' : '#b45309';
    FluxPen.strokeStyle = '#fbfcfd';
    FluxPen.lineWidth = 1.5;
    FluxPen.beginPath();
    FluxPen.arc(X, Y, Index === 0 ? 4.5 : 3.5, 0, Math.PI * 2);
    FluxPen.fill();
    FluxPen.stroke();
  });
  FluxPen.restore();

  Candidates.forEach((Period, Index) =>
  {
    DrawPeriodogramMarker(Geo, Viewport, XScale, Period, Index === 0 ? '#0f766e' : '#b45309',
                          Index < 3 ? `${Fmt(Period, 4)} d` : '', (Index + 1) * 15, true);
  });
  DrawPeriodogramMarker(Geo, Viewport, XScale, SelectedPeriod, '#202124',
                        Number.isFinite(SelectedPeriod) ? `Selected ${Fmt(SelectedPeriod, 4)} d` : 'Selected',
                        0, false);
  DrawPeriodogramLegend(Geo, Series);

  UpdateCanvasCursor(HoverThingy);
}

//MARK: mouse controls
FluxChart.addEventListener('pointermove', UiEvent =>
{
  HoverThingy = PointerPosition(UiEvent);
  if (!DragState || !CurrResult)
  {
    UpdateCanvasCursor(HoverThingy);
    return;
  }
  const Geo = GetChartGeometry();
  const Dx = HoverThingy.x - DragState.x;
  const Dy = HoverThingy.y - DragState.y;
  const XSpan = DragState.viewport.xMax - DragState.viewport.xMin;
  const YSpan = DragState.viewport.yMax - DragState.viewport.yMin;
  const XShift = -Dx / Geo.innerW * XSpan;
  const YShift = Dy / Geo.innerH * YSpan;
  CurrViewport = ClampViewport({
    xMin : DragState.viewport.xMin + XShift,
    xMax : DragState.viewport.xMax + XShift,
    yMin : DragState.viewport.yMin + YShift,
    yMax : DragState.viewport.yMax + YShift,
  });
  DrawFlux();
  UpdateCanvasCursor(HoverThingy);
});

//MARK: start drag
FluxChart.addEventListener('pointerdown', UiEvent =>
{
  if (!CurrResult || UiEvent.button !== 0)
    return;
  FluxChart.focus({preventScroll : true});
  UiEvent.preventDefault();
  const Point = PointerPosition(UiEvent);
  HoverThingy = Point;
  const Viewport = GetViewport();
  if (!Viewport)
    return;
  DragState = {
    x : Point.x,
    y : Point.y,
    viewport : CloneDomain(Viewport),
  };
  FluxChart.classList.add("Dragging");
  FluxChart.setPointerCapture(UiEvent.pointerId);
});

//MARK: stop drag
function FinishDrag(UiEvent)
{
  if (!DragState)
    return;
  DragState = null;
  FluxChart.classList.remove("Dragging");
  UpdateCanvasCursor(HoverThingy);
  if (UiEvent && FluxChart.hasPointerCapture(UiEvent.pointerId))
  {
    FluxChart.releasePointerCapture(UiEvent.pointerId);
  }
}

//MARK: release mouse
FluxChart.addEventListener('pointerup', FinishDrag);
FluxChart.addEventListener('pointercancel', FinishDrag);
FluxChart.addEventListener('pointerleave', UiEvent =>
{
  if (!DragState)
    HoverThingy = null;
  UpdateCanvasCursor(HoverThingy);
});

//MARK: arrow controls
//  leave input fields and open pickers in charge of their own arrow keys.
document.addEventListener('keydown', UiEvent =>
{
  if (!CurrResult || UiEvent.defaultPrevented || UiEvent.target?.isContentEditable ||
      UiEvent.target?.closest?.(
          'input,select,textarea,[contenteditable]:not([contenteditable="false"]),[role=slider],[role=spinbutton],[role=listbox],[role=combobox],[role=menu],[role=tree],[role=tablist],[aria-haspopup=listbox]'))
    return;
  if (UiEvent.key === 'ArrowUp')
  {
    UiEvent.preventDefault();
    ZoomAtPointer(0.72);
  }
  else if (UiEvent.key === 'ArrowDown')
  {
    UiEvent.preventDefault();
    ZoomAtPointer(1.28);
  }
  else if (UiEvent.key === 'ArrowLeft')
  {
    UiEvent.preventDefault();
    ZoomAtPointer(1.28, 'x');
  }
  else if (UiEvent.key === 'ArrowRight')
  {
    UiEvent.preventDefault();
    ZoomAtPointer(0.72, 'x');
  }
});

//MARK: phase bins
function DrawPhaseChart(Geo)
{
  if (!HasPhaseFold())
  {
    DrawNotice('Phase folding needs a recovered orbital period.', Geo.width, Geo.height);
    return;
  }
  const Folded = CurrResult.phase_folded, Viewport = GetViewport();
  if (!Viewport)
    return;
  const X = Value => Geo.pad.left + (Value - Viewport.xMin) / (Viewport.xMax - Viewport.xMin) * Geo.innerW;
  const Y = Value =>
      Geo.pad.top + (1 - (Value - Viewport.yMin) / (Viewport.yMax - Viewport.yMin)) * Geo.innerH;
  FluxPen.fillStyle = '#fbfcfd';
  FluxPen.fillRect(0, 0, Geo.width, Geo.height);
  DrawChartAxes(Geo, Viewport, {xLabel : 'Days from fitted transit center', yLabel : 'Global folded flux'});
  FluxPen.save();
  ClipToChartPlot(Geo);
  if (IsFiniteNumber(Folded.duration))
  {
    FluxPen.fillStyle = 'rgba(180,83,9,.09)';
    FluxPen.fillRect(X(-Folded.duration / 2), Geo.pad.top, X(Folded.duration / 2) - X(-Folded.duration / 2),
                     Geo.innerH);
  }
  FluxPen.fillStyle = 'rgba(15,118,110,.18)';
  for (let I = 0; I < Folded.phase.length; I++)
  {
    const Phase = NullableNumber(Folded.phase[I]), Value = NullableNumber(Folded.raw_flux[I]);
    if (Phase === null || Value === null || Phase < Viewport.xMin || Phase > Viewport.xMax)
      continue;
    FluxPen.fillRect(X(Phase) - .8, Y(Value) - .8, 1.6, 1.6);
  }
  const Model = CurrResult.transit_model;
  if (ShowModelInput.checked && Model?.folded_phase_days?.length)
  {
    ApplyModelStyle(2.1);
    DrawSeriesPath(Model.folded_phase_days, Model.folded_flux, X, Y, Viewport);
    FluxPen.setLineDash([]);
  }
  FluxPen.strokeStyle = '#063f3b';
  FluxPen.lineWidth = 2.3;
  DrawSeriesPath(Folded.binned_phase || [], Folded.binned_flux || [], X, Y, Viewport);
  if (Array.isArray(Folded.binned_uncertainty))
  {
    FluxPen.lineWidth = 1;
    FluxPen.strokeStyle = 'rgba(6,63,59,.55)';
    Folded.binned_phase.forEach((Phase, Index) =>
    {
      const Uncertainty = NullableNumber(Folded.binned_uncertainty[Index]),
            Value = NullableNumber(Folded.binned_flux[Index]);
      if (Uncertainty === null || Value === null || Phase < Viewport.xMin || Phase > Viewport.xMax)
        return;
      FluxPen.beginPath();
      FluxPen.moveTo(X(Phase), Y(Value - Uncertainty));
      FluxPen.lineTo(X(Phase), Y(Value + Uncertainty));
      FluxPen.stroke();
    });
  }
  FluxPen.restore();
  DrawTransitStackLegend(Geo, Boolean(ShowModelInput.checked && Model?.folded_phase_days?.length), true);
  UpdateCanvasCursor(HoverThingy);
}

//MARK: stack legend
function DrawTransitStackLegend(Geo, HasModel, Phase = false)
{
  const Items = [
    {
      color : 'rgba(15,118,110,.6)',
      text : Phase ? 'Folded observations' : 'Individual event windows',
      width : 1.2
    },
    {color : '#063f3b', text : Phase ? 'Median bins' : 'All-event median', width : 3},
  ];
  if (HasModel)
    Items.push({
      color : IsTentativeModel() ? '#9c8979' : '#b45309',
      text : IsTentativeModel() ? 'Tentative fitted model' : 'Fitted model',
      width : 2,
      dash : IsTentativeModel()
    });
  FluxPen.save();
  FluxPen.textAlign = 'left';
  FluxPen.textBaseline = 'middle';
  FluxPen.globalAlpha = 1;
  FluxPen.font = '600 10px system-ui,sans-serif';
  let X = Geo.pad.left, Y = Geo.pad.top + Geo.innerH + 34;
  const Limit = Geo.width - Geo.pad.right;
  for (const Item of Items)
  {
    const ItemWidth = 24 + FluxPen.measureText(Item.text).width + 12;
    if (X + ItemWidth > Limit && X > Geo.pad.left)
    {
      X = Geo.pad.left;
      Y += 17;
    }
    FluxPen.strokeStyle = Item.color;
    FluxPen.lineWidth = Item.width;
    FluxPen.setLineDash(Item.dash ? [ 5, 4 ] : []);
    FluxPen.beginPath();
    FluxPen.moveTo(X, Y);
    FluxPen.lineTo(X + 14, Y);
    FluxPen.stroke();
    FluxPen.setLineDash([]);
    FluxPen.fillStyle = '#3f4650';
    FluxPen.fillText(Item.text, X + 20, Y);
    X += ItemWidth;
  }
  FluxPen.restore();
}

//MARK: stack view
function DrawTransitStackChart(Geo)
{
  if (!HasTransitStack())
  {
    DrawNotice('Reanalyze this file to create event-level stack data.', Geo.width, Geo.height);
    return;
  }
  const Stack = CurrResult.transit_stack, Viewport = GetViewport();
  if (!Viewport)
    return;
  const X = Value => Geo.pad.left + (Value - Viewport.xMin) / (Viewport.xMax - Viewport.xMin) * Geo.innerW;
  const Y = Value =>
      Geo.pad.top + (1 - (Value - Viewport.yMin) / (Viewport.yMax - Viewport.yMin)) * Geo.innerH;
  FluxPen.fillStyle = '#fbfcfd';
  FluxPen.fillRect(0, 0, Geo.width, Geo.height);
  DrawChartAxes(Geo, Viewport, {xLabel : 'Days from ephemeris center', yLabel : 'Locally normalized flux'});
  const Selected = StackEventInput.value === 'all' ? null : Number(StackEventInput.value);
  const Colors = [ '#0f766e', '#2563eb', '#7c3aed', '#0891b2', '#047857', '#4f46e5' ];
  FluxPen.save();
  ClipToChartPlot(Geo);
  Stack.traces.forEach((Trace, Index) =>
  {
    const UiEvent = CurrResult.transits?.[TraceEventIndex(Trace, Index)];
    const Cycle = NullableNumber(UiEvent?.cycle_number);
    if (StackGroupInput.value !== 'all' &&
        (Cycle === null || Math.abs(Cycle % 2) !== (StackGroupInput.value === 'odd' ? 1 : 0)))
      return;
    if (Selected !== null && StackIsolateInput.checked && Selected !== Index)
      return;
    const Shift = StackRecenterInput.checked && IsFiniteNumber(UiEvent?.measured_center)
                      ? UiEvent.measured_center - UiEvent.center
                      : 0;
    const Phases = (Trace.phase_days || []).map(Value => Value - Shift);
    FluxPen.strokeStyle = Colors[Index % Colors.length];
    FluxPen.globalAlpha = Selected === Index ? .95 : Selected === null ? .32 : .1;
    FluxPen.lineWidth = Selected === Index ? 2.6 : 1.1;
    DrawSeriesPath(Phases, Trace.flux || [], X, Y, Viewport);
  });
  FluxPen.globalAlpha = 1;
  const Model = CurrResult.transit_model;
  const HasModel = Boolean(ShowModelInput.checked && Model?.folded_phase_days?.length);
  if (HasModel)
  {
    ApplyModelStyle(2);
    DrawSeriesPath(Model.folded_phase_days, Model.folded_flux, X, Y, Viewport);
    FluxPen.setLineDash([]);
  }
  if (StackMedianInput.checked)
  {
    FluxPen.strokeStyle = '#063f3b';
    FluxPen.lineWidth = 2.7;
    DrawSeriesPath(Stack.median_phase_days || [], Stack.median_flux || [], X, Y, Viewport);
  }
  FluxPen.restore();
  DrawTransitStackLegend(Geo, HasModel);
  UpdateInspectorControls();
  UpdateCanvasCursor(HoverThingy);
}

//MARK: comparison bounds
function ComparisonDomain()
{
  const Comparison = ComparisonPayload();
  if (!Comparison?.time?.length)
    return null;
  const Values = [...(Comparison.search_flux || []), ...(Comparison.model_flux || []) ]
                     .map(NullableNumber)
                     .filter(Number.isFinite);
  if (!Values.length)
    return null;
  const Minimum = Values.reduce((A, B) => Math.min(A, B), Infinity),
        Maximum = Values.reduce((A, B) => Math.max(A, B), -Infinity),
        Padding = Math.max((Maximum - Minimum) * .08, 1e-6);
  return {
    xMin : Comparison.time[0],
    xMax : Comparison.time[Comparison.time.length - 1],
    yMin : Minimum - Padding,
    yMax : Maximum + Padding
  };
}

//MARK: fit comparison
function DrawComparisonChart(Geo)
{
  const Comparison = ComparisonPayload(), Viewport = GetViewport();
  if (!Comparison?.time?.length || !Viewport)
  {
    DrawNotice('Reanalyze this file to compare matched search flux and model residuals.', Geo.width,
               Geo.height);
    return;
  }
  FluxPen.fillStyle = '#fbfcfd';
  FluxPen.fillRect(0, 0, Geo.width, Geo.height);
  const Top = {...Geo, innerH : Geo.innerH * .57, height : Geo.pad.top + Geo.innerH * .57 + Geo.pad.bottom};
  const Residuals =
      (Comparison.residual_flux || []).map(NullableNumber).filter(Number.isFinite).sort((A, B) => A - B);
  const Scale = Math.max(Math.abs(Residuals[Math.floor(Residuals.length * .01)] || 0),
                         Math.abs(Residuals[Math.floor(Residuals.length * .99)] || 0), 1e-6) *
                1.15;
  const Bottom =
      {...Geo, pad : {...Geo.pad, top : Geo.pad.top + Geo.innerH * .69}, innerH : Geo.innerH * .31};
  const ResidualDomain = {...Viewport, yMin : -Scale, yMax : Scale};
  const X = Value => Geo.pad.left + (Value - Viewport.xMin) / (Viewport.xMax - Viewport.xMin) * Geo.innerW;
  const TopY = Value =>
      Top.pad.top + (1 - (Value - Viewport.yMin) / (Viewport.yMax - Viewport.yMin)) * Top.innerH;
  const BottomY = Value => Bottom.pad.top + (1 - (Value + Scale) / (2 * Scale)) * Bottom.innerH;
  DrawChartAxes(Top, Viewport, {yLabel : 'Search flux and model'});
  DrawChartAxes(Bottom, ResidualDomain, {xLabel : TimeAxisLabel(), yLabel : 'Residual flux (data − model)'});
  FluxPen.save();
  ClipToChartPlot(Top);
  FluxPen.strokeStyle = '#0f766e';
  FluxPen.lineWidth = 1;
  DrawSeriesPath(Comparison.time, Comparison.search_flux, X, TopY, Viewport, {timeSeries : true});
  if (ShowModelInput.checked)
  {
    ApplyModelStyle(1.8);
    DrawSeriesPath(Comparison.time, Comparison.model_flux, X, TopY, Viewport, {timeSeries : true});
  }
  FluxPen.restore();
  FluxPen.save();
  ClipToChartPlot(Bottom);
  FluxPen.setLineDash([]);
  FluxPen.strokeStyle = '#526173';
  FluxPen.lineWidth = 1;
  DrawSeriesPath(Comparison.time, Comparison.residual_flux, X, BottomY, ResidualDomain, {timeSeries : true});
  FluxPen.restore();
}

//MARK: comparison data
function ComparisonPayload()
{
  return SignalPickThing.value === 'combined' ? MainResult?.joint_model_comparison
                                              : CurrResult?.model_comparison;
}

//MARK: time axis text
function TimeAxisLabel()
{
  return `Days since ${FmtReference(CurrResult?.time_reference)} (${
      CurrResult?.input_metadata?.time_format || 'convention unverified'})`;
}

//MARK: timing plot
function DrawAuditPredictions(Geo, Viewport, Metrics, XScale)
{
  const Events = PredictedEphemerisEvents(Metrics);
  if (!Events.length)
    return;
  const {width : Width, pad : Pad, innerH : InnerH} = Geo;
  const XMin = Viewport.xMin;
  const XMax = Viewport.xMax;
  FluxPen.save();
  FluxPen.beginPath();
  FluxPen.rect(Pad.left, Pad.top, Geo.innerW, InnerH);
  FluxPen.clip();

  Events.forEach(UiEvent =>
  {
    if (UiEvent.end < XMin || UiEvent.start > XMax)
      return;
    const X1 = Math.max(Pad.left, XScale(UiEvent.start));
    const X2 = Math.min(Width - Pad.right, XScale(UiEvent.end));
    const CenterX = XScale(UiEvent.center);
    if (X2 > X1)
    {
      FluxPen.fillStyle = 'rgba(37, 99, 235, 0.08)';
      FluxPen.fillRect(X1, Pad.top, Math.max(1, X2 - X1), InnerH);
    }
    if (CenterX >= Pad.left && CenterX <= Width - Pad.right)
    {
      FluxPen.strokeStyle = 'rgba(37, 99, 235, 0.46)';
      FluxPen.lineWidth = 1.2;
      FluxPen.setLineDash([ 5, 5 ]);
      FluxPen.beginPath();
      FluxPen.moveTo(CenterX, Pad.top);
      FluxPen.lineTo(CenterX, Pad.top + InnerH);
      FluxPen.stroke();
      FluxPen.setLineDash([]);
    }
  });
  FluxPen.restore();
}

//MARK: timing residuals
function DrawAuditResiduals(Geo, Viewport, Metrics, XScale)
{
  if (!CurrResult || !CurrResult.transits.length)
    return;
  const {width : Width, pad : Pad, innerH : InnerH} = Geo;
  const RailY = Pad.top + InnerH - 15;
  FluxPen.save();
  FluxPen.beginPath();
  FluxPen.rect(Pad.left, Pad.top, Geo.innerW, InnerH);
  FluxPen.clip();

  CurrResult.transits.forEach(Transit =>
  {
    if (Transit.center < Viewport.xMin || Transit.center > Viewport.xMax)
      return;
    const Classification = ClassifyTransitForEphemeris(Transit, Metrics);
    if (!Number.isFinite(Classification.predictedCenter))
      return;
    const TransitX = XScale(Transit.measured_center ?? Transit.center);
    const PredictedX = XScale(Classification.predictedCenter);
    if ((TransitX < Pad.left && PredictedX < Pad.left) ||
        (TransitX > Width - Pad.right && PredictedX > Width - Pad.right))
    {
      return;
    }
    FluxPen.strokeStyle =
        Classification.status === 'matched' ? 'rgba(21, 128, 61, 0.7)' : 'rgba(180, 35, 24, 0.72)';
    FluxPen.lineWidth = Classification.status === 'matched' ? 1.4 : 2.2;
    FluxPen.setLineDash(Classification.status === 'matched' ? [] : [ 4, 4 ]);
    FluxPen.beginPath();
    FluxPen.moveTo(Math.max(Pad.left, Math.min(Width - Pad.right, PredictedX)), RailY);
    FluxPen.lineTo(Math.max(Pad.left, Math.min(Width - Pad.right, TransitX)), RailY);
    FluxPen.stroke();
    FluxPen.setLineDash([]);
    FluxPen.fillStyle = Classification.status === 'matched' ? '#15803d' : '#b42318';
    FluxPen.beginPath();
    FluxPen.arc(Math.max(Pad.left, Math.min(Width - Pad.right, TransitX)), RailY, 3.5, 0, Math.PI * 2);
    FluxPen.fill();
  });
  FluxPen.restore();
}

//MARK: timing legend
function DrawAuditLegend(Geo, Metrics)
{
  const {width : Width, pad : Pad} = Geo;
  const MatchText =
      (IsFiniteNumber(Metrics.ephemerisMatchCount) && IsFiniteNumber(Metrics.ephemerisMatchFraction))
          ? `Ephemeris fit ${Metrics.ephemerisMatchCount}/${CurrResult.transits.length}`
          : 'Ephemeris fit -';
  const Items = [
    {color : '#2563eb', text : 'Predicted'},
    {color : '#15803d', text : 'Aligned'},
    {color : '#b42318', text : 'Off-period'},
    {color : '#202124', text : MatchText},
  ];
  FluxPen.save();
  FluxPen.font = '700 11px system-ui, sans-serif';
  FluxPen.textBaseline = 'middle';
  FluxPen.textAlign = 'left';
  const ItemWidths = Items.map(Item => 18 + FluxPen.measureText(Item.text).width + 10);
  const LegendWidth =
      Math.min(Width - Pad.left - Pad.right, ItemWidths.reduce((Sum, Value) => Sum + Value, 0) + 12);
  const XStart = Math.max(Pad.left + 8, Width - Pad.right - LegendWidth - 6);
  let X = XStart + 8;
  const Y = Pad.top + 15;
  FluxPen.fillStyle = 'rgba(251, 252, 253, 0.88)';
  FluxPen.strokeStyle = 'rgba(215, 220, 227, 0.95)';
  FluxPen.lineWidth = 1;
  FluxPen.fillRect(XStart, Pad.top + 4, LegendWidth, 22);
  FluxPen.strokeRect(XStart, Pad.top + 4, LegendWidth, 22);
  Items.forEach(Item =>
  {
    const WidthNeeded = 18 + FluxPen.measureText(Item.text).width + 10;
    if (X + WidthNeeded > XStart + LegendWidth)
      return;
    FluxPen.fillStyle = Item.color;
    FluxPen.fillRect(X, Y - 4, 9, 8);
    FluxPen.fillStyle = '#3f4650';
    FluxPen.fillText(Item.text, X + 14, Y);
    X += WidthNeeded;
  });
  FluxPen.restore();
}

//MARK: reset plot
function ResetFluxView()
{
  CurrViewport = null;
  DrawFlux();
  QueueSessionSave();
}

//MARK: refresh stack
function RefreshStackView()
{
  UpdateInspectorControls();
  DrawFlux();
}

//MARK: signal changes
function PickSignal()
{
  if (SignalPickThing.value === 'combined')
  {
    CurrResult = MainResult;
    CurrView = 'comparison';
    ViewButtons.forEach(Button =>
    {
      Button.classList.toggle("Active", Button.dataset.view === CurrView);
    });
  }
  else
  {
    CurrResult = MainResult?.signals?.[Number(SignalPickThing.value)] || MainResult;
  }

  // a different signal starts with its own default plot and event selection.
  CurrViewport = null;
  StackEventInput.value = 'all';
  ShowCurveResult(CurrResult);
  QueueSessionSave();
}

//MARK: keep file settings
function ApplyFileSettings()
{
  UpdatePerFileSettings(false);
}

//MARK: clear file settings
function ClearFileSettings()
{
  UpdatePerFileSettings(true);
}

//MARK: resize plot
function ResizeFlux()
{
  UpdateSidebarWidth();
  DrawFlux();
}

//MARK: buttons
function HookUpChartControls()
{
  document.getElementById("ResetViewButton").addEventListener('click', ResetFluxView);
  ShowModelInput.addEventListener('change', DrawFlux);
  ShowLocalDipsInput.addEventListener('change', DrawFlux);
  PhaseScopeInput.addEventListener('change', ResetFluxView);

  // each stack control needs the same inspector refresh before drawing.
  const StackInputs = [
    StackEventInput,
    StackGroupInput,
    StackIsolateInput,
    StackMedianInput,
    StackRecenterInput,
  ];
  StackInputs.forEach(Input =>
  {
    Input.addEventListener('change', RefreshStackView);
  });

  SignalPickThing.addEventListener('change', PickSignal);
  PerFileSettingsInput.addEventListener('change', QueueSessionSave);
  document.getElementById("ApplyPerFileSettings").addEventListener('click', ApplyFileSettings);
  document.getElementById("ClearPerFileSettings").addEventListener('click', ClearFileSettings);
  window.addEventListener('resize', ResizeFlux);
}

//MARK: start page
HookUpChartControls();

SessionReadyPromise = OpenRun();
