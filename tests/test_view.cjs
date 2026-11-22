// Exercise the shipped HTML, including empty results, review scope and duplicate scope.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const html=fs.readFileSync('public/index.html','utf8');
const js=[...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].at(-1)[1];
let nodes={};
function element(){
 return {innerHTML:'',value:'',textContent:'',dataset:{},children:[],append(){},prepend(){},querySelectorAll(){return []},addEventListener(){}};
}
const document={querySelector:s=>nodes[s]??=element(),createElement:element};
const context=vm.createContext({document,window:{addEventListener(){},scrollTo(){}},localStorage:{getItem(){return null}},URL,console});
vm.runInContext(js,context);
const run=s=>vm.runInContext(s,context);
assert.match(html, /<details id="ranges"[^>]* open>/);
assert.match(nodes["#ranges"].innerHTML, /<summary>Date ranges<\/summary>/);
assert.equal(nodes["#ranges"].open,true);
assert.equal(run('downloadDates().days'),90);
assert.equal(nodes['#downloadEnd'].value,new Date(Date.now()-86400000).toISOString().slice(0,10));
assert.equal(nodes['#rangeStart'].value,nodes['#downloadStart'].value);
assert.equal(nodes['#rangeEnd'].value,nodes['#downloadEnd'].value);
run("$('#downloadStart').value='2026-08-24'; $('#downloadEnd').value='2026-11-21'; $('#downloadEnd').oninput()");
assert.equal(nodes['#rangeStart'].value,'2026-08-24');
assert.equal(nodes['#rangeEnd'].value,'2026-11-21');
run("$('#rangeEnd').value='2026-10-20'; estimate()");
assert.equal(nodes['#rangeEnd'].value,'2026-10-20');
assert.match(nodes['#ranges'].innerHTML, /<option value="sample" selected>/);
run("$('#collectionMode').value='sample';estimate()");
assert.match(nodes['#rangeScope'].textContent,/1,080 event records/);
run("$('#collectionMode').value='all';estimate()");
assert.match(nodes['#rangeScope'].textContent,/8,640 quarter-hour/);
run("change('Research report')");
assert.match(nodes['#app'].innerHTML, /application\/pdf/);
assert.ok(nodes['#app'].innerHTML.includes('reports/GDELT_Full_Research_Review_20261120.pdf'));
assert.equal(nodes['#ranges'].open,false);
run("change('Overview')");
const full=run('records.length');
run("$('#rangeStart').value='2026-10-01'; $('#rangeEnd').value='2026-10-31'; applyRange()");
assert.equal(run('records.length'),372);
assert.equal(run('mapGroups(records,\u0027\u0027).mapped+mapGroups(records,\u0027\u0027).omitted'),372);
run("$('#eventStart').value='1900-01-01'; $('#eventEnd').value='1900-01-01'; applyRange()");
assert.equal(run('records.length'),0);
run("switchSample(sourceSnapshot)");
assert.equal(run('records.length'),full);
const id=run('records[0].id');
run("reviews[records[0].id]=fresh();reviews[records[0].id].fields[0]='Supported'");
run('overview()');assert.match(nodes['#app'].innerHTML,/100% \(1\/1\)/);
run("$('#rangeStart').value='2026-10-01'; $('#rangeEnd').value='2026-10-01'; applyRange();overview()");
assert.doesNotMatch(nodes['#app'].innerHTML,/100% \(1\/1\)/);
assert.equal(run('Object.keys(reviews)[0]'),id);
console.log('October filter, map denominator, empty result, reset and review scoping passed');
// Force a two-day duplicate group and verify rescanning when one day is hidden.
const scopeTest=run(`(()=>{
 const a=flatten(sourceSnapshot)[0],b=sourceSnapshot.batches[1];
 const peer={...a,raw:[...a.raw],mentions:[]};peer.raw[0]='9999999999';
 const sample={...sourceSnapshot,batches:[{...a.b,sample:[a]},{...b,sample:[peer]}]};
 switchSample(sample);
 if(!passes(a.id,'article'))return false;
 $('#rangeEnd').value=a.b.day;applyRange();
 return !passes(a.id,'article') && outsideLinks(a.id).includes(peer.raw[0]);
})()`);
assert.equal(scopeTest,true);
async function testDownloadUI(){
 run("$('#downloadStart').value='2026-01-21';$('#downloadEnd').value='2026-11-20';estimate()");
 assert.match(nodes['#rangeScope'].textContent,/304 days/);
 assert.equal(nodes['#rangeFetch'].disabled,true);
 run("$('#downloadStart').value='2026-08-21';$('#downloadEnd').value='2026-08-22';estimate()");
 const progress=[];
 document.querySelector('#downloadBar').removeAttribute=()=>{delete nodes['#downloadBar'].value};
 context.setTimeout=(fn)=>{progress.push([nodes['#rangeState'].textContent,nodes['#downloadBar'].value]);fn()};
 run(`let tick=0;api=async(path)=>{
 if(path==='jobs')return {id:'test'};
 if(path.endsWith('/result'))return viewRange(sourceSnapshot,'2026-08-21','2026-08-22','','');
 if(path.endsWith('/previews'))return {};
 return [{state:'queued',done:0,total:2},{state:'collecting',done:1,total:2},{state:'ready',done:2,total:2,metadata:'complete'}][tick++];
 }`);
 await run('collectNew()');
 assert.deepEqual(progress,[['Queued for download',undefined],['Downloading archive records…',1]]);
 assert.match(nodes['#downloadDetail'].textContent,/24 records/);
 assert.match(nodes['#rangeState'].textContent,/Ready to analyze/);
 assert.equal(nodes['#downloadBar'].value,2);
 assert.equal(nodes['#useRange'].hidden,true);
 assert.equal(run('loaded===pendingSample'),true);
 assert.equal(run('JSON.stringify([...flags])===JSON.stringify([...scanRows(records)])'),true);
 assert.equal(run('records.length'),24);
 run("tab=paths[2];show()");
 assert.equal(nodes['#ranges'].open,false);
 nodes['#ranges'].open=true;run('show()');
 assert.equal(nodes['#ranges'].open,true);
 run("tab=paths[3];show()");
 assert.equal(nodes['#ranges'].open,false);
 run("tab=paths[0];show()");
 assert.equal(nodes['#ranges'].open,true);
 run('dirty=true;tick=0');
 await run('collectNew()');
 assert.equal(run('loaded===pendingSample'),false);
 assert.equal(nodes['#useRange'].hidden,false);
 run('dirty=false');
 nodes['#useRange'].onclick();
 assert.equal(run('loaded===pendingSample'),true);
 run("api=async()=>{throw Error('Temporary connection error')}");
 await run('collectNew()');
 assert.equal(nodes['#rangeState'].textContent,'Download failed');
 assert.equal(nodes['#rangeFetch'].disabled,false);
 console.log('Validated download limit, queued, in-progress, ready, open and retry states.');
}
async function testFullUI(){
 const sample=run("sourceSnapshot.batches[0]");
 const stamp=sample.stamp;
 context.sample=sample;
 run("collectorBase=async()=>'';api=async path=>{if(path==='ranges')return {id:'full'};if(path==='ranges/full')return {state:'ready',done:96,total:96,rows:1248,gaps:0,counts:[1248,96,96,0,0]};if(path.endsWith('manifest'))return [[sample.stamp,12,0]];if(path.includes('/previews/'))return {state:'complete',previews:{}};return sample}");
 await run('collectFull()');
 assert.equal(nodes['#fullResults'].hidden,false);
 assert.match(nodes['#fullResults'].innerHTML,/1,248/);
 assert.equal(nodes['#allEvents'].href,'/api/ranges/full/events.tsv');
 assert.equal(run('loaded.full'),true);
 assert.equal(nodes['#rangeEnd'].value,nodes['#downloadEnd'].value);
 assert.equal(run('loaded.batches[0].stamp'),stamp);
 assert.match(nodes['#rangeState'].textContent,/Ready to analyze/);
 nodes['#rangeRestore'].onclick();
 assert.equal(nodes['#fullResults'].hidden,true);
 console.log('Verified full-range totals, export link, archive detail and restore.');
}

async function testPreflight(){
 const dialog=nodes['#volumeDialog'];
 dialog.showModal=()=>dialog.open=true;
 dialog.close=()=>{dialog.open=false;dialog.onclose()};
 run("let calls=[];api=async(path,options)=>{calls.push([path,options?.method]);return {exact:4321}}");
 context.AbortSignal=AbortSignal;
 nodes['#collectionMode'].value='sample';
 await nodes['#rangeFetch'].onclick();
 assert.equal(dialog.open,true);
 assert.match(nodes['#volumeSize'].textContent,/4,321 event rows/);
 assert.match(nodes['#volumeSize'].textContent,/up to 24 records/);
 nodes['#reviseDates'].onclick();
 assert.equal(run("calls.some(([,method])=>method==='POST')"),false);
 console.log('Size preview and dismissal issue no collection request.');
}

testDownloadUI().then(testFullUI).then(testPreflight).catch(e=>{console.error(e);process.exitCode=1});


