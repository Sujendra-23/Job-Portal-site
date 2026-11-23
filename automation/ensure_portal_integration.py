"""Restore automation only when index.html is the exact known pre-integration page."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATCH = Path(__file__).with_name('portal-integration.patch')
LEGACY_SHA256 = '3b9ddbe8cd500c97c49b80ef22f82160071d0b587f8ecf23e4c2be6fd12da218'
REPAIRED_SHA256 = 'b849ffa28d49d27f4d852f7429b3795da535999975a7aad13d9c61bd19bf72f3'
MARKERS = (b'roles_jobright_public.json', b'roles_jobright.json', b'automation/portal-automation.js', b'automation-meta')

class PortalRepairError(RuntimeError):
    pass

def digest(data):
    return hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest()

def expected_repair(path):
    return digest(Path(path).read_bytes()) == REPAIRED_SHA256

def ensure(root=ROOT):
    page = root/'index.html'
    original = page.read_bytes()
    if all(marker in original for marker in MARKERS):
        return {'status':'integration_present','changed':False}
    if digest(original) != LEGACY_SHA256:
        raise PortalRepairError('Unrecognized page changes: automatic repair will not overwrite custom HTML')
    # Match the known legacy input; only this one file is ever patched.
    if b'\r\n' in original:
        page.write_bytes(original.replace(b'\r\n',b'\n'))
    args = ['git','apply','--include=index.html']
    try:
        for command in (args+['--check',str(PATCH)], args+[str(PATCH)]):
            result = subprocess.run(command,cwd=root,capture_output=True,text=True)
            if result.returncode:
                raise PortalRepairError('Known-page integration patch could not be applied safely')
        if not expected_repair(page):
            raise PortalRepairError('Repaired page did not match the expected integration')
    except Exception:
        page.write_bytes(original)
        raise
    return {'status':'known_legacy_page_repaired','changed':True}

def main():
    try:
        result=ensure()
        print(json.dumps(result))
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a') as f:
                f.write('changed='+str(result['changed']).lower()+'\n')
        return 0
    except (PortalRepairError,OSError) as e:
        message=str(e) if isinstance(e,PortalRepairError) else 'Portal page or repair patch is unavailable'
        print(json.dumps({'status':'failed','error':message}),file=sys.stderr)
        return 1

if __name__=='__main__':
    sys.exit(main())
