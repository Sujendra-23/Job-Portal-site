const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('index.html','utf8');
const inline = html.match(/<script>\s*([\s\S]*?)<\/script>/)[1].replace(/load\(\);\s*$/, '');
const extra = fs.readFileSync('automation/portal-automation.js','utf8');
function run(code) {
  const c = {console, document: {createElement: tag => tag === 'textarea' ? ({set innerHTML(s) {this.value=String(s).replace(/&lt;/g,'<').replace(/&gt;/g,'>').replace(/&amp;/g,'&')}}) : ({set textContent(s) {this.innerHTML = String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}})}};
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
test('public full-time jobs enter only the full-time tab', () => {
  assert.equal(run("DATA={jobright_public:[{company:'Public',title:'Software Engineer, New Grad 2027',automation_source:'jobright-public-github',category:'Full-Time 2027',employment_type:'full-time'}]};[tabRoles({kind:'ft'}).length,tabRoles({kind:'intern'}).length,tabRoles({kind:'leads'}).length].join(',')"),'1,0,0');
});
test('public Spring internships and co-ops enter only the internship tab', () => {
  assert.equal(run("DATA={jobright_public:[{company:'Intern',title:'Software Engineer',automation_source:'jobright-public-github',category:'Spring 2027 Internship'},{company:'Coop',title:'Backend Engineer',automation_source:'jobright-public-github',category:'Spring 2027 Co-op'}]};[tabRoles({kind:'ft'}).length,tabRoles({kind:'intern'}).length,tabRoles({kind:'leads'}).length].join(',')"),'0,2,0');
});
test('existing curated job takes precedence over a duplicate public job', () => {
  assert.equal(run("DATA={top:[{company:'Same',title:'Software Engineer',location:'US',description:'curated'}],jobright_public:[{company:'Same',title:'Software Engineer',location:'US',automation_source:'jobright-public-github',category:'Full-Time 2027'}]};tabRoles({kind:'ft'}).map(r=>r.description).join(',')"),'curated');
});
test('excluded and expired collected jobs are not routed into any role tab', () => {
  assert.equal(run("DATA={jobright_public:[{company:'Excluded',title:'Software Engineer',automation_source:'jobright-public-github',filter_status:'excluded'},{company:'Expired',title:'Software Engineer',automation_source:'jobright-public-github',status:'expired'}]};tabRoles({kind:'ft'}).length+tabRoles({kind:'intern'}).length"),0);
});
test('public leads use a view-listing link without inventing an employer Apply URL', () => {
  const rendered = run("rowHtml({company:'Public',title:'SWE',description:'Source details',automation_source:'jobright-public-github',application_link:null,source_url:'https://jobright.ai/jobs/info/test'})");
  assert.ok(rendered.includes('>View listing</a>'));
  assert.ok(rendered.includes('href="https://jobright.ai/jobs/info/test"'));
  assert.ok(!rendered.includes('href="null"'));
});

test('page loads automation helpers and both Jobright data sources', () => {
  assert.match(html, /<script\s+src="automation\/portal-automation\.js"/);
  assert.equal(run("ROLE_FILES.jobright_public"), 'roles_jobright_public.json');
  assert.equal(run("ROLE_FILES.jobright"), 'roles_jobright.json');
});
test('posting dates accept ISO timestamps and never show Invalid Date', () => {
  assert.equal(run("fmtDate('2026-11-20T10:00:00Z')"),'November 20, 2026');
  assert.equal(run("fmtDate('not a date')"),'Date not listed');
});
