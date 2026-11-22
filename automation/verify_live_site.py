"""Verify the deployed portal exposes the current collected snapshot."""
import argparse
from datetime import datetime, timezone
import json
import subprocess
import sys
import time
from urllib.parse import urlencode

SITE = 'https://sujendra-23.github.io/Job-Portal-site/'
class VerificationError(ValueError):
    pass

def verify(html, status, records, expected_time):
    for marker in ('roles_jobright_public.json', 'automation/portal-automation.js', 'automation-meta'):
        if marker not in html:
            raise VerificationError('Published page is missing the Jobright integration')
    if not isinstance(status, dict) or status.get('status') != 'success':
        raise VerificationError('Published collection status is not successful')
    try:
        actual = datetime.fromisoformat(status['last_success'].replace('Z','+00:00'))
        expected = datetime.fromisoformat(expected_time.replace('Z','+00:00'))
        if actual.tzinfo is None or expected.tzinfo is None:
            raise ValueError()
    except (KeyError, TypeError, AttributeError, ValueError):
        raise VerificationError('Published collection timestamp is invalid') from None
    if actual < expected:
        raise VerificationError('Published collection is older than this deployment')
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        raise VerificationError('Published lead data is invalid')
    visible = [r for r in records if r.get('filter_status') != 'excluded']
    if len(visible) != status.get('visible_public_leads'):
        raise VerificationError('Published lead count does not match the collection report')
    identifiers = [r.get('id') for r in records]
    if None in identifiers or len(set(identifiers)) != len(identifiers):
        raise VerificationError('Published leads have missing or duplicate IDs')
    return {'status':'verified', 'last_success':status['last_success'], 'visible_public_leads':len(visible)}

def fetch(path, nonce):
    result = subprocess.run(['curl','--fail','--silent','--show-error','--proto','=https',
                             '--max-time','15','--max-filesize','10485760',
                             SITE+path+'?'+urlencode({'verify':nonce})],capture_output=True,text=True)
    if result.returncode:
        raise VerificationError('Published website is temporarily unavailable')
    return result.stdout

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-time',required=True)
    args=parser.parse_args()
    for attempt in range(6):
        try:
            nonce=str(time.time_ns())
            result=verify(fetch('',nonce),json.loads(fetch('jobright_public_sync.json',nonce)),
                          json.loads(fetch('roles_jobright_public.json',nonce)),args.expected_time)
            print(json.dumps(result))
            return 0
        except (VerificationError, ValueError) as e:
            message=str(e) if isinstance(e,VerificationError) else 'Published JSON is not yet available'
            print(json.dumps({'status':'waiting_for_publication','attempt':attempt+1,'reason':message}))
            if attempt<5:
                time.sleep(10)
    print('::error::Published portal did not pass the collected-data verification',file=sys.stderr)
    return 1

if __name__=='__main__':
    sys.exit(main())
