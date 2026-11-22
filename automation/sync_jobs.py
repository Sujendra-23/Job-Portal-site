"""Import an authorized, normalized Jobright export; never scrape recommendations."""
import argparse
from collections import Counter
from datetime import date, datetime, timezone, timedelta
import hashlib
import html
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ('top', 'midsize', 'growth', 'startup', 'linkedin_posts')
MAX_BYTES = 10 * 1024 * 1024

class ImportErrorSafe(ValueError):
    pass

def norm(value):
    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').casefold()).strip()

def plain(value):
    return html.unescape(re.sub(r'<[^>]+>', ' ', str(value or '')))

def url(value):
    if not isinstance(value, str):
        raise ImportErrorSafe('Missing URL')
    p = urlsplit(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ImportErrorSafe('URLs must use HTTPS without embedded credentials')
    return value

def canonical(value):
    p = urlsplit(url(value))
    query = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ('source', 'ref', 'referrer', 'trackingid')]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip('/'), urlencode(sorted(query)), ''))

def identities(job):
    keys = {('role', norm(job.get('company')), norm(job.get('title')), norm(job.get('location')))}
    try:
        keys.add(('url', canonical(job.get('application_link'))))
    except (ValueError, TypeError):
        pass
    if job.get('source_id'):
        keys.add(('source', str(job['source_id'])))
    return keys

def timestamp(value):
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError()
        return dt.astimezone(timezone.utc)
    except (ValueError, AttributeError, TypeError):
        raise ImportErrorSafe('Expected timezone-aware ISO timestamp') from None

def iso_date(value):
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except (ValueError, TypeError):
        raise ImportErrorSafe('Expected ISO calendar date') from None

def fresh(value, now):
    dt = timestamp(value)
    if dt > now + timedelta(minutes=5) or dt < now - timedelta(hours=24):
        raise ImportErrorSafe('Feed or record is stale (24-hour limit) or future dated')
    return dt.isoformat()

def validate(raw, now):
    if not isinstance(raw, dict):
        raise ImportErrorSafe('Job must be an object')
    for field in ('company', 'title', 'location', 'description', 'country', 'employment_type'):
        if not isinstance(raw.get(field), str) or not raw[field].strip():
            raise ImportErrorSafe('Missing required job field: ' + field)
    j = {k: plain(raw[k]).strip() for k in ('company', 'title', 'location', 'description', 'country', 'employment_type')}
    j['application_link'] = url(raw.get('application_link'))
    host = urlsplit(j['application_link']).hostname
    if any(host == h or host.endswith('.' + h) for h in ('jobright.ai', 'linkedin.com', 'indeed.com', 'glassdoor.com', 'ziprecruiter.com')):
        raise ImportErrorSafe('Application link must be an employer/ATS posting')
    j['source_url'] = url(raw.get('source_url'))
    if urlsplit(j['source_url']).hostname != 'jobright.ai' or not urlsplit(j['source_url']).path.startswith('/jobs/info/'):
        raise ImportErrorSafe('Expected a Jobright job detail attribution URL')
    j['source_id'] = str(raw.get('source_id') or urlsplit(j['source_url']).path.rstrip('/').split('/')[-1])
    j['last_checked'] = fresh(raw.get('checked_at'), now)
    j['posting_date'] = iso_date(raw.get('posting_date'))
    j['start_date'] = iso_date(raw.get('start_date'))
    if j['posting_date'] and j['posting_date'] > now.date().isoformat():
        raise ImportErrorSafe('Posting date is in the future')
    for k in ('salary', 'degree', 'qualifications', 'required_experience', 'work_arrangement', 'term', 'sponsorship_history'):
        value = raw.get(k)
        if value is not None and not isinstance(value, str):
            raise ImportErrorSafe('Optional text field has invalid type: ' + k)
        j[k] = plain(value).strip() if value else None
    for k in ('status', 'sponsorship', 'cpt', 'opt'):
        default = 'unknown'
        allowed = ('active', 'expired', 'unknown') if k == 'status' else ('supported', 'restricted', 'unknown')
        if raw.get(k, default) not in allowed:
            raise ImportErrorSafe('Invalid status field: ' + k)
        j[k] = raw.get(k, default)
    evidence = raw.get('eligibility_evidence')
    if evidence is not None and not isinstance(evidence, str):
        raise ImportErrorSafe('Eligibility evidence must be text')
    j['eligibility_evidence'] = plain(evidence).strip() if evidence else None
    if any(j[k] != 'unknown' for k in ('sponsorship', 'cpt', 'opt')):
        if not j['eligibility_evidence'] or not raw.get('eligibility_source_url'):
            raise ImportErrorSafe('Eligibility claims require posting evidence and its URL')
        j['eligibility_source_url'] = url(raw['eligibility_source_url'])
    else:
        j['eligibility_source_url'] = None
    minimum = raw.get('min_experience_years')
    if minimum is not None and (type(minimum) not in (int, float) or not 0 <= minimum <= 60):
        raise ImportErrorSafe('Invalid minimum experience')
    j['min_experience_years'] = minimum
    j['automation_source'] = 'jobright-authorized-feed'
    j['source'] = 'Jobright (authorized export)'
    j['status'] = raw.get('status', 'unknown')
    return j

