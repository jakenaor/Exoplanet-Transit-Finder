// Focused behavior checks; no browser, server, or analysis workers are started.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const calls=[];
const canvasContext = new Proxy({measureText:text=>({width:String(text).length*6})}, {
  get(target,key) { return key in target ? target[key] : (...args)=>{calls.push([key,...args]);}; },
});
function element(id) {
  return {id,value:'',checked:true,hidden:false,disabled:false,innerHTML:'',textContent:'',scrollTop:0,dataset:{},clientWidth:900,clientHeight:500,
    style:{setProperty(){},removeProperty(){}},classList:{add(){},remove(){},toggle(){}},listeners:{},
    addEventListener(type,callback){(this.listeners[type]??=[]).push(callback);},
    setAttribute(){},removeAttribute(){},querySelector(){return null;},querySelectorAll(){return [];},
    getContext(){return canvasContext;},getBoundingClientRect(){return {width:900,height:500,left:0,top:0};},
    replaceChildren(){},append(){},focus(){document.activeElement=this;},remove(){},contains(){return false;},setPointerCapture(){},hasPointerCapture(){return false;}};
}
const elements=new Map();const get=id=>elements.get(id)||elements.set(id,element(id)).get(id);
for(const [id,value] of Object.entries({strictnessInput:'1',smoothingInput:'1',searchModeInput:'tls',tlsMaxSignalsInput:'1',batchSort:'index',phaseScope:'focus',stackEvent:'all',stackGroup:'all'}))get(id).value=value;
const document={getElementById:get,querySelector:()=>get('main'),querySelectorAll:()=>[],listeners:{},
  addEventListener(type,fn){(this.listeners[type]??=[]).push(fn);},createElement:()=>element('new'),body:element('body')};
const context=vm.createContext({document,console,Blob,FormData,URL,Map,Set,Date,Math,JSON,Number,Array,Object,String,Promise,
  window:{matchMedia:()=>({matches:false}),addEventListener(){},setTimeout(){return 1;},clearTimeout(){},setInterval(){return 1;},clearInterval(){},devicePixelRatio:1,location:{href:'http://localhost/'}}});
let source=fs.readFileSync(path.join(__dirname,'../Exoplanet data parsing tool/static/app.js'),'utf8');
source=source.replace('sessionReadyPromise = initializeSession();','sessionReadyPromise = Promise.resolve();');
vm.runInContext(source,context);
const run=code=>vm.runInContext(code,context);

for(const input of ['null','undefined',"''","'  '",'true','false','NaN','Infinity','{}','[]'])assert.equal(run(`nullableNumber(${input})`),null);
assert.equal(run('nullableNumber(0)'),0);assert.equal(run("nullableNumber('0')"),0);
run(`currentResult={transits:[],period_sde:1000,tls_fap:null,planet_assessment:{status:'no_planet_like_signal',short_label:'Saved verdict',candidate_score:12,supporting_evidence:[],limiting_evidence:[]}};`);
assert.equal(run('currentPlanetAssessment().candidateScore'),12,'UI must retain backend verdict despite a large SDE');
assert.equal(run('currentPlanetAssessment().shortLabel'),'Saved verdict');
run('currentResult={transits:[]};');
assert.equal(run('currentPlanetAssessment().candidateScore'),null,'legacy data must not be silently rescored');

run(`batchInProgress=true;batchResults=[{file:{name:'complete.csv'},result:{transits:[],period:2,planet_assessment:{status:'strong_candidate',candidate_score:80,short_label:'Strong'}}},{file:{name:'running.csv'},result:null,status:'running'}];currentBatchIndex=0;renderBatchSelect();`);
assert.equal(get('resultSelect').disabled,false,'completed results remain navigable during batch');
assert.equal(get('batchPickerButton').disabled,false);
assert.match(get('resultSelect').innerHTML,/value="1" disabled/,'unfinished results cannot be selected');
assert.match(get('batchPickerMeta').textContent,/candidate score/);

run(`currentResult={normalization:{segment_time_ranges:[{start_day:0,end_day:1},{start_day:10,end_day:11}]}};`);
calls.length=0;
run(`drawSeriesPath([0,1,10,11],[1,1,1,1],x=>x,y=>y,{xMin:0,xMax:11},{timeSeries:true});`);
assert.equal(calls.filter(c=>c[0]==='moveTo').length,2,'observation gap starts a new path');
assert.equal(calls.filter(c=>c[0]==='lineTo').length,2,'no line bridges the gap');

