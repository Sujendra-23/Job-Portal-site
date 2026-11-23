import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from automation.publish_collected_data import DATA_FILES, PublishError, git, publish

class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.remote=self.root/'remote.git';self.worker=self.root/'worker';self.editor=self.root/'editor'
        self.command(self.root,'init','--bare','--initial-branch=main',str(self.remote))
        self.command(self.root,'clone',str(self.remote),str(self.worker))
        for name in DATA_FILES:(self.worker/name).write_text('[]\n')
        (self.worker/'index.html').write_text('original page\n')
        self.commit(self.worker,'baseline');self.command(self.worker,'push','origin','HEAD:main')
        self.command(self.root,'clone',str(self.remote),str(self.editor))
    def tearDown(self):self.tmp.cleanup()
    def command(self,root,*args):
        result=git(root,*args)
        self.assertEqual(result.returncode,0,result.stderr)
        return result
    def commit(self,root,message):
        self.command(root,'add','.')
        self.command(root,'-c','user.name=Test','-c','user.email=test@example.com','commit','-m',message)
    def modify_collection(self):
        (self.worker/'roles_jobright_public.json').write_text('[{"id":"new"}]\n')
    def test_no_change_does_not_push(self):
        calls=[]
        self.assertEqual(publish(self.worker,validator=lambda r:calls.append(r))['push_attempts'],0)
        self.assertEqual(calls,[self.worker])
    def test_parallel_owner_edit_is_preserved_and_retried(self):
        self.modify_collection();attempts=[];validated=[]
        def raced(root,*args):
            if args==('push','origin','HEAD:main'):
                attempts.append(1)
                if len(attempts)==1:
                    (self.editor/'index.html').write_text('new owner page\n')
                    self.commit(self.editor,'owner update');self.command(self.editor,'push','origin','HEAD:main')
            return git(root,*args)
        with patch('automation.publish_collected_data.git',side_effect=raced):
            result=publish(self.worker,validator=lambda r:validated.append(r))
        self.assertEqual(result['push_attempts'],2);self.assertEqual(len(validated),2)
        self.command(self.editor,'pull','--ff-only')
        self.assertEqual((self.editor/'index.html').read_text(),'new owner page\n')
        self.assertEqual(json.loads((self.editor/'roles_jobright_public.json').read_text()),[{'id':'new'}])
    def test_conflicting_owner_data_is_not_overwritten(self):
        self.modify_collection()
        def raced(root,*args):
            if args==('push','origin','HEAD:main'):
                (self.editor/'roles_jobright_public.json').write_text('[{"id":"owner"}]\n')
                self.commit(self.editor,'owner data update');self.command(self.editor,'push','origin','HEAD:main')
            return git(root,*args)
        with patch('automation.publish_collected_data.git',side_effect=raced):
            with self.assertRaisesRegex(PublishError,'conflict'):publish(self.worker,validator=lambda r:None)
        self.assertEqual(json.loads((self.editor/'roles_jobright_public.json').read_text()),[{'id':'owner'}])
        self.assertFalse((self.worker/'.git/rebase-merge').exists())
    def test_retries_are_bounded(self):
        self.modify_collection();attempts=[]
        def denied(root,*args):
            if args==('push','origin','HEAD:main'):
                attempts.append(1);return subprocess.CompletedProcess(args,1,'','rejected')
            return git(root,*args)
        with patch('automation.publish_collected_data.git',side_effect=denied):
            with self.assertRaisesRegex(PublishError,'bounded retries'):publish(self.worker,validator=lambda r:None)
        self.assertEqual(len(attempts),3)
    def test_unrelated_staged_changes_are_refused(self):
        self.modify_collection();(self.worker/'index.html').write_text('unrelated local edit\n')
        self.command(self.worker,'add','index.html')
        with self.assertRaisesRegex(PublishError,'Unrelated staged'):publish(self.worker,validator=lambda r:None)
    def test_failed_validation_never_pushes(self):
        self.modify_collection()
        def reject(root):raise PublishError('validation failed')
        with self.assertRaisesRegex(PublishError,'validation failed'):publish(self.worker,validator=reject)
        self.command(self.editor,'pull','--ff-only')
        self.assertEqual((self.editor/'roles_jobright_public.json').read_text(),'[]\n')

    def test_only_verified_automatic_page_repair_can_be_published(self):
        from automation.ensure_portal_integration import ROOT, ensure
        baseline=(ROOT/'tests/fixtures/legacy-index.html').read_bytes()
        (self.worker/'index.html').write_bytes(baseline)
        self.commit(self.worker,'known legacy page');self.command(self.worker,'push','origin','HEAD:main')
        ensure(self.worker);self.modify_collection()
        result=publish(self.worker,validator=lambda r:None,include_page_repair=True)
        self.assertEqual(result['status'],'published')
        self.command(self.editor,'pull','--ff-only')
        self.assertIn('roles_jobright_public.json',(self.editor/'index.html').read_text())
    def test_custom_page_cannot_be_staged_as_automatic_repair(self):
        (self.worker/'index.html').write_text('custom page')
        self.modify_collection()
        with self.assertRaisesRegex(PublishError,'verified automatic repair'):
            publish(self.worker,validator=lambda r:None,include_page_repair=True)
