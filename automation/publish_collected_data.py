"""Publish collected JSON with bounded retries when another editor updates main."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DATA_FILES = ('roles_jobright.json', 'jobright_sync.json', 'roles_jobright_public.json', 'jobright_public_sync.json')

class PublishError(RuntimeError):
    pass

def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, capture_output=True, text=True)

def validate_publication(root):
    for command in ([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests'],
                    ['node', '--test', 'tests/portal.test.cjs']):
        result = subprocess.run(command, cwd=root, capture_output=True, text=True)
        if result.returncode:
            # Test output contains test diagnostics, not authentication responses.
            print(result.stdout, end='')
            print(result.stderr, end='', file=sys.stderr)
            raise PublishError('Latest main failed validation; publication stopped without overwriting it')

def publish(root=ROOT, validator=validate_publication, attempts=3, include_page_repair=False):
    allowed = set(DATA_FILES)
    if include_page_repair:
        try:
            from .ensure_portal_integration import expected_repair
        except ImportError:
            from ensure_portal_integration import expected_repair
        if not expected_repair(root/'index.html'):
            raise PublishError('Refusing to publish a page other than the verified automatic repair')
        allowed.add('index.html')
    if git(root, 'add', '--', *sorted(allowed)).returncode:
        raise PublishError('Could not stage collection files')
    diff = git(root, 'diff', '--cached', '--quiet')
    if diff.returncode == 0:
        validator(root)
        return {'status':'unchanged', 'push_attempts':0}
    if diff.returncode != 1:
        raise PublishError('Could not inspect staged collection files')
    staged = git(root, 'diff', '--cached', '--name-only').stdout.splitlines()
    if set(staged) - allowed:
        raise PublishError('Unrelated staged changes found; refusing to include them in a data commit')
    commit = git(root, '-c', 'user.name=github-actions[bot]', '-c',
                 'user.email=41898282+github-actions[bot]@users.noreply.github.com',
                 'commit', '-m', 'Update public Jobright leads')
    if commit.returncode:
        raise PublishError('Could not create collected-data commit')
    for attempt in range(1, attempts + 1):
        if git(root, 'fetch', 'origin', 'main:refs/remotes/origin/main').returncode:
            raise PublishError('Could not refresh main; previous published site retained')
        if git(root, '-c', 'user.name=github-actions[bot]', '-c',
               'user.email=41898282+github-actions[bot]@users.noreply.github.com',
               'rebase', 'refs/remotes/origin/main').returncode:
            git(root, 'rebase', '--abort')
            raise PublishError('Concurrent edits conflict with collected data; no changes were overwritten')
        # Validate the actual revision we will publish, including recent owner edits.
        validator(root)
        if git(root, 'push', 'origin', 'HEAD:main').returncode == 0:
            return {'status':'published', 'push_attempts':attempt}
        print(json.dumps({'status':'retrying', 'attempt':attempt,
                          'reason':'Push rejected or unavailable; refreshing main before retry'}))
    raise PublishError('Could not publish after bounded retries; no force push was attempted')

def main():
    try:
        print(json.dumps(publish(include_page_repair=os.environ.get('PORTAL_REPAIRED')=='true')))
    except PublishError as e:
        print(json.dumps({'status':'failed','error':str(e)}),file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
