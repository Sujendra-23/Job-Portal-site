const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('index.html','utf8');
const inline = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1].replace(/load\(\);\s*$/, '');
const extra = fs.readFileSync('automation/portal-automation.js','utf8');
function run(code) {
  const c = {console, document: {createElement: () => ({set textContent(s) {this.innerHTML = String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}})}};
  vm.createContext(c); vm.runInContext(extra + '\n' + inline, c);
  return vm.runInContext(code,c);
}
test('existing tabs and resume tracking keys retained', () => {
  assert.equal(run("TABS.map(t=>t.id).join(',')"), 'ft,intern,leads,emails');
  assert.equal(run("key({company:'Acme',title:'SWE'})"), 'Acme||SWE');
  assert.ok(html.includes('jobportal_applied_v1'));
});
test('co-op and plural internship titles route correctly', () => {
  assert.equal(run("isIntern({title:'Software Engineering Internships', employment_type:'internship'})"),true);
  assert.equal(run("isIntern({title:'Backend Developer', employment_type:'co-op'})"),true);
});
test('automated expired and excluded roles hidden, original roles preserved', () => {
  assert.equal(run("automationVisible({status:'expired'})"),true);
  assert.equal(run("automationVisible({automation_source:'feed',status:'expired'})"),false);
  assert.equal(run("automationVisible({automation_source:'feed',filter_status:'excluded'})"),false);
});
test('eligibility output escapes untrusted text and attribute quotes', () => {
  const result = run(`automationDetails({automation_source:'feed', category:'<img src=x>',source_url:'https://example.com/" onmouseover="x',eligibility_evidence:'<script>bad</script>'})`);
  assert.ok(result.includes('&lt;script&gt;'));
  assert.ok(!result.includes('<img'));
  assert.ok(!result.includes('href="https://example.com/" onmouseover='));
});
test('unverified data remains isolated', () => {
  assert.equal(run("DATA={unverified:[{company:'Lead',title:'Software Engineer'}],jobright:[{company:'Actual',title:'SWE'}]};tabRoles({kind:'leads'})[0].company"),'Lead');
});
test('support rank requires explicit current posting evidence', () => {
  assert.equal(run("sponsorshipRank({sponsorship_history:'Sponsored in 2024'})"),0);
  assert.equal(run("sponsorshipRank({opt:'supported'})"),1);
});
test('public Jobright leads never enter verified tabs', () => {
  assert.equal(run("DATA={jobright_public:[{company:'Public',title:'Software Engineer, New Grad 2027',automation_source:'jobright-public-github'}]};tabRoles({kind:'ft'}).length"),0);
  assert.equal(run("DATA={jobright_public:[{company:'Public',title:'Software Engineer, New Grad 2027',automation_source:'jobright-public-github'}]};tabRoles({kind:'leads'}).length"),1);
});
test('public leads use a view-listing link without inventing an employer Apply URL', () => {
  assert.ok(html.includes("(r.application_link?'Apply':'View listing')"));
  assert.ok(html.includes('r.application_link || r.source_url'));
});
