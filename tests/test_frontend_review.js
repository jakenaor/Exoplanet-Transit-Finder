// a pretend page keeps these checks quick; no server or workers needed.
const Assert = require('node:assert/strict');
const Fs = require('node:fs');
const Vm = require('node:vm');
const Path = require('node:path');

//MARK: fake page
const CanvasDoodles = [];
// keep the canvas doodles so we can check gaps without opening a browser.
const FakePlotThing =
    new Proxy({
      measureText : Text => ({width : String(Text).length * 6}),
    },
              {
                get(Target, Key)
                {
                  return Key in Target ? Target[Key] : (...Args) =>
                  {
                    CanvasDoodles.push([ Key, ...Args ]);
                  };
                },
              });

//MARK: fake element
function MakeFakeThing(Id)
{
  // only the dom methods used by app.js need a stand-in here.
  return {
    id : Id,
    value : '',
    checked : true,
    hidden : false,
    disabled : false,
    innerHTML : '',
    textContent : '',
    scrollTop : 0,
    dataset : {},
    clientWidth : 900,
    clientHeight : 500,
    style : {
      setProperty()
      {
      },
      removeProperty()
      {
      },
    },
    classList : {
      add()
      {
      },
      remove()
      {
      },
      toggle()
      {
      },
    },
    listeners : {},
    addEventListener(Type, Callback)
    {
      (this.listeners[Type] ??= []).push(Callback);
    },
    setAttribute()
    {
    },
    removeAttribute()
    {
    },
    querySelector()
    {
      return null;
    },
    querySelectorAll()
    {
      return [];
    },
    getContext()
    {
      return FakePlotThing;
    },
    getBoundingClientRect()
    {
      return {width : 900, height : 500, left : 0, top : 0};
    },
    replaceChildren()
    {
    },
    append()
    {
    },
    focus()
    {
      FakePageThing.activeElement = this;
    },
    remove()
    {
    },
    contains()
    {
      return false;
    },
    setPointerCapture()
    {
    },
    hasPointerCapture()
    {
      return false;
    },
  };
}

//MARK: fake element list
const FakeBits = new Map();
const GrabThing = Id => FakeBits.get(Id) || FakeBits.set(Id, MakeFakeThing(Id)).get(Id);
const FakeViewButtons = [ 'zoom', 'clean', 'raw', 'phase', 'stack', 'periodogram', 'audit', 'comparison' ]
    .map(View =>
    {
      const Button = MakeFakeThing(`view-${View}`);
      Button.dataset.view = View;
      return Button;
    });
//MARK: starting controls
for (const [Id, Value] of Object.entries({
       StrictnessInput : '1',
       SmoothingInput : '1',
       SearchModeInput : 'tls',
       TlsMaxSignalsInput : '1',
       BatchSort : 'index',
       PhaseScope : 'focus',
       StackEvent : 'all',
       StackGroup : 'all',
     }))
{
  GrabThing(Id).value = Value;
}

//MARK: page events
const FakePageThing = {
  getElementById : GrabThing,
  querySelector : () => GrabThing('main'),
  querySelectorAll : Selector => Selector === '.ViewButton[data-view]' ? FakeViewButtons : [],
  listeners : {},
  addEventListener(Type, Fn)
  {
    (this.listeners[Type] ??= []).push(Fn);
  },
  createElement : () => MakeFakeThing('new'),
  body : MakeFakeThing('body'),
};

//MARK: load the app
//MARK: fake globals
const FakeAppThing = Vm.createContext({
  document : FakePageThing,
  console,
  Blob,
  FormData,
  URL,
  Map,
  Set,
  Date,
  Math,
  JSON,
  Number,
  Array,
  Object,
  String,
  Promise,
  window : {
    matchMedia : () => ({matches : false}),
    addEventListener()
    {
    },
    setTimeout()
    {
      return 1;
    },
    clearTimeout()
    {
    },
    setInterval()
    {
      return 1;
    },
    clearInterval()
    {
    },
    devicePixelRatio : 1,
    location : {href : 'http://localhost/'},
  },
});
//MARK: skip startup fetch
let Source = Fs.readFileSync(
    Path.join(__dirname, '../Exoplanet data parsing tool/static/app.js'),
    'utf8',
);
// skip the startup request. the checks below supply their own results.
Source = Source.replace(
    "SessionReadyPromise = OpenRun();",
    "SessionReadyPromise = Promise.resolve();",
);
//MARK: real markup still needs every control
const PageSource = Fs.readFileSync(Path.join(__dirname, '../Exoplanet data parsing tool/static/index.html'), 'utf8');
const PageIds = [...PageSource.matchAll(/\bid=["']([^"']+)["']/g)].map(Match => Match[1]);
Assert.equal(new Set(PageIds).size, PageIds.length, 'html ids must be unique');
for (const Match of Source.matchAll(/document\.getElementById\(["']([^"']+)["']\)/g))
  Assert.ok(PageIds.includes(Match[1]), 'missing html control: ' + Match[1]);

