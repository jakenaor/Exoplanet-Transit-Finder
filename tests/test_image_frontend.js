//MARK: tiny fake page so async button races are repeatable
const Assert = require('node:assert/strict');
const Fs = require('node:fs');
const Path = require('node:path');
const Vm = require('node:vm');
const StaticDir = Path.join(__dirname, '../Exoplanet data parsing tool/static');
const OldId = 'a'.repeat(32);
const NewId = 'b'.repeat(32);
const Tick = () => new Promise(Resolve => setImmediate(Resolve));

function Later()
{
  let Resolve;
  const PromiseThing = new Promise(Done => { Resolve = Done; });
  return {PromiseThing, Resolve};
}

function FakePage()
{
  const Bits = new Map();
  const Pen = new Proxy({}, {get:(Thing, Key) => Thing[Key] || (() => {}), set:(Thing, Key, Value) => (Thing[Key] = Value, true)});
  function Get(Id)
  {
    if (!Bits.has(Id))
      Bits.set(Id, {
        value:'', disabled:false, hidden:false, width:1000, height:650, listeners:{},
        classList:{add() {}, toggle() {}},
        setAttribute() {}, getAttribute() { return null; },
        addEventListener(Key, Callback) { (this.listeners[Key] ??= []).push(Callback); },
        getContext() { return Pen; }, replaceChildren() {}, append() {},
        getBoundingClientRect() { return {left:0, top:0, width:1000, height:650}; },
      });
    return Bits.get(Id);
  }
  return {Get, Doc:{getElementById:Get, body:Get('body'), createElement:() => Get(Symbol())}};
}

function ImagePage(Saved = null, Fetch = async () => { throw new Error('unexpected fetch'); })
{
  const Page = FakePage();
  for (const [Id, Value] of Object.entries({ApertureRadius:8, SkyInner:12, SkyOuter:20, TrackRadius:12, ImageWorkers:4, ImageClock:'start'}))
    Page.Get(Id).value = Value;
  const Timers = [];
  const Window = {setTimeout(Callback) { Timers.push(Callback); return Timers.length; }, clearTimeout() {}, location:{href:'http://localhost/images'}};
  Window.parent = Window;
  const Context = Vm.createContext({
    document:Page.Doc, window:Window, fetch:Fetch, console, AbortController, FormData,
    localStorage:{getItem() { return Saved && JSON.stringify(Saved); }, setItem() {}},
    Image:class { set src(Value) { queueMicrotask(() => this.onload()); } },
  });
  Vm.runInContext(Fs.readFileSync(Path.join(StaticDir, 'images.js'), 'utf8'), Context);
  const Run = Source => Vm.runInContext(Source, Context);
  function Ready()
  {
    Run("ImageRun={id:'" + OldId + "',status:'uploading',science_count:2,dark_count:2};PreviewThing={factor:1};StarThingies=[[40,40]];");
  }
  return {Page, Context, Timers, Run, Ready, Click:Id => Page.Get(Id).listeners.click[0]()};
}

function FinderPage()
{
  const Page = FakePage(), Track = {restored:0};
  const Context = Vm.createContext({
    document:Page.Doc, window:{location:{href:'http://localhost/?session=old_session'}, history:{replaceState() {}}},
    URL, console, FileResults:[{result:{old:true}}], BatchInProgress:false, RunningJobId:null,
    RequestId:null, JobConnectionLost:false, ResultViewports:new Map(), SessionId:'old_session',
    SaveRunNow:async () => true, fetch:async () => ({ok:true, json:async () => ({state:{new:true}})}),
    RestoreSessionState() { Track.restored++; }, DrawFlux() {}, SetStatus() {}, QueueSessionSave() {},
  });
  Vm.runInContext(Fs.readFileSync(Path.join(StaticDir, 'tabs.js'), 'utf8'), Context);
  return {Context, Track, Import:() => Vm.runInContext("OpenImageCurveFromImages('/?session=images_" + OldId + "')", Context)};
}

//MARK: controls lock before the server replies
async function CheckPendingButtons()
{
  const Work = ImagePage(), Start = Later();
  Work.Ready();
  Work.Context.PostImageJson = () => Start.PromiseThing;
  Work.Context.ImageApi = async () => ({id:OldId, status:'running', total:2, completed:0});
  const Pending = Work.Click('ProcessImages');
  Assert.equal(Work.Page.Get('PrepareImages').disabled, true);
  Assert.equal(Work.Page.Get('ProcessImages').disabled, true);
  Start.Resolve({id:OldId, status:'running'});
  await Pending;

  const Import = ImagePage(), Reply = Later();
  Import.Ready();
  Import.Run("ImageRun.status='completed';ImageRun.result={usable_frames:2};");
  let Calls = 0;
  Import.Context.PostImageJson = () => { Calls++; return Reply.PromiseThing; };
  const Opening = Import.Click('ImageToFinder');
  await Import.Click('ImageToFinder');
  Assert.equal(Calls, 1);
  Assert.equal(Import.Page.Get('PrepareImages').disabled, true);
  Assert.equal(Import.Page.Get('ImageToFinder').disabled, true);
  Reply.Resolve({url:'/?session=images_' + OldId});
  await Opening;
  Assert.equal(Import.Page.Get('PrepareImages').disabled, false);
}