def classify(j):
    title = j['title'].lower()
    text = ' '.join(str(j.get(k) or '') for k in ('title', 'description', 'qualifications', 'required_experience'))
    text = text.lower().replace('’', "'")
    if norm(j['country']) not in ('us', 'usa', 'united states', 'united states of america'):
        return None, 'outside_us'
    if re.search(r'\b(senior|sr\.?|staff|principal|lead|manager|director|iii|iv)\b', title):
        return None, 'seniority'
    if not re.search(r'\bsoftware (?:engineer(?:ing)?|develop\w*)|\b(?:back[ -]?end|front[ -]?end|full[ -]?stack) (?:software )?(?:engineer\w*|develop\w*)', title):
        return None, 'unrelated'
    # Negated requirements are removed before checking explicit restrictions.
    restrictions = re.sub(r'(?:no|without|does not require|not required)[^.\n;]{0,35}(?:security clearance|citizenship)', '', text)
    restrictions = re.sub(r'(?:security clearance|citizenship)(?: is)? not required', '', restrictions)
    patterns = (
        r'(?:must|require[sd]?|only|limited to)[^.\n;]{0,55}(?:citizen|citizenship|green card|permanent residen|security clearance)',
        r'(?:us|u\.s\.) citizens? only', r'(?:active|eligible for|obtain|maintain)[^.\n;]{0,30}(?:security|secret) clearance',
        r'(?:no|without|not (?:provide|offer|available|support)|unable to|cannot|will not)[^.\n;]{0,50}(?:sponsor|sponsorship)',
        r'(?:sponsorship|visa sponsorship)[^.\n;]{0,20}(?:not available|not provided|not offered)',
        r'(?:permanent|unrestricted) (?:us |u\.s\. )?work authori',
        r'\bus persons?\b',
        r'(?:citizenship|security clearance|green card|permanent residen[a-z ]*)[^.\n;]{0,20}(?:required|mandatory|only)',
    )
    if any(re.search(p, restrictions) for p in patterns) or any(j[k] == 'restricted' for k in ('sponsorship', 'cpt', 'opt')):
        return None, 'eligibility_restriction'
    minimum = j.get('min_experience_years')
    experience = [int(x) for x in re.findall(r'\b(\d{1,2})\+?\s*(?:-|–|to)?\s*\d*\s*years? (?:of )?(?:professional |relevant |industry |software |engineering |development |work )*experience', text)]
    if (minimum is not None and minimum > 3) or (experience and min(experience) > 3):
        return None, 'experience'
    intern = j['employment_type'] in ('internship', 'co-op') or re.search(r'\bintern(?:ship)?s?\b|\bco[ -]?op\b', title)
    if intern:
        term = (j.get('term') or '') + ' ' + j['title']
        start = j.get('start_date')
        if re.search(r'\b(?:summer|fall|autumn)\s*2027\b|\b2027\s*(?:summer|fall|autumn)\b', term, re.I):
            return None, 'wrong_term'
        if j.get('term') and not re.search(r'\b(?:spring|winter|january|february|march|april|may)\s*2027\b|\b2027\s*(?:spring|winter)\b', j['term'], re.I):
            return None, 'wrong_term'
        spring = bool(re.search(r'\b(?:spring|winter|january|february|march|april|may)\s*2027\b|\b2027\s*(?:spring|winter)\b', term, re.I))
        if not spring and not (start and '2027-01-01' <= start <= '2027-05-31'):
            return None, 'wrong_term'
        if start and not '2027-01-01' <= start <= '2027-05-31':
            return None, 'wrong_term'
        return ('Spring 2027 Co-op' if j['employment_type'] == 'co-op' or re.search(r'co[ -]?op', title) else 'Spring 2027 Internship'), None
    if j['employment_type'] != 'full-time':
        return None, 'employment_type'
    if j.get('start_date') and not '2027-05-01' <= j['start_date'] <= '2027-12-31':
        return None, 'wrong_start'
    if re.search(r'\b202[0-689]\b', title) and '2027' not in title:
        return None, 'wrong_year'
    if not ('2027' in title or re.search(r'new grad|new college grad|entry[ -]level|early[ -]career|associate|engineer (?:i|ii)\b|developer (?:i|ii)\b', title) or minimum is not None and minimum <= 3):
        return None, 'unconfirmed_early_career'
    return 'Full-Time 2027', None

def load_json(path, default=None):
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text())

def atomic_json(path, data):
    content = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if path.exists() and path.read_text() == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as f:
        f.write(content)
        name = f.name
    os.replace(name, path)

