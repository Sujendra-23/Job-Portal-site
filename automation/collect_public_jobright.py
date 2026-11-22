"""Collect factual leads from Jobright's public GitHub lists, not its private website.

Only title/company/location/work model/date-label/links are read. No job description,
account data, Jobright web page, private API, or employer site is downloaded.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

try:
    from .sync_jobs import ROOT, LEGACY, ImportErrorSafe, atomic_json, classify, load_json, norm
except ImportError:
    from sync_jobs import ROOT, LEGACY, ImportErrorSafe, atomic_json, classify, load_json, norm

SOURCES = (
    ('2026-Software-Engineer-New-Grad', 'full-time'),
    ('2026-Software-Engineer-Internship', 'internship'),
)
US_STATES = set('AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY'.split())
LINK = re.compile(r'\[([^\]]+)\]\((https?://[^\s]+)\)')

def clean(cell):
    return re.sub(r'<[^>]*>', '', cell.replace('**', '').replace('\\|', '|')).strip()

def read_source(repo):
    # Fixed public GitHub URLs; never accepts an arbitrary source or credential.
    address = f'https://raw.githubusercontent.com/jobright-ai/{repo}/master/README.md'
    result = subprocess.run(['curl', '--fail', '--silent', '--show-error', '--proto', '=https',
                             '--max-time', '30', '--max-filesize', '2097152', '--retry', '2',
                             '--retry-delay', '2', address], capture_output=True, text=True)
    if result.returncode:
        raise ImportErrorSafe('Public Jobright list could not be downloaded; existing data retained')
    if len(result.stdout.encode()) > 2 * 1024 * 1024:
        raise ImportErrorSafe('Public list exceeds size limit')
    return result.stdout

def parse_table(markdown):
    company = None
    rows = []
    if '| Company | Job Title | Location | Work Model | Date Posted |' not in markdown:
        raise ImportErrorSafe('Public list layout changed; existing data retained')
    for line in markdown.splitlines():
        if not line.startswith('|'):
            continue
        cells = [clean(c) for c in re.split(r'(?<!\\)\|', line)[1:-1]]
        if len(cells) != 5:
            if 'jobright.ai/jobs/info/' in line:
                raise ImportErrorSafe('Malformed public job row; existing data retained')
            continue
        if cells[0] == 'Company' or all(re.fullmatch(r'[- :]+', c) for c in cells):
            continue
        if cells[0] == '↳':
            if not company:
                raise ImportErrorSafe('Public list company continuation has no company')
        else:
            match = LINK.fullmatch(cells[0])
            company = match.group(1).strip() if match else cells[0]
        match = LINK.fullmatch(cells[1])
        if not match:
            continue
        title, source = match.groups()
        parts = urlsplit(source)
        if parts.scheme != 'https' or parts.hostname != 'jobright.ai' or not re.fullmatch(r'/jobs/info/[a-zA-Z0-9_-]+', parts.path):
            raise ImportErrorSafe('Unexpected job attribution link in public list')
        rows.append(dict(company=company, title=title.strip(), location=cells[2],
                         work_arrangement=cells[3], source_date_label=cells[4],
                         source_url=urlunsplit((parts.scheme, parts.netloc, parts.path, '', '')),
                         source_id=parts.path.rsplit('/', 1)[-1]))
    if not rows:
        raise ImportErrorSafe('Public job table is empty or unparseable; existing data retained')
    return rows

def is_us(location):
    if re.search(r'\b(?:united states(?: of america)?|usa|us)\b|(?<!\w)u\.s\.(?!\w)', location, re.I):
        return True
    if re.search(r'\bUS\b', location):
        return True
    return bool(re.search(r',\s*('+'|'.join(sorted(US_STATES))+r')(?:\s+\d{5})?\s*$', location))

def dedupe_keys(j):
    location = re.sub(r'\b(?:united states(?: of america)?|usa)\b|\((?:hybrid|onsite|remote|on site)\)', '', j.get('location', ''), flags=re.I)
    company = re.sub(r'\b(?:incorporated|inc|llc|ltd|corporation|corp)\b', '', norm(j.get('company')))
    company = norm(company)
    company = {'palantir technologies':'palantir', 'hewlett packard enterprise':'hpe'}.get(company, company)
    locations = {norm(location)} | {norm(part) for part in re.split(r';|/|\bor\b', location)}
    keys = {('role', company, norm(j.get('title')), place) for place in locations if place}
    if j.get('source_id'):
        keys.add(('source', j['source_id']))
    for field in ('source_url', 'application_link'):
        u = j.get(field) or ''
        p = urlsplit(u)
        if p.hostname == 'jobright.ai' and p.path.startswith('/jobs/info/'):
            keys.add(('source', p.path.rstrip('/').rsplit('/', 1)[-1]))
    return keys

def collect(root=ROOT, fetch=read_source, now=None):
    now = now or datetime.now(timezone.utc)
    checked = now.isoformat()
    inputs = [(repo, kind, parse_table(fetch(repo))) for repo, kind in SOURCES]
    # Parse both sources and all saved files before writing anything.
    existing = load_json(root / 'roles_jobright_public.json', [])
    if not isinstance(existing, list) or any(not isinstance(j, dict) for j in existing):
        raise ImportErrorSafe('Saved public leads are invalid')
    blocked = set()
    for filename in [f'roles_{name}.json' for name in LEGACY] + ['roles_unverified.json', 'roles_jobright.json']:
        data = load_json(root / filename)
        if not isinstance(data, list) or any(not isinstance(j, dict) for j in data):
            raise ImportErrorSafe('Existing portal records are invalid')
        for j in data:
            blocked.update(dedupe_keys(j))
    positions = {}
    for i, j in enumerate(existing):
        for key in dedupe_keys(j):
            positions[key] = i
    counts = Counter(inspected=0, matched=0, added=0, updated=0, duplicates=0)
    rejected = Counter()
    for repo, kind, rows in inputs:
        for raw in rows:
            counts['inspected'] += 1
            j = dict(raw, country='US' if is_us(raw['location']) else 'unknown',
                     employment_type=kind, description='', cpt='unknown', opt='unknown', sponsorship='unknown')
            # Public lists do not contain employer eligibility/experience evidence.
            # Restrictive titles are excluded; the remainder stays unverified.
            category, reason = classify(j)
            if re.search(r'\b(?:defense|government|usg|clearance|ts/sci|citizen|full.scope polygraph)\b', j['title'], re.I):
                category, reason = None, 'restricted_title'
            if not category:
                rejected[reason] += 1
                continue
            counts['matched'] += 1
            keys = dedupe_keys(j)
            found = {positions[k] for k in keys if k in positions}
            if len(found) > 1:
                raise ImportErrorSafe('Public lead identifiers conflict; existing data retained')
            if keys & blocked:
                counts['duplicates'] += 1
                for i in found:
                    existing[i] = dict(existing[i], filter_status='excluded', filter_reason='present_in_existing_portal')
                continue
            j.update(automation_source='jobright-public-github', source='Jobright public GitHub list',
                     public_dataset_url=f'https://github.com/jobright-ai/{repo}',
                     category=category, status='unknown', filter_status='included',
                     application_link=None, posting_date=None, last_checked=checked,
                     description='Unverified lead from Jobright’s public GitHub list. '
                     'The employer posting, degree requirements, experience, CPT/OPT/H-1B eligibility, '
                     'and start-date availability have not been verified. '
                     f'The source lists its date as “{j["source_date_label"]}”; this is not a verified employer posting date. '
                     'Open the Jobright source to review the listing and find the employer’s application page.')
            if found:
                position = found.pop()
                old = existing[position]
                for field in ('id', 'date_added', 'first_discovered'):
                    j[field] = old[field]
                counts['updated' if old != j else 'duplicates'] += 1
                existing[position] = j
            else:
                position = len(existing)
                j.update(id=hashlib.sha256(('public:'+j['source_id']).encode()).hexdigest()[:24],
                         date_added=now.date().isoformat(), first_discovered=checked)
                existing.append(j)
                counts['added'] += 1
            for key in keys:
                positions[key] = position
    report = dict(status='success', last_success=checked, source_type='Jobright public GitHub lists',
                  sources=[f'https://github.com/jobright-ai/{repo}' for repo, _ in SOURCES],
                  **counts, rejected=dict(rejected),
                  visible_public_leads=sum(j.get('filter_status') != 'excluded' for j in existing))
    atomic_json(root / 'roles_jobright_public.json', existing)
    atomic_json(root / 'jobright_public_sync.json', report)
    return report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(collect(args.root)))
    except Exception as e:
        print(json.dumps({'status':'failed', 'error':str(e) if isinstance(e, ImportErrorSafe) else 'Public collection failed; existing data retained'}), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
