from pathlib import Path
import tempfile
import unittest
from automation.ensure_portal_integration import ensure, expected_repair, PortalRepairError, ROOT

def legacy_page():
    return (ROOT/'tests/fixtures/legacy-index.html').read_bytes()

class PortalRepairTests(unittest.TestCase):
    def test_known_legacy_page_repaired_and_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'index.html').write_bytes(legacy_page())
            self.assertTrue(ensure(root)['changed'])
            self.assertTrue(expected_repair(root/'index.html'))
            before=(root/'index.html').read_bytes()
            self.assertFalse(ensure(root)['changed'])
            self.assertEqual((root/'index.html').read_bytes(),before)
    def test_unrecognized_custom_page_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);page=root/'index.html';page.write_text('<html>Custom owner page</html>')
            before=page.read_bytes()
            with self.assertRaises(PortalRepairError):ensure(root)
            self.assertEqual(page.read_bytes(),before)
    def test_custom_page_with_hooks_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);page=root/'index.html'
            page.write_text('Custom design roles_jobright.json roles_jobright_public.json automation/portal-automation.js automation-meta')
            before=page.read_bytes();self.assertFalse(ensure(root)['changed'])
            self.assertEqual(page.read_bytes(),before)
    def test_job_data_never_modified(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'index.html').write_bytes(legacy_page())
            data=root/'roles_unverified.json';data.write_text('[{"company":"Owner entry"}]')
            before=data.read_bytes();ensure(root);self.assertEqual(data.read_bytes(),before)
    def test_crlf_legacy_input_supported(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'index.html').write_bytes(legacy_page().replace(b'\n',b'\r\n'))
            self.assertTrue(ensure(root)['changed']);self.assertTrue(expected_repair(root/'index.html'))
