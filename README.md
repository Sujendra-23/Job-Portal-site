# Job Portal site

Static job portal (GitHub Pages). Files:

- `index.html` — the portal page. Tabs: All openings / Top companies. Roles grouped by posting date.
- `roles.json` — job data, refreshed automatically by an agent every 3 hours. **Do not edit by hand.**
- `top_companies.json` — company names shown under the "Top companies" tab. Safe to edit.
- `resumes.json` — tailored resume links. **This is the only file another agent should edit.**

## resumes.json format

```json
{
  "Company||Job Title": {
    "sujendra": "https://link-to-sujendras-tailored-resume.pdf",
    "shruthi": "https://link-to-shruthis-tailored-resume.pdf"
  }
}
```

Rules:
- The key must match `Company||Title` exactly as written in `roles.json`.
- Either or both of `sujendra` / `shruthi` may be present.
- Never edit `roles.json`, `index.html`, or any other file when updating resumes.
