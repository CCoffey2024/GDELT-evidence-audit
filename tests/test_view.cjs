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
 nodes['#useRange'].onclick();
 assert.equal(run('records.length'),24);
 assert.equal(nodes['#rangeState'].textContent,'Viewing downloaded records');
 run("api=async()=>{throw Error('Temporary connection error')}");
 await run('collectNew()');
 assert.equal(nodes['#rangeState'].textContent,'Download failed');
 assert.equal(nodes['#rangeFetch'].disabled,false);
 console.log('Validated download limit, queued, in-progress, ready, open and retry states.');
}
testDownloadUI().catch(e=>{console.error(e);process.exitCode=1});