Vm.runInContext(Source, FakeAppThing);
const RunApp = Code => Vm.runInContext(Code, FakeAppThing);

//MARK: settings checks
RunApp("ResetDetectionControls()");
Assert.equal(RunApp("DetectionOptions().searchMode"), 'tls', 'reset restores TLS as the search mode');
Assert.equal(RunApp("DetectionOptions().tlsThreads"), 4, 'reset restores four CPU workers');
//MARK: restore checks
RunApp("ApplySavedDetectionOptions({searchMode:'bls',tlsThreads:2,exposureSeconds:0})");
Assert.equal(RunApp("DetectionOptions().searchMode"), 'bls', 'saved search mode is restored');
Assert.equal(RunApp("DetectionOptions().tlsThreads"), 2, 'saved worker count is restored');
Assert.equal(RunApp("DetectionOptions().exposureSeconds"), 0, 'saved instantaneous exposure stays zero');
RunApp("ResetDetectionControls()");
Assert.equal(RunApp("DetectionOptions().searchMode"), 'tls');
Assert.equal(RunApp("DetectionOptions().tlsThreads"), 4);
Assert.equal(RunApp("DetectionOptions().exposureSeconds"), null, 'reset leaves exposure unknown');

//MARK: missing values
for (const Input of ['null', 'undefined', "''", "'  '", 'true', 'false', 'NaN', 'Infinity', '{}', '[]'])
{
  Assert.equal(RunApp(`NullableNumber(${Input})`), null);
}
//MARK: zero checks
Assert.equal(RunApp("NullableNumber(0)"), 0);
Assert.equal(RunApp("NullableNumber('0')"), 0);
//MARK: verdict checks
RunApp(`
  CurrResult = {
    transits: [],
    period_sde: 1000,
    tls_fap: null,
    planet_assessment: {
      status: 'no_planet_like_signal',
      short_label: 'Saved verdict',
      candidate_score: 12,
      supporting_evidence: [],
      limiting_evidence: [],
    },
  };
`);
Assert.equal(RunApp("CurrentPlanetAssessment().candidateScore"), 12,
             'UI must retain backend verdict despite a large SDE');
Assert.equal(RunApp("CurrentPlanetAssessment().shortLabel"), 'Saved verdict');
RunApp("CurrResult={transits:[]};");
Assert.equal(RunApp("CurrentPlanetAssessment().candidateScore"), null,
             'legacy data must not be silently rescored');

//MARK: batch checks
RunApp(`
  BatchInProgress = true;
  FileResults = [
    {
      file: {name: 'complete.csv'},
      result: {
        transits: [],
        period: 2,
        planet_assessment: {status: 'strong_candidate', candidate_score: 80, short_label: 'Strong'},
      },
    },
    {file: {name: 'running.csv'}, result: null, status: 'running'},
  ];
  CurrFileIndex = 0;
  RenderBatchSelect();
`);
Assert.equal(GrabThing("ResultSelect").disabled, false, 'completed results remain navigable during batch');
Assert.equal(GrabThing("BatchPickerButton").disabled, false);
Assert.match(GrabThing("ResultSelect").innerHTML, /value="1" disabled/,
             'unfinished results cannot be selected');
Assert.match(GrabThing("BatchPickerMeta").textContent, /candidate score/);

//MARK: gap checks
RunApp(`
  CurrResult = {
    normalization: {
      segment_time_ranges: [{start_day: 0, end_day: 1}, {start_day: 10, end_day: 11}],
    },
  };
`);
CanvasDoodles.length = 0;
RunApp("DrawSeriesPath([0,1,10,11],[1,1,1,1],X=>X,Y=>Y,{xMin:0,xMax:11},{timeSeries:true});");
Assert.equal(CanvasDoodles.filter(C => C[0] === 'moveTo').length, 2, 'observation gap starts a new path');
Assert.equal(CanvasDoodles.filter(C => C[0] === 'lineTo').length, 2, 'no line bridges the gap');

//MARK: box height checks
RunApp(`
  CurrView = 'clean';
  CurrResult = {
    plot: {
      time: Array.from({length: 21}, (Unused,I) => I),
      raw_flux: Array(20).fill(1).concat([100]),
    },
  };
`);
Assert.ok(
    RunApp("TransitFluxRange({start:0,end:20,depth:.01},Array(20).fill(1).concat([100])).high") < 2,
    'one raw spike cannot stretch a cleaned-view box',
);
//MARK: stack numbering
Assert.equal(RunApp("TraceEventIndex({transit_index:1},4)"), 0,
             'stack event IDs remain one-based in payloads');
RunApp("CurrResult={transits:[]};");
Assert.equal(
    RunApp(
        "ClassifyTransitForEphemeris({source:'TLS model',center:2},{period:2,periodEpoch:0,periodDuration:.1}).status"),
    'unknown',
    'predicted centers are not timing measurements',
);