def sync(payload, root=ROOT, now=None):
    now = now or datetime.now(timezone.utc)
    if not isinstance(payload, dict) or payload.get('schema_version') != 1 or not isinstance(payload.get('jobs'), list):
        raise ImportErrorSafe('Expected schema_version=1 and jobs array')
    generated = fresh(payload.get('generated_at'), now)
    if len(payload['jobs']) > 10000:
        raise ImportErrorSafe('Feed exceeds 10,000 jobs')
    # Validate the complete batch before making any writes.
    incoming = [validate(raw, now) for raw in payload['jobs']]
    existing = load_json(root / 'roles_jobright.json', [])
    if not isinstance(existing, list) or any(not isinstance(j, dict) for j in existing):
        raise ImportErrorSafe('Existing automated data is invalid')
    legacy_keys = set()
    for name in LEGACY:
        rows = load_json(root / f'roles_{name}.json')
        if not isinstance(rows, list) or any(not isinstance(j, dict) for j in rows):
            raise ImportErrorSafe('Existing portal data is invalid')
        for j in rows:
            legacy_keys.update(identities(j))
    counts = Counter(inspected=len(incoming), matched=0, added=0, updated=0, duplicates=0)
    rejected = Counter()
    positions = {}
    for i, j in enumerate(existing):
        for k in identities(j):
            positions[k] = i
    for j in incoming:
        keys = identities(j)
        found = {positions[k] for k in keys if k in positions}
        if len(found) > 1:
            raise ImportErrorSafe('Conflicting job identifiers; resolve before importing')
        category, reason = classify(j)
        if not category:
            rejected[reason] += 1
            # Preserve previously discovered records, hide now-ineligible records.
            if found:
                i = found.pop()
                existing[i] = {**existing[i], 'filter_status': 'excluded', 'filter_reason': reason, 'last_checked': j['last_checked']}
            continue
        counts['matched'] += 1
        if keys & legacy_keys:
            counts['duplicates'] += 1
            continue
        j['category'] = category
        j['filter_status'] = 'included'
        if found:
            i = found.pop()
            old = existing[i]
            j['date_added'] = old['date_added']
            j['first_discovered'] = old['first_discovered']
            j['id'] = old['id']
            if old != j:
                counts['updated'] += 1
            else:
                counts['duplicates'] += 1
            existing[i] = j
            position = i
        else:
            j['date_added'] = now.date().isoformat()
            j['first_discovered'] = now.isoformat()
            j['id'] = hashlib.sha256(j['source_id'].encode()).hexdigest()[:24]
            existing.append(j)
            counts['added'] += 1
            position = len(existing) - 1
        for k in keys:
            positions[k] = position
    # Existing records are never removed because an export is empty or partial.
    report = {'status': 'success', 'last_success': now.isoformat(), 'feed_generated_at': generated, **counts, 'rejected': dict(rejected)}
    atomic_json(root / 'roles_jobright.json', existing)
    atomic_json(root / 'jobright_sync.json', report)
    return report

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ImportErrorSafe('Feed redirects are refused; configure its final HTTPS URL')

def fetch_feed():
    endpoint = url(os.environ.get('JOBRIGHT_FEED_URL'))
    host = urlsplit(endpoint).hostname
    allowed = os.environ.get('JOBRIGHT_FEED_HOST', '').lower().strip()
    if host != allowed or host == 'jobright.ai' or host.endswith('.jobright.ai'):
        raise ImportErrorSafe('Use an approved export host, not Jobright web or private API routes')
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ImportErrorSafe('Export host must resolve to public addresses')
    headers = {'Accept': 'application/json', 'User-Agent': 'Job-Portal-Authorized-Import/1.0'}
    token = os.environ.get('JOBRIGHT_FEED_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    for attempt in range(3):
        try:
            with build_opener(NoRedirect()).open(Request(endpoint, headers=headers), timeout=30) as r:
                if r.headers.get_content_type() != 'application/json':
                    raise ImportErrorSafe('Export must return application/json')
                data = r.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ImportErrorSafe('Export exceeds 10 MiB')
                return json.loads(data)
        except HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise ImportErrorSafe(f'Export request failed with HTTP {e.code}; check access or rate limits') from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise ImportErrorSafe('Export request failed after three attempts') from None
        time.sleep(2 ** attempt)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Local authorized normalized export (keep outside repository)')
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        if os.environ.get('JOBRIGHT_IMPORT_AUTHORIZED') != 'true':
            raise ImportErrorSafe('Import disabled: permission to collect AND republish is required')
        payload = load_json(args.input) if args.input else fetch_feed()
        print(json.dumps(sync(payload, args.root)))
    except Exception as e:
        # Never print response bodies, endpoint URLs, or credentials.
        message = str(e) if isinstance(e, ImportErrorSafe) else 'Import failed; invalid data or unavailable files'
        print(json.dumps({'status': 'failed', 'error': message}), file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
