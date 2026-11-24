# Maintaining this portal

- Fetch the current main branch before editing. Never replace index.html with a cached copy from before the Jobright integration.
- Routine job sweeps should edit only their designated role JSON files. Preserve automation/, .github/workflows/, the Jobright data files, and the page integration.
- Route collected public Jobright full-time roles into Full-Time 2027 and Spring 2027 internships/co-ops into Spring/Winter 2027, as explicitly requested by the owner. Tab placement does not verify a posting: retain source attribution, unknown eligibility, and employer-verification labels. Do not infer sponsorship from employer history.
- Run `python3 -m unittest discover -s tests` and `node --test tests/portal.test.cjs` before pushing page or automation changes.
- The workflow repairs only the exact known pre-integration page. Do not weaken this hash check or overwrite unrecognized owner HTML. Update the repair patch and its expected hash deliberately if the canonical repair needs to change.
- Preserve owner-maintained job records, contacts, resume links and application tracking. Never force-push collection results.