run(`currentView='clean';currentResult={plot:{time:Array.from({length:21},(_,i)=>i),raw_flux:Array(20).fill(1).concat([100])}};`);
assert.ok(run(`transitFluxRange({start:0,end:20,depth:.01},Array(20).fill(1).concat([100])).high`)<2,'one raw spike cannot stretch a cleaned-view box');
assert.equal(run('traceEventIndex({transit_index:1},4)'),0,'stack event IDs remain one-based in payloads');
run(`currentResult={transits:[]};`);
assert.equal(run(`classifyTransitForEphemeris({source:'TLS model',center:2},{period:2,periodEpoch:0,periodDuration:.1}).status`),'unknown','predicted centers are not timing measurements');

let prevented=false;
for(const handler of document.listeners.keydown)handler({key:'ArrowUp',target:{closest:()=>({})},preventDefault(){prevented=true;}});
assert.equal(prevented,false,'chart shortcuts do not capture input arrow keys');

run('globalThis.zoomCalls=[];globalThis.savedZoomAtPointer=zoomAtPointer;zoomAtPointer=(...args)=>zoomCalls.push(args);currentResult={transits:[]};');
const ordinaryChartButton={closest:selector=>selector.split(',').includes('button') ? {} : null};
for(const key of ['ArrowUp','ArrowDown','ArrowLeft','ArrowRight']) {
  let handled=false;
  for(const handler of document.listeners.keydown)handler({key,target:ordinaryChartButton,defaultPrevented:false,preventDefault(){handled=true;}});
  assert.equal(handled,true,`${key} still controls the graph after clicking a chart button`);
}
assert.deepEqual(JSON.parse(run('JSON.stringify(zoomCalls)')),[[.72],[1.28],[1.28,'x'],[.72,'x']]);
for(const target of [{closest:()=>({})},{isContentEditable:true},{closest:selector=>selector.includes('aria-haspopup') ? {} : null}]) {
  for(const handler of document.listeners.keydown)handler({key:'ArrowUp',target,preventDefault(){throw Error('Control arrow key was stolen');}});
}
for(const handler of document.listeners.keydown)handler({key:'ArrowUp',target:ordinaryChartButton,defaultPrevented:true,preventDefault(){throw Error('Already handled key was stolen');}});
assert.equal(run('zoomCalls.length'),4);
run('zoomAtPointer=savedZoomAtPointer;globalThis.savedGetViewport=getViewport;globalThis.savedPointerPosition=pointerPosition;getViewport=()=>({xMin:0,xMax:10,yMin:0,yMax:2});pointerPosition=()=>({x:100,y:100});');
for(const handler of get('chart').listeners.pointerdown)handler({button:0,pointerId:3,preventDefault(){}});
assert.equal(document.activeElement,get('chart'),'clicking the graph moves keyboard focus away from the last edited control');
run('getViewport=savedGetViewport;pointerPosition=savedPointerPosition;dragState=null;');

get('perFileSettings').value='{"a.csv":{"inventedSetting":1}}';
assert.throws(()=>run('readPerFileSettings()'),/Unknown per-file setting/);
console.log('Frontend review: 11 behavior groups passed (including arrow shortcuts and chart focus).');
module.exports = {context,run,elements,calls};

async function checkRequestRecovery() {
  const file=new Blob(['Time,Flux\n0,1\n1,1']);file.name='sample.csv';context.testFile=file;
  const requests=[];
  const result={transits:[],planet_assessment:{status:'no_planet_like_signal',candidate_score:0}};
  context.fetch=async(url,options={})=>{
    requests.push({url,options});
    if(options.method==='POST')return {ok:true,json:async()=>({job_id:'existing-job',status:'queued'})};
    return {ok:true,json:async()=>({job_id:'existing-job',status:'completed',result})};
  };
  run(`activeBatchId='batch-recovery';activeFileIndex=0;activeRequestId=null;activeAnalysisJobId=null;jobConnectionLost=false;analysisCancelRequested=false;`);
  await run('analyzeFile(testFile,detectionOptions())');
  assert.equal(requests.filter(r=>r.options.method==='POST').length,1);
  assert.equal(requests[0].options.body.get('analysisRequestId'),'batch-recovery:0');
  assert.equal(run('activeAnalysisJobId'),null);
  requests.length=0;
  run(`activeAnalysisJobId='existing-job';activeRequestId='batch-recovery:0';`);
  await run(`analyzeFile(testFile,detectionOptions(),()=>{},'existing-job')`);
  assert.equal(requests.filter(r=>r.options.method==='POST').length,0,'reconnect polls the original job without submitting');
  assert.match(requests[0].url,/existing-job/);
  console.log('Frontend request recovery: stable request token and poll-only reconnect passed.');
}
if(require.main===module)checkRequestRecovery().catch(error=>{console.error(error);process.exitCode=1;});
