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
  querySelectorAll : () => [],
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
console.log('Frontend review: 12 behavior groups passed (including signal selection and chart focus).');

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
