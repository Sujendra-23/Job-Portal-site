# Active public Jobright collection

The portal now collects factual leads from Jobright's own public GitHub lists every three hours. No Jobright login, account cookies, paid service, or new secret is needed for this public mode.

Sources:

- [Jobright software engineering new-grad list](https://github.com/jobright-ai/2026-Software-Engineer-New-Grad)
- [Jobright software engineering internship list](https://github.com/jobright-ai/2026-Software-Engineer-Internship)

Although their names contain 2026, both lists currently include 2027 opportunities and were being updated in November 2026. The collector filters actual titles, locations and terms instead of treating the repository name as the hiring year. Jobright describes its new-grad repository as a resource for discovering and sharing opportunities. The collector reads only the publisher's factual table metadata: company, title, location, work model, source date label and Jobright detail URL. It does not copy full descriptions, repository artwork, or private account content, and it preserves source attribution.

## What appears on the portal

New public matches are saved to `roles_jobright_public.json` and displayed only in **Unverified Leads**. Existing verified job files, contacts, resume links and application tracking stay intact.

- US locations only, including explicitly US remote listings.
- Full-time 2027 titles or suitable early-career titles. An undated early-career title is a lead, not confirmation that the role accepts a May 2027 graduate.
- Internship/co-op titles must explicitly identify Spring/Winter 2027; unknown terms and Summer/Fall internships are excluded.
- Senior/lead roles and titles explicitly referencing defense, government, citizenship or clearance are excluded.
- Source IDs and normalized company/title/location prevent repeated imports. Known company aliases and multi-city locations are supported. Existing verified and unverified files are checked before adding a lead. Not all employer aliases/requisitions can be resolved from metadata alone.
- Eligibility, required experience, degree, employer posting status and direct employer application URLs are **unknown**, because the public tables do not provide this evidence. No sponsor ranking is invented. Public matches cannot be promoted to verified jobs without employer verification.
- Public listings have **View listing** links to Jobright, rather than fabricated employer Apply links.
- The source's month/day label is retained in the explanation; it is not promoted to a verified employer posting date.
- First discovery dates are preserved. Records that disappear from these rolling lists remain unverified history; disappearance is not treated as proof of expiration.
- If an existing portal file later contains a matching public lead, the stored public copy is hidden, retaining its history.

This is a public subset. It does **not** reproduce the personalized `/jobs/recommend` results, and it cannot discover every Jobright posting. Public-source refresh time is shown separately from job posting or employer verification time.

## Three-hour automation

`.github/workflows/jobright-sync.yml` runs at minute 17 every three hours UTC, on pushes to main, and on manual dispatch. It:

1. Runs Python and JavaScript checks.
2. Fetches the two fixed public README URLs with bounded retries, HTTPS, time/size limits, and no credentials.
3. Parses both tables before modifying any data. Invalid, empty or inaccessible tables fail the run and preserve the previous published data.
4. Filters and merges leads, preserving prior discovery dates and existing portal records.
5. Commits only collection JSON, then builds and deploys the same saved data to Pages.

A failed fetch stops the run before publication. Git push conflicts or insufficient bot write permissions also stop deployment, keeping the previous site available. GitHub may delay scheduled runs; the page shows an overdue message if the last successful public collection is older than seven hours. Public GitHub sources may update less often than the three-hour polling interval, so a successful poll need not discover a new job.

The existing repository `GITHUB_TOKEN` uses scoped workflow `contents: write` for data commits. The Pages deployment job separately requests `pages: write` and `id-token: write`. A bot-created commit is deployed in the same workflow, without relying on another push-triggered run.

## Personalized recommendation import remains off

`JOBRIGHT_IMPORT_AUTHORIZED=false` continues to guard the separate private/feed importer. That setting does not disable public GitHub collection. The private step now skips cleanly while disabled, allowing public collection and publication to proceed.

Jobright's [website robots directives](https://jobright.ai/robots.txt) disallow recommendations/API routes, and its [website terms](https://jobright.ai/legal/service) restrict automated website extraction. This implementation never fetches the Jobright website, private APIs, employer pages, or account recommendations. A supported, authorized personalized feed still needs to be established before enabling that separate importer. The old setup guide's authorization instructions apply to that private mode, not to the public GitHub collector.

## Verification

Run:

```sh
python3 -m unittest discover -s tests -v
node --test tests/portal.test.cjs
python3 automation/collect_public_jobright.py
python3 automation/build_pages.py
```

The first real collection inspected 776 public table entries and saved 117 new leads after filtering and duplicate checks, including five explicitly marked Spring 2027 internship/co-op leads. No synthetic examples were added to production. All 47 Python checks and eight JavaScript checks passed locally. Browser inspection confirmed public leads, source links, honest eligibility labels, the unverified banner, search, and the existing 207 full-time roles.

`jobright_public_sync.json` records the current source URLs, inspected/matched/added/updated/duplicate counts, rejection reasons and last-success time. Use **Actions → Jobright collection and Pages → Run workflow** to verify an immediate repeat without waiting for the next schedule. Repeated collection should retain the same IDs and first-discovery timestamps and add zero duplicates.

## Concurrent edits and page integration

The automatic save step now uses `automation/publish_collected_data.py`. It commits only the four collection JSON files, fetches the latest main, incorporates compatible intervening commits with a rebase, validates the resulting publication snapshot, and attempts a normal push. If another edit arrives during that interval it refreshes and retries, up to three attempts. It never force-pushes or overwrites conflicting owner changes. A conflict or failed validation stops publication safely.

The page must retain its automation helper script, Jobright entries in ROLE_FILES, public-lead routing, source-link rendering, and status/eligibility controls. Replacing index.html with a copy from before the integration removes those connections; update the current version instead. Tests explicitly check these connections and stop the collector workflow if they are removed. The separate legacy Pages publisher can still publish an owner commit even when these integration tests fail.

Repair verification includes 53 Python checks and nine JavaScript checks, including simulated competing edits, conflict preservation, bounded retries, and refusing unrelated staged changes.

## Scheduled recovery and live verification

The primary collector remains scheduled at minute 17 every three hours UTC. A separate `jobright-recovery.yml` workflow checks hourly at minute 47. It requests a fresh primary run when the last successful public collection is more than 3.5 hours old, or the latest primary workflow failed and its one-hour retry cooldown has passed. Healthy collections are left alone; an active/queued collection prevents a second dispatch. A manually disabled workflow is reported as requiring owner action rather than being silently re-enabled.

The recovery workflow uses the repository's built-in GITHUB_TOKEN with Actions write permission solely to dispatch the existing collector. It does not publish the website, edit job data, send email, create issues, or require a personal token. Manual recovery is available from Actions → Jobright recovery check → Run workflow; selecting `recover_now` requests an immediate collection if none is already active. All workflows have bounded job timeouts, and the recovery checker has a distinct concurrency group.

After each deployment, `verify_live_site.py` checks the actual public page, the public collection report, and the public lead JSON. It requires the integration hooks, a successful report at least as recent as the deployed snapshot, consistent visible-record counts, and unique lead IDs. It retries briefly for publication propagation, then marks the run failed if the live site is stale or missing its integration. The recovery checker can detect that failed primary run and request another attempt after cooldown.

For these safeguards to control publication, the repository owner must select Settings → Pages → Build and deployment → Source → GitHub Actions. If legacy branch publishing stays enabled, it can still publish an index.html replacement without waiting for the integration tests. This application integration cannot prevent an owner from deliberately replacing or deleting its files; maintain the current source and run checks when editing it.

GitHub schedules and upstream availability remain external dependencies. The recovery check improves resilience but cannot guarantee exact wall-clock execution during GitHub outages. The portal displays the last successful collection time and an overdue indication, and failed runs remain visible in Actions. No third-party monitoring or notification subscription is configured.

Reliability validation includes 74 Python checks and nine JavaScript checks: overdue/missing/future timestamp handling, active-run suppression, cooldowns, failed-deployment recovery, dispatch targeting, disabled-workflow handling, stale live pages, inconsistent data counts, duplicate IDs, and the previously verified concurrent-edit cases.
