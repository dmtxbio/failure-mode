const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const crypto = require('node:crypto');
const source = fs.readFileSync(require('node:path').join(__dirname,'../web/app.js'),'utf8');
const context = vm.createContext({crypto});
vm.runInContext(source.replace(/\ninit\(\);\s*$/, '\nthis.testAPI = {validateProject, escapeHTML, state};'),context);
const api = context.testAPI;
api.state.taxonomy=[{id:'efficacy'}];
test('restoring a workspace preserves assessment and rejects unsupported metadata',()=>{
  const p = api.validateProject({name:'A program',stage:'Development',context:'Protocol draft',entries:{efficacy:{status:'gap',notes:'Endpoint unresolved',owner:'Clinical',evidence:'Protocol §2'},unknown:{status:'addressed'}}});
  assert.equal(p.entries.efficacy.status,'gap');
  assert.equal(p.entries.efficacy.notes,'Endpoint unresolved');
  assert.equal(p.entries.efficacy.evidence,'Protocol §2');
  assert.equal(p.entries.unknown,undefined);
  assert.throws(()=>api.validateProject({name:'A',stage:'Invalid'}),/valid workspace/);
});
test('imported statuses cannot inject markup or mark a review complete',()=>{
  const p=api.validateProject({name:'A',stage:'Submission',entries:{efficacy:{status:'<script>alert(1)</script>'}}});
  assert.equal(p.entries.efficacy.status,'unreviewed');
});
test('source text is escaped before rendering',()=>{
  assert.equal(api.escapeHTML('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
});
