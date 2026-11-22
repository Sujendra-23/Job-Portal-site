/* Additive portal integration: existing resume keys and local storage are unchanged. */
let SYNC_STATUS = null;
const automationVisible = r => !r.automation_source || (r.filter_status !== 'excluded' && r.status !== 'expired');
const sponsorshipRank = r => ['sponsorship', 'cpt', 'opt'].filter(k => r[k] === 'supported').length;
function automationDetails(r) {
  if (!r.automation_source) return '';
  const labels = {supported: 'supported in posting', restricted: 'restricted', unknown: 'unknown'};
  return '<br><span class="badge">' + esc(r.category || '') + '</span>' +
    '<br><small>H-1B: ' + esc(labels[r.sponsorship] || 'unknown') +
    ' · CPT: ' + esc(labels[r.cpt] || 'unknown') + ' · OPT: ' + esc(labels[r.opt] || 'unknown') + '</small>' +
    (r.sponsorship_history ? '<br><small>Employer history: ' + esc(r.sponsorship_history) + ' (not a guarantee)</small>' : '') +
    (r.eligibility_evidence ? '<br><small>' + esc(r.eligibility_evidence) + '</small>' : '') +
    (r.eligibility_source_url ? '<br><a href="' + esc(r.eligibility_source_url) + '" target="_blank" rel="noopener noreferrer">Eligibility evidence</a>' : '') +
    '<br><small>Listing status: ' + esc(r.status || 'unknown') + ' · Checked: ' + esc(r.last_checked || 'unknown') + '</small>' +
    '<br><a href="' + esc(r.source_url) + '" target="_blank" rel="noopener noreferrer">Source: Jobright</a>';
}
function paintSyncStatus() {
  const el = document.getElementById('automation-meta');
  if (!SYNC_STATUS || !SYNC_STATUS.last_success) {
    el.textContent = 'Jobright import: awaiting an authorized feed';
    return;
  }
  const last = new Date(SYNC_STATUS.last_success);
  const stale = Date.now() - last.getTime() > 7 * 60 * 60 * 1000;
  el.textContent = 'Jobright last updated: ' + last.toLocaleString() + (stale ? ' · Update overdue — check GitHub Actions' : '');
}
