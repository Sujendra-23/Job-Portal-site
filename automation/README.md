# Personalized Jobright import setup and access

**Public collection is now active separately.** See [PUBLIC_COLLECTION.md](PUBLIC_COLLECTION.md). The authorization flag and feed requirements in this guide apply to personalized/authorized exports, not Jobright’s public GitHub lists.

Implemented against `Sujendra-23/Job-Portal-site`, base commit `15620be7173d2eb7fc89effd03919724cc972de7`.

Deployment status (November 22, 2026): the tested integration commit `59c0c26` is merged into `main` and deployed to the existing site. [GitHub Actions run 45071787233](https://github.com/Sujendra-23/Job-Portal-site/actions/runs/45071787233) completed tests, Pages artifact build, and deployment successfully. Import and data-commit steps were skipped. Repository variable `JOBRIGHT_IMPORT_AUTHORIZED` is explicitly set to `false`; personalized collection remains disabled pending authorization and a supported feed.

The GitHub account `shruthib18122001-commits` now has repository write access. Pages retains its existing `main`-branch publishing source. An API attempt to select the workflow publisher returned HTTP 404 while read access to Pages succeeded, so a repository owner should select **Settings → Pages → Build and deployment → Source → GitHub Actions** to make the new workflow the sole publisher. This setting change is outstanding; the existing website and the custom workflow deployment both succeeded.

## Source permission is required

As checked November 22, 2026, Jobright's [robots file](https://jobright.ai/robots.txt) disallows `/jobs/recommend` and `/api`. Its [Terms of Service](https://jobright.ai/legal/service), sections 3 and 9, prohibit automated access and data gathering and require written permission for systematic retrieval. Public republication also needs to be covered by the permission. An account login alone does not establish this permission.

This implementation does not scrape Jobright or use private APIs, session cookies, passwords, or browser storage. It accepts a normalized export supplied through a permitted channel. No official export/API has been established for this account; the JSON format below is this integration's contract, not a claim about an existing Jobright API. An automated upstream exporter must be authorized and arranged before unattended collection is possible. If Jobright provides a different supported payload, its adapter still needs to be implemented against that documented format.

Ask Jobright for written permission to collect the specified listings every three hours and republish job information, plus a supported export/feed method. Their terms list `legal@jobright.ai` as a contact. No request has been sent on your behalf. Do not route an unauthorized scraper through a different host to feed this importer. Local exports also require permission for collection/republication.

## Applying the delivered patch

From a checkout of this existing repository at the base commit, apply the supplied patch. The check refuses conflicting local changes:

```sh
git apply --check /absolute/path/jobright-automation.patch
git apply /absolute/path/jobright-automation.patch
```

Run the verification commands below, review the changes, then commit and push as the repository owner or authorized collaborator. The patch was checked against a clean checkout of the base commit. It includes all new source files and workflow configuration.

## GitHub activation

1. Obtain repository write access (including adding workflow files). A scoped credential, if used, needs Contents and Workflows write for this repository only. Do not put credentials in chat or the repository. Applying the patch as the repository owner also works.
2. Review and merge the changes into `main`. No existing job JSON, contacts, resumes, or company lists are modified. Initial `roles_jobright.json` is empty; sample jobs exist only in test code and disposable test directories.
3. In repository Settings → Pages, select **GitHub Actions** as the publishing source. The workflow stages the existing static site. Confirm there is no separate deployment workflow in the repository before enabling a competing publisher.
4. Enable GitHub Actions and allow the workflow's `GITHUB_TOKEN` to write repository contents. Allow `github-pages` deployments from `main`. Branch rules that disallow bot writes require a separately approved PR-based update policy; the workflow fails rather than bypassing branch rules.
5. After source authorization, set these repository settings:

| Setting | Type | Value |
|---|---|---|
| `JOBRIGHT_IMPORT_AUTHORIZED` | Actions variable | `true` only when collection **and public republication** are permitted |
| `JOBRIGHT_FEED_HOST` | Actions variable | Exact hostname of the approved export host |
| `JOBRIGHT_FEED_URL` | Actions secret | Final HTTPS URL returning the normalized JSON below |
| `JOBRIGHT_FEED_TOKEN` | Actions secret, optional | Bearer token supported by that export service |

The workflow runs at **00:17, 03:17, 06:17, 09:17, 12:17, 15:17, 18:17, 21:17 UTC**, plus manual dispatch. GitHub schedules can be delayed and public-repository schedules can be disabled after 60 days without activity. See [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule). This schedule is UTC and is unaffected by daylight saving changes.

A normal push runs tests, collects public GitHub leads, and deploys the saved site. Scheduled, manual and push runs now collect the public GitHub lists. The separate private import step runs only when JOBRIGHT_IMPORT_AUTHORIZED is true; while false it is skipped. An explicitly enabled but invalid private feed fails the run and preserves the current deployment. Imported JSON is committed with `GITHUB_TOKEN`, then deployed **in the same run** because token-created pushes do not normally trigger another workflow. Deployment uses `pages: write` and `id-token: write` only in the deployment job. No personal GitHub token is required in Actions. See [GitHub Pages workflow requirements](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).

6. Run **Jobright authorized import and Pages** manually in Actions. Check tests, import counts, commit, artifact upload and deployment. Confirm new real listings, source links, eligibility evidence and timestamp on the live site. Website deployment is verified. Production import verification remains outstanding until authorization and a supported feed are provided.

## Normalized feed contract, version 1

This is a synthetic **documentation example**, never production data:

```json
{
  "schema_version": 1,
  "generated_at": "2026-11-22T20:00:00Z",
  "jobs": [{
    "source_id": "example-job-id",
    "company": "Example employer",
    "title": "Software Engineer, New Grad 2027",
    "location": "Austin, TX",
    "country": "US",
    "employment_type": "full-time",
    "description": "Plain text of the permitted posting",
    "application_link": "https://careers.example.com/jobs/123",
    "source_url": "https://jobright.ai/jobs/info/example-job-id",
    "checked_at": "2026-11-22T20:00:00Z",
    "posting_date": null,
    "start_date": null,
    "min_experience_years": 2,
    "required_experience": "0–3 years",
    "qualifications": null,
    "salary": null,
    "degree": null,
    "work_arrangement": "hybrid",
    "term": null,
    "sponsorship": "unknown",
    "cpt": "unknown",
    "opt": "unknown",
    "eligibility_evidence": null,
    "eligibility_source_url": null,
    "sponsorship_history": null,
    "status": "unknown"
  }]
}
```

Required strings: company, title, location, country, employment_type, description, application_link, source_url, checked_at. Required envelope: schema_version, generated_at, jobs. Source attribution must use a Jobright `/jobs/info/` link. Application links must be HTTPS employer/ATS posting links; common aggregators are rejected. URL syntax is validated; availability and employer ownership must be verified by the authorized upstream source. The importer does not follow application links or claim to validate every employer domain.

Use employment_type `full-time`, `internship`, or `co-op`; country `US`, `USA`, or `United States`. Unknown or other employment types are excluded. For internships/co-ops, provide term `Spring 2027`/`Winter 2027`, an explicit matching title, or a start_date January–May 2027. A graduation date in the description is not treated as internship timing. Missing dates remain null. `status` is active/expired/unknown, with unknown as default; active must reflect actual upstream verification. `checked_at` is the record's source refresh time, not evidence that this importer visited the employer. It and generated_at must have timezones and be no older than 24 hours.

For CPT/OPT/H-1B fields use supported/restricted/unknown. Any supported or restricted value requires a current posting quotation in eligibility_evidence and its HTTPS eligibility_source_url. Historical sponsorship belongs only in sponsorship_history; it never upgrades current eligibility. The importer enforces the presence of evidence; it cannot prove that the upstream quotation is truthful. Do not insert private profile, resume, or account information in posting text. Unrecognized fields are dropped before publishing.

Full-time matches require an explicit 2027 title or early-career evidence (new grad, associate, Engineer I/II, or structured minimum experience ≤3 years). An undated early-career role does not guarantee a 2027 start; confirm availability with the employer. Known full-time starts before May 2027 are excluded for the stated graduation target. Senior/staff/lead roles, experience over three years, non-US roles and restrictive authorization language are excluded. Text matching is conservative and cannot replace reading the original posting; keep structured experience and eligibility fields accurate.

## Behavior and preservation

- Existing job data, contacts, resume files, resume keys and browser application tracking are preserved.
- New records use roles_jobright.json and route into existing full-time/internship tabs. No new tab or redesign is introduced.
- Deduplication uses Jobright ID, canonical application URL, or normalized company/title/location, including existing verified role files. Tracking parameters are ignored while job-identifying query parameters are retained. Unverified leads stay isolated.
- Existing legacy duplicates are left unchanged. New imports already present in a legacy file are skipped; legacy entries are never overwritten. Matching cannot resolve all distinct URL/company aliases automatically.
- Existing automated records preserve their first-discovered date and ID when updated. Expired or newly excluded automated jobs remain in saved history but are hidden in the portal. Absent listings are not treated as expired because feeds may be partial.
- Newest discovery date remains the primary grouping; within each date current posting-supported CPT/OPT/H-1B signals rank higher. Historical employer information is shown separately.
- A separate eligibility filter and last-success timestamp are added. The timestamp shows overdue after seven hours; workflow failures remain visible in Actions. Legacy records without structured evidence appear as eligibility unknown.
- The feed has a 10 MiB/10,000-record limit, bounded retries, a timeout, exact host matching, public-address checks, HTTPS only, and no redirects. Jobright hosts are refused by the remote importer, even with the authorization flag. If Jobright supplies an official authorized endpoint on its own domain, adapt this restriction only to that documented endpoint after reviewing its permission.
- Errors do not replace saved listings or last-success metadata. Empty successful feeds preserve listings. Status and data files are individually replaced atomically; they are committed and deployed together by Actions after successful completion.
- The Pages build includes known public JSON and static assets only, excluding exports and source tooling. Keep local export files outside the repository, or in ignored exports/; never add them as public site assets.

## Local use and verification

Python 3.12+ and Node.js are sufficient; no third-party Python dependencies.

```sh
python3 -m unittest discover -s tests -v
node --test tests/portal.test.cjs
python3 automation/build_pages.py
python3 -m http.server 8765 --directory _site
```

After authorization, a local normalized export can be tested without any Jobright login:

```sh
JOBRIGHT_IMPORT_AUTHORIZED=true python3 automation/sync_jobs.py --input /absolute/path/outside/repository/export.json
```

For safe experiments, use a disposable clone. A successful import modifies roles_jobright.json and jobright_sync.json in the selected root. The tests use temporary folders and synthetic examples; they do not publish samples.

Validation completed locally: 32 Python checks and six JavaScript checks; full CLI→filtered JSON→Pages artifact integration; failed-import preservation; browser confirmation of imported full-time/co-op routing, eligibility filtering, duplicate suppression, attribution, and timestamp. Baseline preview retained all 207 existing full-time roles. Test listings were removed from the preview afterward. GitHub Actions execution and live deployment succeeded after repository write access was granted. Personalized remote collection remains unverified and disabled because no authorized feed has been established. Public GitHub collection is documented separately and does not require those feed secrets.

## Troubleshooting

- **403 pushing changes:** authenticate as an owner/collaborator with repository write access. For workflow files, a scoped token also needs Workflows write.
- **Import disabled:** authorization flag is absent/false. Obtain actual source and republication permission before setting it.
- **Feed request 401/403:** renew the export token in Actions Secrets; never upload Jobright cookies as a workaround.
- **Redirect refused:** configure the final HTTPS export URL, keeping the exact host allowlist updated.
- **Stale export:** upstream feed generation or record checks have stopped. Repair that service; do not simply change timestamps on old data.
- **Invalid export:** check the contract, timestamp formats, nulls, status enums, and evidence fields. HTML login pages are rejected without being logged.
- **No new matches:** inspect rejection counts in the Actions output. The workflow does not widen filters automatically.
- **Bot commit rejected:** branch protection or Contents permissions prohibit writes. Keep protections intact and agree a suitable update mechanism with the owner.
- **Deployment rejected:** select Actions as the Pages source, verify github-pages environment branch rules, and review the deployment log.

Rollback: revert the integration commit using Git, then redeploy the prior site. Existing job data files are unchanged by this integration. Reverting roles_jobright.json/jobright_sync.json to a known successful commit rolls back imported state independently.
