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
