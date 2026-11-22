import unittest
from automation.verify_live_site import verify, VerificationError

HTML='roles_jobright_public.json automation/portal-automation.js automation-meta'
TIME='2026-11-22T22:00:00Z'
def report(**kw):return dict(status='success',last_success=TIME,visible_public_leads=1,**kw)

class LiveVerificationTests(unittest.TestCase):
    def test_matching_snapshot(self):
        self.assertEqual(verify(HTML,report(),[{'id':'one'}],TIME)['status'],'verified')
    def test_old_page_missing_hooks_rejected(self):
        with self.assertRaisesRegex(VerificationError,'integration'):verify('<html>old page</html>',report(),[{'id':'one'}],TIME)
    def test_stale_published_data_rejected(self):
        r=report();r['last_success']='2026-11-22T19:00:00Z'
        with self.assertRaisesRegex(VerificationError,'older'):verify(HTML,r,[{'id':'one'}],TIME)
    def test_newer_snapshot_accepted(self):
        self.assertEqual(verify(HTML,report(),[{'id':'one'}],'2026-11-22T21:00:00Z')['status'],'verified')
    def test_mismatched_record_count_rejected(self):
        with self.assertRaisesRegex(VerificationError,'count'):verify(HTML,report(),[],TIME)
    def test_invalid_status_and_records_rejected(self):
        for r in ({},None):
            with self.assertRaises(VerificationError):verify(HTML,r,[{'id':'one'}],TIME)
        with self.assertRaises(VerificationError):verify(HTML,report(),{},TIME)
    def test_duplicate_ids_rejected(self):
        r=report();r['visible_public_leads']=2
        with self.assertRaisesRegex(VerificationError,'duplicate'):verify(HTML,r,[{'id':'one'},{'id':'one'}],TIME)
    def test_excluded_history_not_counted_as_visible(self):
        self.assertEqual(verify(HTML,report(),[{'id':'one'},{'id':'two','filter_status':'excluded'}],TIME)['visible_public_leads'],1)
    def test_timestamp_requires_timezone(self):
        r=report();r['last_success']='2026-11-22T22:00:00'
        with self.assertRaisesRegex(VerificationError,'timestamp'):verify(HTML,r,[{'id':'one'}],TIME)
