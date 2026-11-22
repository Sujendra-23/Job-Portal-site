"""CLI -> filtering -> persisted JSON -> Pages artifact, using disposable data."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from automation.build_pages import build, PUBLIC_DATA
from test_sync_jobs import job, feed

ROOT = Path(__file__).resolve().parents[1]

class IntegrationTests(unittest.TestCase):
    def test_command_to_pages_and_failed_import_recovery(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in PUBLIC_DATA:
                (root/name).write_text('{}' if name in ('resumes.json','jobright_sync.json') else '[]')
            shutil.copy2(ROOT/'index.html',root/'index.html')
            (root/'automation').mkdir()
            shutil.copy2(ROOT/'automation/portal-automation.js',root/'automation/portal-automation.js')
            now = datetime.now(timezone.utc).isoformat()
            j = job(); j['checked_at'] = now
            payload = feed(j, j); payload['generated_at'] = now
            export = root/'private-export.json'; export.write_text(json.dumps(payload))
            env = dict(os.environ, JOBRIGHT_IMPORT_AUTHORIZED='true')
            command = [sys.executable,str(ROOT/'automation/sync_jobs.py'),'--root',str(root),'--input',str(export)]
            result = subprocess.run(command,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(json.loads(result.stdout)['added'],1)
            out = build(root)
            self.assertEqual(len(json.loads((out/'roles_jobright.json').read_text())),1)
            self.assertTrue((out/'automation/portal-automation.js').exists())
            self.assertFalse((out/'private-export.json').exists())
            before = (root/'roles_jobright.json').read_bytes()
            export.write_text('<html>Login required</html>')
            result = subprocess.run(command,env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,1)
            self.assertEqual((root/'roles_jobright.json').read_bytes(),before)
            self.assertNotIn('Login required',result.stderr)
            env['JOBRIGHT_IMPORT_AUTHORIZED']='false'
            self.assertEqual(subprocess.run(command,env=env,capture_output=True).returncode,1)
