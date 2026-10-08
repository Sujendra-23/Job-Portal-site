# Job Portal site

Static job portal (GitHub Pages), six tabs.

## Tabs and data files

| Tab | File | Maintained by |
|---|---|---|
| Top Companies | `roles_top.json` | Muse (this agent) — 118 top companies |
| Mid-size & Established | `roles_midsize.json` | Other agent (Claude) |
| Growth Stage | `roles_growth.json` | Other agent (Claude) |
| Startup Stage | `roles_startup.json` | Other agent (Claude) |
| LinkedIn Hiring Posts | `roles_linkedin_posts.json` | Muse — organic hiring posts only |
| Spring/Winter 2027 Internships | _(computed)_ | Automatic — aggregates intern/co-op roles from all five role files |
| Emails | `emails.json` | Other agent (Claude) |

Shared files (do not restructure):
- `index.html` — the portal page. Do not edit except via the repo owner.
- `top_companies.json` — the 118 top-company names. Read-only for tab filtering.
- `resumes.json` — tailored resume links both agents may add to (see below).

## Role file format (`roles_*.json`)

Array of role objects:

```json
[
  {
    "company": "Acme",
    "title": "Software Engineer, New Grad 2027",
    "location": "San Francisco, CA",
    "posting_date": "2026-10-07",
    "application_link": "https://careers.acme.com/jobs/123",
    "description": "<p>Full HTML or plain text…</p>",
    "degree": "BS/MS",
    "source": "portal_sweep_2026-10-07"
  }
]
```

- `posting_date` must be `YYYY-MM-DD` (used for date-wise sections).
- `application_link` must be the employer's own posting URL, never an aggregator link.
- Dedupe rule: the same opening must appear in only ONE tab. If a career-portal
  listing and a LinkedIn hiring post describe the same opening, it lives in the
  company-tier tab, never in LinkedIn Hiring Posts.
- Intern routing: any role whose title contains intern/internship/co-op is shown
  ONLY in the Spring/Winter 2027 Internships tab, never in the tier tabs — the page
  routes this automatically, so just put roles in the tier files regardless of type.

## `resumes.json` format (both agents)

```json
{
  "Company||Job Title": {
    "sujendra": "https://link-to-sujendras-tailored-resume.pdf",
    "shruthi": "https://link-to-shruthis-tailored-resume.pdf"
  }
}
```

- Key must match `Company||Title` exactly as in the role files.
- Either or both of `sujendra` / `shruthi` may be present.
- Only add resume links. Never edit role files to update resumes.

## `emails.json` format (other agent)

```json
[
  { "company": "Acme", "name": "Jane Doe", "title": "Recruiter", "email": "jane@acme.com" }
]
```

## Ownership boundaries

- Muse never edits `roles_midsize.json`, `roles_growth.json`, `roles_startup.json`, `emails.json`.
- The other agent never edits `roles_top.json`, `roles_linkedin_posts.json`, `top_companies.json`.
- Both may add entries to `resumes.json`.