//MARK: old replies should stay in the past
async function CheckStaleReplies()
{
  const Poll = ImagePage(), Reply = Later();
  Poll.Ready();
  Poll.Context.ImageApi = () => Reply.PromiseThing;
  const Pending = Poll.Run('PollImageRun()');
  Poll.Run("ImageGeneration++;ImageRun={id:'" + NewId + "',status:'uploading'};");
  Reply.Resolve({id:OldId, status:'completed'});
  await Pending;
  Assert.equal(Poll.Run('ImageRun.id'), NewId);

  const Preview = ImagePage(), Pixels = Later();
  Preview.Ready();
  Preview.Run('PreviewThing=null;');
  Preview.Context.ImageApi = () => Pixels.PromiseThing;
  const Loading = Preview.Run('LoadImagePreview()');
  Preview.Run("ImageGeneration++;ImageRun={id:'" + NewId + "',status:'uploading'};");
  Pixels.Resolve({name:'old preview'});
  await Loading;
  Assert.equal(Preview.Run('PreviewThing'), null);

  const Restore = Later();
  const Restored = ImagePage({id:OldId}, () => Restore.PromiseThing);
  Assert.equal(Restored.Page.Get('PrepareImages').disabled, true);
  Restored.Run("ImageGeneration++;ImageRun={id:'" + NewId + "',status:'uploading'};ImageBusy=false;");
  Restore.Resolve({ok:true, json:async () => ({id:OldId, science_count:0})});
  await Tick();
  Assert.equal(Restored.Run('ImageRun.id'), NewId);
}

async function CheckCancelDuringCreate()
{
  const Upload = ImagePage(), Reply = Later();
  Upload.Page.Get('ScienceImages').files = [{name:'light.fit', size:1}];
  Upload.Page.Get('DarkImages').files = [{name:'dark.fit', size:1}];
  Upload.Context.PostImageJson = () => Reply.PromiseThing;
  const Pending = Upload.Click('PrepareImages');
  await Upload.Click('CancelImages');
  Reply.Resolve({id:OldId, status:'uploading'});
  await Pending;
  Assert.equal(Upload.Run('ImageRun'), null);
  Assert.equal(Upload.Page.Get('PrepareImages').disabled, false);
}

async function CheckExpiredRun()
{
  const Work = ImagePage();
  Work.Ready();
  Work.Context.ImageApi = async () => { throw Object.assign(new Error('expired'), {status:400}); };
  await Work.Run('PollImageRun()');
  Assert.equal(Work.Run('ImageRun'), null);
  Assert.equal(Work.Page.Get('PrepareImages').disabled, false);
  Assert.equal(Work.Timers.length, 0);
}

//MARK: keep the current finder results until importing is actually safe
async function CheckFinderImports()
{
  const Save = FinderPage();
  Save.Context.SaveRunNow = async () => false;
  await Assert.rejects(Save.Import(), /Could not save/);
  Assert.equal(Save.Track.restored, 0);

  const Batch = FinderPage();
  Batch.Context.fetch = async () =>
  {
    Batch.Context.BatchInProgress = true;
    return {ok:true, json:async () => ({state:{new:true}})};
  };
  await Assert.rejects(Batch.Import(), /finder changed/);
  Assert.equal(Batch.Track.restored, 0);

  const Duplicate = FinderPage(), Reply = Later();
  Duplicate.Context.SaveRunNow = () => Reply.PromiseThing;
  const Pending = Duplicate.Import();
  await Assert.rejects(Duplicate.Import(), /already being imported/);
  Reply.Resolve(true);
  await Pending;
  Assert.equal(Duplicate.Track.restored, 1);
}

async function CheckQueuedSaveDestination()
{
  const Source = Fs.readFileSync(Path.join(StaticDir, 'app.js'), 'utf8');
  const SaveCode = Source.slice(Source.indexOf('function SaveRunNow()'), Source.indexOf('//MARK: queue save'));
  const First = Later(), Calls = [];
  const Context = Vm.createContext({
    SessionInitialized:true, RestoringSession:false, SessionId:'old_session', SessionSaveTimer:null,
    SessionSaveChain:Promise.resolve(true), window:{clearTimeout() {}}, console,
    PackRunState:() => ({marker:'old results'}), ShortSessionId:() => 'old',
    SetSessionIndicator() {}, SetSaveFileLocation() {}, ReadJsonResponse:async () => ({}),
    fetch:async (Url, Options) =>
    {
      Calls.push({Url, State:JSON.parse(Options.body)});
      if (Calls.length === 1)
        await First.PromiseThing;
      return {ok:true};
    },
  });
  Vm.runInContext(SaveCode, Context);
  const A = Vm.runInContext('SaveRunNow()', Context);
  await Tick();
  const B = Vm.runInContext('SaveRunNow()', Context);
  Context.SessionId = 'images_' + NewId;
  First.Resolve();
  await Promise.all([A, B]);
  Assert.equal(Calls.length, 2);
  Assert.ok(Calls.every(Call => Call.Url === '/analysis-sessions/old_session'));
}

(async () =>
{
  for (const Check of [CheckPendingButtons, CheckStaleReplies, CheckCancelDuringCreate, CheckExpiredRun, CheckFinderImports, CheckQueuedSaveDestination])
  {
    await Check();
    console.log('ok ' + Check.name);
  }
})().catch(ErrorThing => { console.error(ErrorThing); process.exitCode = 1; });
