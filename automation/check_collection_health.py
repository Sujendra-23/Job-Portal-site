"""Recover overdue public collection without overlapping or repeatedly dispatching runs."""
import json
import os
from pathlib import Path
import re
import sys
from datetime import datetime, timezone, timedelta
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}

def instant(value):
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return result.astimezone(timezone.utc) if result.tzinfo else None
    except (ValueError, AttributeError, TypeError):
        return None

def decision(status, runs, now, force=False):
    if any(run.get('status') in ACTIVE for run in runs):
        return 'already_running'
    last = instant(status.get('last_success'))
    fresh = status.get('status') == 'success' and last is not None and -timedelta(minutes=5) <= now-last <= timedelta(minutes=210)
    latest = max(runs, key=lambda r: instant(r.get('run_started_at') or r.get('created_at')) or datetime.min.replace(tzinfo=timezone.utc), default={})
    failed = latest.get('conclusion') in {'failure', 'timed_out', 'startup_failure'}
    if fresh and not failed and not force:
        return 'healthy'
    started = instant(latest.get('run_started_at') or latest.get('created_at'))
    if started and now-started < timedelta(minutes=60) and not force:
        return 'cooldown'
    return 'recover'

def github(path, method='GET', data=None):
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        raise RuntimeError('Missing repository workflow token')
    request = Request('https://api.github.com'+path, method=method,
                      data=json.dumps(data).encode() if data is not None else None,
                      headers={'Authorization':'Bearer '+token, 'Accept':'application/vnd.github+json',
                               'Content-Type':'application/json', 'User-Agent':'Job-Portal-Recovery'})
    try:
        with urlopen(request, timeout=30) as response:
            body = response.read(2*1024*1024)
            return json.loads(body) if body else None
    except HTTPError as e:
        raise RuntimeError(f'GitHub recovery request failed (HTTP {e.code})') from None
    except (URLError, TimeoutError, ValueError):
        raise RuntimeError('GitHub recovery request unavailable') from None

def check(root=ROOT, request=github, now=None, force=False):
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise RuntimeError('Invalid GitHub repository context')
    base = f'/repos/{repo}/actions/workflows/jobright-sync.yml'
    workflow = request(base)
    if workflow.get('state') != 'active':
        raise RuntimeError('Collection workflow is disabled; repository owner action is required')
    try:
        status = json.loads((root/'jobright_public_sync.json').read_text())
        if not isinstance(status, dict):
            status = {}
    except (OSError, ValueError):
        status = {}
    runs = request(base+'/runs?branch=main&per_page=30').get('workflow_runs', [])
    result = decision(status, runs, now or datetime.now(timezone.utc), force)
    if result == 'recover':
        request(base+'/dispatches', 'POST', {'ref':'main'})
        result = 'recovery_dispatched'
    return {'status':result, 'last_success':status.get('last_success')}

def main():
    try:
        result = check(force=os.environ.get('RECOVER_NOW') == 'true')
        print(json.dumps(result))
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as f:
                f.write('## Jobright collection recovery\n\n'+result['status']+'\n')
        return 0
    except RuntimeError as e:
        print(json.dumps({'status':'failed','error':str(e)}),file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
