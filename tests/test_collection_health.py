from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from automation.check_collection_health import check, decision

NOW=datetime(2026,11,22,22,tzinfo=timezone.utc)
def status(minutes=0):return {'status':'success','last_success':(NOW-timedelta(minutes=minutes)).isoformat()}
def run(minutes=0,conclusion='success',state='completed'):
    return {'status':state,'conclusion':conclusion,'created_at':(NOW-timedelta(minutes=minutes)).isoformat()}

class RecoveryDecisionTests(unittest.TestCase):
    def test_fresh_collection_not_dispatched(self):self.assertEqual(decision(status(180),[run(180)],NOW),'healthy')
    def test_overdue_collection_recovered(self):self.assertEqual(decision(status(211),[run(211)],NOW),'recover')
    def test_active_collection_not_duplicated(self):
        for state in ('queued','in_progress','waiting','pending','requested'):
            self.assertEqual(decision(status(300),[run(1,None,state)],NOW,force=True),'already_running')
    def test_recent_failure_observes_cooldown(self):self.assertEqual(decision(status(300),[run(30,'failure')],NOW),'cooldown')
    def test_failed_deployment_recovered_even_with_fresh_collection(self):self.assertEqual(decision(status(90),[run(90,'failure')],NOW),'recover')
    def test_missing_status_recovered(self):self.assertEqual(decision({},[],NOW),'recover')
    def test_invalid_and_future_timestamp_recovered(self):
        self.assertEqual(decision({'status':'success','last_success':'invalid'},[],NOW),'recover')
        self.assertEqual(decision(status(-30),[],NOW),'recover')
    def test_explicit_manual_recovery_can_override_freshness(self):self.assertEqual(decision(status(),[run()],NOW,True),'recover')
    def test_healthy_cancelled_run_does_not_restart_unnecessarily(self):self.assertEqual(decision(status(10),[run(5,'cancelled')],NOW),'healthy')

@patch.dict(os.environ,{'GITHUB_REPOSITORY':'Sujendra-23/Job-Portal-site'})
class RecoveryAPITests(unittest.TestCase):
    def test_only_expected_workflow_is_dispatched(self):
        calls=[]
        def request(path,method='GET',data=None):
            calls.append((path,method,data))
            if path.endswith('jobright-sync.yml'):return {'state':'active'}
            if '/runs?' in path:return {'workflow_runs':[]}
            return None
        with tempfile.TemporaryDirectory() as folder:
            result=check(Path(folder),request,NOW)
        self.assertEqual(result['status'],'recovery_dispatched')
        self.assertEqual(calls[-1],('/repos/Sujendra-23/Job-Portal-site/actions/workflows/jobright-sync.yml/dispatches','POST',{'ref':'main'}))
    def test_disabled_workflow_requires_owner_action(self):
        with self.assertRaisesRegex(RuntimeError,'disabled'):
            check(Path('.'),lambda *a:{'state':'disabled_manually'},NOW)
    def test_healthy_check_does_not_write(self):
        calls=[]
        def request(path,method='GET',data=None):
            calls.append(method)
            return {'state':'active'} if path.endswith('jobright-sync.yml') else {'workflow_runs':[run()]}
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder)/'jobright_public_sync.json').write_text(json.dumps(status()))
            result=check(Path(folder),request,NOW)
        self.assertEqual(result['status'],'healthy');self.assertNotIn('POST',calls)
