# Maintaining this portal

- Fetch the current main branch before editing. Never replace index.html with a cached copy from before the Jobright integration.
- Routine job sweeps should edit only their designated role JSON files. Preserve automation/, .github/workflows/, the Jobright data files, and the page integration.
- Keep public Jobright leads in the Unverified Leads tab until employer requirements are verified. Do not infer sponsorship from employer history or silently promote unknown eligibility.
- Run `python3 -m unittest discover -s tests` and `node --test tests/portal.test.cjs` before pushing page or automation changes.
- The workflow repairs only the exact known pre-integration page. Do not weaken this hash check or overwrite unrecognized owner HTML. Update the repair patch and its expected hash deliberately if the canonical repair needs to change.
- Preserve owner-maintained job records, contacts, resume links and application tracking. Never force-push collection results.