//MARK: keyboard checks
let Prevented = false;
for (const Handler of FakePageThing.listeners.keydown)
{
  Handler({
    key : 'ArrowUp',
    target : {closest : () => ({})},
    preventDefault()
    {
      Prevented = true;
    }
  });
}
Assert.equal(Prevented, false, 'chart shortcuts do not capture input arrow keys');

//MARK: plot arrows
RunApp(`
  globalThis.ZoomCalls = [];
  globalThis.SavedZoomAtPointer = ZoomAtPointer;
  ZoomAtPointer = (...Args) => ZoomCalls.push(Args);
  CurrResult = {transits: []};
`);
const OrdinaryChartButton = {
  closest : Selector => Selector.split(',').includes('button') ? {} : null,
};
for (const Key of ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'])
{
  let Handled = false;
  for (const Handler of FakePageThing.listeners.keydown)
  {
    Handler({
      key : Key,
      target : OrdinaryChartButton,
      defaultPrevented : false,
      preventDefault()
      {
        Handled = true;
      }
    });
  }
  Assert.equal(Handled, true, `${Key} still controls the graph after clicking a chart button`);
}
Assert.deepEqual(JSON.parse(RunApp("JSON.stringify(ZoomCalls)")),
                 [ [ .72 ], [ 1.28 ], [ 1.28, 'x' ], [ .72, 'x' ] ]);

//MARK: input focus
//  inputs and open pickers need their own arrow keys.
for (const Target of [{closest : () => ({})},
                      {isContentEditable : true},
                      {closest : Selector => Selector.includes('aria-haspopup') ? {} : null},
])
{
  for (const Handler of FakePageThing.listeners.keydown)
  {
    Handler({
      key : 'ArrowUp',
      target : Target,
      preventDefault()
      {
        throw Error('Control arrow key was stolen');
      },
    });
  }
}
for (const Handler of FakePageThing.listeners.keydown)
{
  Handler({
    key : 'ArrowUp',
    target : OrdinaryChartButton,
    defaultPrevented : true,
    preventDefault()
    {
      throw Error('Already handled key was stolen');
    },
  });
}
Assert.equal(RunApp("ZoomCalls.length"), 4);
//MARK: mouse focus
RunApp(`
  ZoomAtPointer = SavedZoomAtPointer;
  globalThis.SavedGetViewport = GetViewport;
  globalThis.SavedPointerPosition = PointerPosition;
  GetViewport = () => ({xMin:0,xMax:10,yMin:0,yMax:2});
  PointerPosition = () => ({x:100,y:100});
`);
for (const Handler of GrabThing("FluxChart").listeners.pointerdown)
{
  Handler({button : 0, pointerId : 3, preventDefault()
  {
  }});
}
Assert.equal(FakePageThing.activeElement, GrabThing("FluxChart"),
             'clicking the graph moves keyboard focus away from the last edited control');
// put the real functions back before the remaining checks.
RunApp(`
  GetViewport = SavedGetViewport;
  PointerPosition = SavedPointerPosition;
  DragState = null;
`);

//MARK: file settings checks
GrabThing("PerFileSettings").value = '{"a.csv":{"inventedSetting":1}}';
Assert.throws(() => RunApp("ReadPerFileSettings()"), /Unknown per-file setting/);
//MARK: view changes
//  check the real button wiring while recording the draw/save order.
RunApp(`
  globalThis.SavedUiHandlers = {DrawFlux, QueueSessionSave, ShowCurveResult, UpdateInspectorControls};
  globalThis.SavedCurveState = {
    CurrResult, MainResult, CurrView, CurrViewport,
    SignalValue: SignalPickThing.value,
    EventValue: StackEventInput.value,
  };
  globalThis.UiWorkflow = [];
  DrawFlux = () => UiWorkflow.push('draw');
  QueueSessionSave = () => UiWorkflow.push('save');
  ShowCurveResult = Result => UiWorkflow.push('show:' + Result.signal_id);
  UpdateInspectorControls = () => UiWorkflow.push('inspect');
  CurrViewport = {xMin: 1, xMax: 2, yMin: 0, yMax: 1};
`);
for (const Handler of GrabThing('ResetViewButton').listeners.click)
  Handler();
Assert.equal(RunApp("CurrViewport"), null, 'reset clears the custom chart bounds');
Assert.deepEqual(JSON.parse(RunApp("JSON.stringify(UiWorkflow)")), [ 'draw', 'save' ]);

//MARK: combined signal check
RunApp(`
  UiWorkflow.length = 0;
  MainResult = {signal_id: 'primary', signals: [{signal_id: 'first'}, {signal_id: 'second'}]};
  CurrView = 'phase';
  CurrViewport = {xMin: 1, xMax: 2, yMin: 0, yMax: 1};
  StackEventInput.value = '2';
`);
GrabThing("SignalPickThing").value = 'combined';
for (const Handler of GrabThing("SignalPickThing").listeners.change)
  Handler();
Assert.equal(RunApp("CurrResult === MainResult"), true, 'combined view uses the original observation result');
Assert.equal(RunApp("CurrView"), 'comparison');
Assert.equal(RunApp("CurrViewport"), null);
Assert.equal(GrabThing('StackEvent').value, 'all');
Assert.deepEqual(JSON.parse(RunApp("JSON.stringify(UiWorkflow)")), [ 'show:primary', 'save' ]);

//MARK: single signal check
RunApp("UiWorkflow.length = 0;");
GrabThing("SignalPickThing").value = '1';
for (const Handler of GrabThing("SignalPickThing").listeners.change)
  Handler();
Assert.equal(RunApp("CurrResult.signal_id"), 'second', 'the selected signal supplies its own result');
Assert.deepEqual(JSON.parse(RunApp("JSON.stringify(UiWorkflow)")), [ 'show:second', 'save' ]);

//MARK: stack draw order
RunApp("UiWorkflow.length = 0;");
for (const Handler of GrabThing('StackEvent').listeners.change)
  Handler();
Assert.deepEqual(JSON.parse(RunApp("JSON.stringify(UiWorkflow)")), [ 'inspect', 'draw' ]);
RunApp(`
  DrawFlux = SavedUiHandlers.DrawFlux;
  QueueSessionSave = SavedUiHandlers.QueueSessionSave;
  ShowCurveResult = SavedUiHandlers.ShowCurveResult;
  UpdateInspectorControls = SavedUiHandlers.UpdateInspectorControls;
  CurrResult = SavedCurveState.CurrResult;
  MainResult = SavedCurveState.MainResult;
  CurrView = SavedCurveState.CurrView;
  CurrViewport = SavedCurveState.CurrViewport;
  SignalPickThing.value = SavedCurveState.SignalValue;
  StackEventInput.value = SavedCurveState.EventValue;
`);
//MARK: curve file selection
RunApp(`
  BatchInProgress = false;
  RunningJobId = null;
  RequestId = null;
  JobConnectionLost = false;
  SetFiles([{name:'curve.csv'}, {name:'curve.json'}, {name:'star.FITS'}, {name:'other.fit'}, {name:'last.fts'}]);
`);
Assert.deepEqual(JSON.parse(RunApp('JSON.stringify(CurveFiles.map(File => File.name))')),
                 ['curve.csv', 'star.FITS', 'other.fit', 'last.fts']);
Assert.match(GrabThing('Status').textContent, /Skipped 1 unsupported file.*JSON metadata/);
RunApp("SetFiles([{name:'metadata.JSON'}]);");
Assert.equal(RunApp('CurveFiles.length'), 4, 'metadata alone does not replace the current light curve selection');
Assert.match(GrabThing('Status').textContent, /No CSV or FITS light curves were added/);

//MARK: short curve inspection
RunApp(`
  globalThis.InspectionFixture = {
    review_only: true, analysis_mode: 'inspection', search_status: 'not_run',
    review_reason: 'Only 22 usable samples remain; transit search requires at least 50.',
    search_requirements: {minimum_samples: 50, usable_samples: 22},
    total_points: 22, time_reference: 2461360, time_unit: 'days', flux_unit: 'counts',
    median_flux: 100, robust_noise: null, transits: [], signals: [], observed_events: [],
    predicted_windows: [], exploratory_dips: [], warnings: [], period: null,
    planet_assessment: null, fit_quality: null, diagnostics: null, periodogram: null,
    phase_folded: null, transit_stack: null, transit_model: null, model_comparison: null,
    input_metadata: {time_format: 'bjd', time_scale: 'tdb'},
    normalization: {method: 'none', segment_time_ranges: [{start_day:0, end_day:.021}]},
    domain: {time_min:0, time_max:.021},
    raw_domain: {flux_min:99.8, flux_max:100.2},
    clean_domain: {flux_min:99.8, flux_max:100.2},
    plot: {
      time: Array.from({length:22}, (Unused,Index) => Index * .001),
      raw_flux: Array.from({length:22}, (Unused,Index) => 100 + Math.sin(Index) / 10),
      smooth_flux: Array.from({length:22}, (Unused,Index) => 100 + Math.sin(Index) / 10),
      flux_uncertainty: Array.from({length:22}, (Unused,Index) => Index % 2 ? null : .04),
      exposure_seconds: Array(22).fill(null), break_indices: [],
    },
  };
  CurrResult = InspectionFixture;
  MainResult = InspectionFixture;
  CurrFile = {name:'short.csv'};
  CurrView = 'phase';
  CurrViewport = null;
  ViewBeforeInspection = null;
`);
CanvasDoodles.length = 0;
RunApp('ShowCurveResult(CurrResult);');
Assert.equal(RunApp('CurrView'), 'raw', 'short results open the measured light curve');
Assert.equal(RunApp('CurrentPlanetAssessment()'), null, 'inspection has no fallback planet verdict');
Assert.match(GrabThing('Assessment').innerHTML, /Data inspection/);
Assert.doesNotMatch(GrabThing('Assessment').innerHTML, /ScoreTrack|ScoreFill|Candidate score/);
Assert.doesNotMatch(GrabThing('Metrics').innerHTML, /Orbital period|Supported events|SDE|Radius ratio/);
Assert.match(GrabThing('SearchUnavailable').textContent, /22.*50/);
Assert.equal(GrabThing('SearchModeInput').disabled, true);
Assert.equal(GrabThing('StrictnessInput').disabled, true);
Assert.equal(GrabThing('ModelControl').hidden, true);
Assert.equal(GrabThing('ExportCsvButton').disabled, false);
Assert.equal(GrabThing('ExportCsvButton').textContent, 'Light curve CSV');
for (const Button of FakeViewButtons)
  Assert.equal(Button.disabled, Button.dataset.view !== 'raw', `${Button.dataset.view} availability follows inspection mode`);
Assert.ok(CanvasDoodles.filter(Call => Call[0] === 'arc').length >= 22, 'each retained measurement is visible');

//MARK: supplied error bars
CanvasDoodles.length = 0;
RunApp('DrawRawMeasurements([0,.001],[100,100],X=>X,Y=>Y,{xMin:0,xMax:.01});');
Assert.deepEqual(CanvasDoodles.filter(Call => Call[0] === 'lineTo').map(Call => Call.slice(1)),
                 [[0,99.96],[3,100.04],[3,99.96]], 'supplied errors stay in input flux units; missing errors are not invented');

//MARK: short curve exports
RunApp(`
  globalThis.SavedDownload = DownloadBlob;
  globalThis.InspectionDownload = null;
  DownloadBlob = (Content, Filename) => { globalThis.InspectionDownload = {Content, Filename}; };
  ExportTransitCsv();
  DownloadBlob = SavedDownload;
`);
Assert.match(RunApp('InspectionDownload.Filename'), /light-curve\.csv$/);
Assert.equal(RunApp('InspectionDownload.Content.split("\\n").length'), 23);
Assert.match(RunApp('InspectionDownload.Content'), /^Time,Flux,flux_err,exposure_seconds,/);
Assert.equal(RunApp('RawCurveRowsForExport()[0].Time'), 2461360);
Assert.equal(RunApp('SummaryForExport().planet_assessment'), null);
Assert.equal(RunApp('SummaryForExport().period'), null);
Assert.equal(RunApp('SummaryForExport().metrics'), undefined);
Assert.equal(RunApp('SummaryForExport().plot.raw_flux[0]'), 100);
Assert.equal(RunApp('SummaryForExport().plot.flux_uncertainty[0]'), .04);
RunApp('delete InspectionFixture.median_flux;');
Assert.ok(RunApp('InspectionMedian()') > 99 && RunApp('InspectionMedian()') < 101, 'the descriptive median uses retained input flux when it is not supplied');
Assert.doesNotMatch(RunApp("PdfAnalysisDetails(AnalysisPdfRow('short.csv',CurrResult)).map(Line=>Line.text).join('\\n')"),
                    /Candidate score:|Period:|Local measured depth:/);

//MARK: short curve zoom and pan
RunApp('CurrViewport = null; HoverThingy = null;');
const FullSpan = RunApp('GetViewport().xMax - GetViewport().xMin');
RunApp('ZoomAtPointer(.5);');
Assert.ok(RunApp('GetViewport().xMax - GetViewport().xMin') < FullSpan, 'raw inspection can zoom');
const BeforePan = RunApp('GetViewport().xMin');
for (const Handler of GrabThing('FluxChart').listeners.pointerdown)
  Handler({button:0, pointerId:7, clientX:450, clientY:250, preventDefault()
  {
  }});
for (const Handler of GrabThing('FluxChart').listeners.pointermove)
  Handler({pointerId:7, clientX:400, clientY:250});
for (const Handler of GrabThing('FluxChart').listeners.pointerup)
  Handler({pointerId:7});
Assert.notEqual(RunApp('GetViewport().xMin'), BeforePan, 'raw inspection can pan after zooming');

//MARK: inspection batch navigation
RunApp(`
  BatchInProgress = true;
  FileResults = [{file:{name:'short.csv'},result:InspectionFixture}, {file:{name:'running.csv'},result:null,status:'running'}];
  CurrFileIndex = 0;
  RenderBatchSelect();
`);
Assert.equal(GrabThing('ResultSelect').disabled, false);
Assert.match(GrabThing('BatchPickerMeta').textContent, /Data inspection/);
Assert.doesNotMatch(GrabThing('BatchPickerMeta').textContent, /candidate score|supported|SDE|SNR|P -/);
RunApp('CurrResult = {transits:[]}; UpdateCurveTools();');
Assert.equal(RunApp('CurrView'), 'phase', 'browsing an inspection does not lose the previous search view');
Assert.equal(GrabThing('SearchModeInput').disabled, false);
for (const Button of FakeViewButtons)
  Assert.equal(Button.disabled, false, 'normal result controls are restored');
//MARK: search mode transitions
for (const Mode of ['tls', 'bls'])
{
  GrabThing('SearchModeInput').value = Mode;
  RunApp('UpdateDetectionReadouts();');
  Assert.equal(GrabThing('TlsOptions').hidden, Mode !== 'tls');
  GrabThing('TlsThreadsInput').disabled = true;
  RunApp('CurrResult = InspectionFixture; UpdateCurveTools();');
  Assert.equal(GrabThing('SearchModeInput').disabled, true);
  Assert.equal(GrabThing('TlsOptions').hidden, Mode !== 'tls');
  RunApp('CurrResult = {transits:[]}; UpdateCurveTools();');
  Assert.equal(GrabThing('SearchModeInput').disabled, false);
  Assert.equal(GrabThing('TlsThreadsInput').disabled, true, 'inspection preserves a pre-existing disabled search control');
  Assert.equal(GrabThing('TlsOptions').hidden, Mode !== 'tls');
  GrabThing('TlsThreadsInput').disabled = false;
}
GrabThing('SearchModeInput').value = 'tls';
RunApp('UpdateDetectionReadouts();');
RunApp("CurrResult=null; MainResult=null; CurrView='zoom'; CurrViewport=null; BatchInProgress=false; UpdateCurveTools();");
console.log('Frontend review: 19 behavior groups passed (including short-curve inspection, exports, and navigation).');

//MARK: observation viewer
RunApp(`
  globalThis.ObservationFixture = {
    ...InspectionFixture, total_points:6,
    plot:{...InspectionFixture.plot, time:[0,.001,.002,2,2.001,2.002], raw_flux:[100,101,99,102,103,101], smooth_flux:[100,101,99,102,103,101]},
    domain:{time_min:0,time_max:2.002}, raw_domain:{flux_min:98,flux_max:104},
    observation_view:{
      version:1,total_points:6,time_reference:2461360,flux_unit:'counts',representation:'original input flux',
      domain:{time_min:0,time_max:2.002},raw_domain:{flux_min:98,flux_max:104},
      plot:{time:[0,.001,.002,2,2.001,2.002],display_time:[0,.001,.002,.003,.004,.005],raw_flux:[100,101,99,102,103,101],flux_uncertainty:[.1,null,.2,.3,.4,.5],exposure_seconds:[0,15,null,30,30,30],break_indices:[3]},
      display_time_map:{version:1,enabled:true,cadence_days:.001,threshold_days:30/1440,join_days:.001,gap_count:1,removed_days:1.997,
        display_domain:{time_min:0,time_max:.005},
        gaps:[{time_start:.002,time_end:2,display_start:.002,display_end:.003,removed_days:1.997}],
        knots:[{time:0,display_time:0},{time:.002,display_time:.002},{time:2,display_time:.003},{time:2.002,display_time:.005}],
        runs:[{run_id:1,points:3,plot_start:0,plot_end:3,time_start:0,time_end:.002,display_start:0,display_end:.002},{run_id:2,points:3,plot_start:3,plot_end:6,time_start:2,time_end:2.002,display_start:.003,display_end:.005}],
      },
    },
  };
  MainResult=ObservationFixture; CurrResult=MainResult; CurrView='raw'; CurrViewport=null;
  ObservationUnitsInput.value='minutes'; ShowCurveResult(CurrResult);
`);
Assert.equal(RunApp('GetViewport().xMax'), .005, 'only observation coordinates shrink');
Assert.ok(Math.abs(RunApp('ObservationRealTime(.003)') - 2) < 1e-12);
Assert.equal(RunApp('ObservationUnit().factor'), 1440);
Assert.match(GrabThing('ObservationSummary').textContent, /1 gaps cut/);
Assert.match(GrabThing('CurveTableHead').innerHTML, /Original time/);
Assert.ok(RunApp('RawCurveRowsForExport()[3].Time') === 2461362, 'CSV uses original time after the gap');
Assert.equal(RunApp('RawCurveRowsForExport()[0].exposure_seconds'), 0);
CanvasDoodles.length = 0;
RunApp("DrawChartAxes(GetChartGeometry(),GetViewport(),{xTickFormat:Value=>'tick:'+Value});");
Assert.ok(CanvasDoodles.some(Call => Call[0] === 'fillText' && String(Call[1]).startsWith('tick:')), 'axes use the requested formatter');
RunApp(`
  const Geo=GetChartGeometry(), View=GetViewport();
  UpdateObservationHover({x:Geo.pad.left+.003/.005*Geo.innerW,y:Geo.pad.top+(View.yMax-102)/(View.yMax-View.yMin)*Geo.innerH});
`);
Assert.equal(RunApp('ObservationHoverIndex'), 3);
Assert.match(GrabThing('ObservationReadout').textContent, /2461362.*flux 102/);
Assert.match(GrabThing('ObservationReadout').textContent, /30.*s/);
GrabThing('ObservationRun').value='1';
RunApp('PickObservationRun();');
Assert.ok(RunApp('GetViewport().xMin') >= .002 - 1e-12);
Assert.ok(RunApp('GetViewport().xMax') <= .005 + 1e-12);
GrabThing('ObservationUnits').value='auto';
Assert.equal(RunApp('ObservationUnit().name'), 'minutes', 'shortened gap margins do not inflate a single-run span');
GrabThing('ObservationUnits').value='minutes';
RunApp(`
  FileResults=[{file:{name:'two-nights.csv'},result:ObservationFixture}]; CurrFileIndex=0;
  globalThis.ObservationState=JSON.parse(JSON.stringify(PackRunState()));
  RestoreSessionState(ObservationState);
`);
Assert.equal(GrabThing('ObservationUnits').value, 'minutes');
Assert.equal(GrabThing('ObservationRun').value, '1');
Assert.equal(RunApp('GetViewport().xMin'), RunApp('ObservationState.current_viewport.xMin'));
RunApp(`
  MainResult={...ObservationFixture,total_points:100};
  CurrResult=MainResult; UpdateCurveTools(); CurrView='raw'; CurrViewport=null;
`);
Assert.equal(GrabThing('SearchModeInput').disabled, false, 'long view-only results permit search-setting changes');
RunApp('CurrResult.review_only=false; CurrResult.period=2;');
RunApp('DownloadBlob=(Content,Filename)=>{globalThis.ObservationDownload={Content,Filename};}; ExportTransitCsv(); DownloadBlob=SavedDownload;');
Assert.match(GrabThing('Status').textContent, /original timestamps/);
Assert.doesNotMatch(GrabThing('Status').textContent, /search was not run/);
Assert.ok(RunApp('SummaryForExport().observation_view.display_time_map.enabled'));
Assert.match(RunApp("PdfAnalysisDetails(AnalysisPdfRow('two-nights.csv',CurrResult)).map(Line=>Line.text).join(' ')"), /OBSERVATION VIEW/);

//MARK: old caches still know where the night ended
RunApp(`
  MainResult={...InspectionFixture,total_points:4,domain:{time_min:0,time_max:6},
    normalization:{segment_time_ranges:[{start_day:0,end_day:1},{start_day:5,end_day:6}]},
    plot:{time:[0,1,5,6],raw_flux:[1,1,1,1],smooth_flux:[1,1,1,1]}};
  CurrResult=MainResult; CurrView='raw'; CurrViewport=null;
`);
Assert.equal(RunApp('CurrentObservation().display_time_map.runs.length'), 2);
CanvasDoodles.length = 0;
RunApp("DrawSeriesPath(ObservationTimes(),CurrentObservation().plot.raw_flux,X=>X,Y=>Y,{xMin:0,xMax:6},{breakIndices:CurrentObservation().plot.break_indices});");
Assert.equal(CanvasDoodles.filter(Call=>Call[0]==='lineTo').length, 2, 'legacy metadata cannot draw a line through the night gap');

//MARK: points crowded into the same screen column
RunApp(`
  const Time=Array.from({length:1000},(Unused,Index)=>Index/1000);
  const Flux=Array(1000).fill(100); Flux[505]=103;
  MainResult={...ObservationFixture,observation_view:{...ObservationFixture.observation_view,
    total_points:1000,domain:{time_min:0,time_max:.999},raw_domain:{flux_min:99,flux_max:104},
    plot:{time:Time,display_time:Time,raw_flux:Flux,flux_uncertainty:[],exposure_seconds:[]},
    display_time_map:{enabled:false,runs:[],gaps:[],knots:[]}}};
  CurrResult=MainResult; CurrView='raw'; CurrViewport=null;
  const DenseGeo=GetChartGeometry(), DenseView=GetViewport();
  UpdateObservationHover({x:DenseGeo.pad.left+.5/.999*DenseGeo.innerW,y:DenseGeo.pad.top+(DenseView.yMax-103)/(DenseView.yMax-DenseView.yMin)*DenseGeo.innerH});
`);
Assert.equal(RunApp('ObservationHoverIndex'), 505, 'hover finds visible peaks among overlapping samples');
RunApp("CurrResult=null; MainResult=null; CurrView='zoom'; CurrViewport=null; BatchInProgress=false; UpdateCurveTools();");
console.log('Observation viewer: original timestamps, gap map, units, hover, runs, cache, and exports passed.');

//MARK: exposure checks
GrabThing("ExposureSecondsInput").value = '0';
Assert.equal(RunApp("DetectionOptions().exposureSeconds"), 0,
             'instantaneous exposure override remains a numeric zero');
GrabThing("ExposureSecondsInput").value = '';
Assert.equal(RunApp("DetectionOptions().exposureSeconds"), null, 'blank exposure stays unknown');
Assert.match(RunApp("ExposureSummary({known_rows:0,unknown_rows:10})"),
             /Unknown; template evaluated as instantaneous/);
Assert.match(
    RunApp(
        "ExposureSummary({known_rows:10,unknown_rows:0,minimum_seconds:0,maximum_seconds:0,source:'explicit per-file override'})"),
    /0.* s; 10 declared samples/,
);
//MARK: eta checks
Assert.match(
    RunApp(
        "SearchEtaText({eta_state:'available',estimated_remaining_seconds:1020,eta_lower_seconds:840,eta_upper_seconds:1260},{stage:'tls_search'})"),
    /about 17 min/,
);
Assert.match(
    RunApp(
        "SearchEtaText({eta_state:'available',estimated_remaining_seconds:1020,eta_lower_seconds:540,eta_upper_seconds:3120},{stage:'tls_search'})"),
    /estimating/,
    'a 9–52min range is withheld, not made artificially precise',
);
Assert.match(
    RunApp(
        "SearchEtaText({eta_state:'estimating',estimated_remaining_seconds:1020,eta_lower_seconds:840,eta_upper_seconds:1260},{stage:'tls_search'})"),
    /estimating/,
);
Assert.match(
    RunApp(
        "SearchEtaText({eta_state:'available',estimated_remaining_seconds:1020,eta_lower_seconds:840,eta_upper_seconds:1260},{stage:'tls_finalizing'})"),
    /Finalizing/,
);
console.log('Exposure controls and uncertainty-aware ETA labels passed.');

//MARK: shared fake page
//  other checks reuse this fake page and its canvas doodles.
module.exports = {
  context : FakeAppThing,
  run : RunApp,
  elements : FakeBits,
  calls : CanvasDoodles
};

//MARK: reconnect checks
async function CheckRequestRecovery()
{
  // the fetch stub below returns one job id for both submission and polling.
  const CurveFile = new Blob([ 'Time,Flux\n0,1\n1,1' ]);
  CurveFile.name = 'sample.csv';
  FakeAppThing.TestFile = CurveFile;
  const Requests = [];
  const Result = {transits : [], planet_assessment : {status : 'no_planet_like_signal', candidate_score : 0}};
  //MARK: fake job replies
  FakeAppThing.fetch = async (Url, Options = {}) =>
  {
    Requests.push({url : Url, options : Options});
    if (Options.method === 'POST')
    {
      return {ok : true, json : async () => ({job_id : 'existing-job', status : 'queued'})};
    }
    return {ok : true, json : async () => ({job_id : 'existing-job', status : 'completed', result : Result})};
  };
  RunApp(`
    BatchRunId = 'batch-recovery';
    RunningFileIndex = 0;
    RequestId = null;
    RunningJobId = null;
    JobConnectionLost = false;
    AnalysisCancelRequested = false;
  `);
  await RunApp("RunCurve(TestFile,DetectionOptions())");
  Assert.equal(Requests.filter(R => R.options.method === 'POST').length, 1);
  Assert.equal(Requests[0].options.body.get('analysisRequestId'), 'batch-recovery:0');
  Assert.equal(Requests[0].options.body.has('exposureSeconds'), false,
               'blank exposure is not submitted as a known duration');
  Assert.equal(RunApp("RunningJobId"), null);

  //MARK: no extra upload
  Requests.length = 0;
  RunApp(`
    RunningJobId = 'existing-job';
    RequestId = 'batch-recovery:0';
  `);
  await RunApp("RunCurve(TestFile,DetectionOptions(),()=>{},'existing-job')");
  Assert.equal(Requests.filter(R => R.options.method === 'POST').length, 0,
               'reconnect polls the original job without submitting');
  Assert.match(Requests[0].url, /existing-job/);
  console.log('Frontend request recovery: stable request token and poll-only reconnect passed.');

  //MARK: exposure upload
  GrabThing('InspectOnlyInput').checked = true;
  GrabThing('CutGapsInput').checked = true;
  GrabThing('GapMinutesInput').value = '45';
  for (const [FileIndex, Exposure] of [[ 1, '0' ], [ 2, '1200' ]])
  {
    Requests.length = 0;
    GrabThing("ExposureSecondsInput").value = Exposure;
    RunApp(`
      RunningFileIndex = ${FileIndex};
      RunningJobId = null;
      RequestId = null;
    `);
    await RunApp("RunCurve(TestFile,DetectionOptions())");
    const Submitted = Requests.find(Request => Request.options.method === 'POST');
    Assert.equal(Submitted.options.body.get('inspectOnly'), 'true');
    Assert.equal(Submitted.options.body.get('cutGaps'), 'true');
    Assert.equal(Submitted.options.body.get('gapMinutes'), '45');
    Assert.equal(Submitted.options.body.get('exposureSeconds'), Exposure,
                 'the declared exposure reaches the upload request');
  }
  GrabThing("ExposureSecondsInput").value = '';
  console.log('Exposure submission: blank omitted; instantaneous zero and 1200 seconds preserved.');
}

//MARK: run async checks
if (require.main === module)
{
  CheckRequestRecovery().catch(RunError =>
  {
    console.error(RunError);
    process.exitCode = 1;
  });
}
