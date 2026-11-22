from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest
from automation.collect_public_jobright import collect, parse_table, is_us, dedupe_keys, SOURCES
from automation.sync_jobs import ImportErrorSafe, LEGACY

HEADER = '| Company | Job Title | Location | Work Model | Date Posted |\n| ----- | --------- | --------- | ---- | ------- |\n'
def row(company='Example', title='Software Engineer, New Grad 2027', location='Austin, TX, United States', source_id='abc'):
    co = '↳' if company == '↳' else f'**[{company}](https://example.com)**'
    return f'| {co} | **[{title}](https://jobright.ai/jobs/info/{source_id}?utm_source=git)** | {location} | Remote | Nov 22 |\n'

NOW = datetime(2026,11,22,21,tzinfo=timezone.utc)
class PublicJobrightTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        for name in LEGACY+('unverified','jobright'):
            (self.root/f'roles_{name}.json').write_text('[]')
        self.sources={SOURCES[0][0]:HEADER+row(),SOURCES[1][0]:HEADER+row(title='Software Engineering Intern Spring 2027',source_id='intern')}
    def tearDown(self):self.tmp.cleanup()
    def run_collect(self):return collect(self.root,self.sources.__getitem__,NOW)
    def saved(self):return json.loads((self.root/'roles_jobright_public.json').read_text())
    def test_actual_markdown_and_continuation(self):
        rows=parse_table(HEADER+row()+row(company='↳',source_id='def'))
        self.assertEqual([r['company'] for r in rows],['Example','Example'])
        self.assertNotIn('utm_',rows[0]['source_url'])
    def test_orphan_continuation_rejected(self):
        with self.assertRaises(ImportErrorSafe):parse_table(HEADER+row(company='↳'))
    def test_public_leads_not_marked_employer_verified(self):
        report=self.run_collect(); self.assertEqual(report['added'],2)
        for j in self.saved():
            self.assertIsNone(j['application_link']);self.assertIsNone(j['posting_date'])
            self.assertEqual(j['status'],'unknown');self.assertEqual(j['sponsorship'],'unknown')
            self.assertEqual(j['automation_source'],'jobright-public-github')
            self.assertIn('not been verified',j['description'])
    def test_idempotence_and_original_discovery(self):
        self.run_collect();before=self.saved();report=self.run_collect()
        self.assertEqual(report['added'],0);self.assertEqual(before,self.saved())
    def test_source_id_deduplication(self):
        self.sources[SOURCES[0][0]]=HEADER+row()+row(source_id='abc')
        self.assertEqual(self.run_collect()['added'],2)
    def test_existing_normalized_location_deduplication(self):
        (self.root/'roles_top.json').write_text(json.dumps([dict(company='Example Inc.',title='Software Engineer, New Grad 2027',location='Austin, TX')]))
        report=self.run_collect();self.assertEqual(report['added'],1);self.assertEqual(report['duplicates'],1)
    def test_company_alias_and_multi_city_deduplication(self):
        left=dict(company='Palantir',title='Software Engineer, New Grad',location='New York, NY; Denver, CO')
        right=dict(company='Palantir Technologies',title='Software Engineer, New Grad',location='Denver, CO, United States')
        self.assertTrue(dedupe_keys(left) & dedupe_keys(right))
    def test_promoted_lead_hidden_without_deleting_history(self):
        self.run_collect()
        (self.root/'roles_top.json').write_text(json.dumps([self.saved()[0]]))
        report=self.run_collect()
        self.assertEqual(len(self.saved()),2);self.assertEqual(report['visible_public_leads'],1)
    def test_non_us_and_wrong_term_excluded(self):
        self.sources[SOURCES[0][0]]=HEADER+row(location='Toronto, ON, Canada')
        self.sources[SOURCES[1][0]]=HEADER+row(title='Software Engineering Intern Summer 2027',source_id='summer')
        self.assertEqual(self.run_collect()['added'],0)
    def test_restrictive_titles_excluded(self):
        self.sources[SOURCES[0][0]]=HEADER+row(title='Software Engineer, New Grad - Defense')
        self.assertEqual(self.run_collect()['rejected']['restricted_title'],1)
    def test_layout_change_preserves_both_files(self):
        self.run_collect(); before={p.name:p.read_bytes() for p in self.root.glob('*.json')}
        self.sources[SOURCES[1][0]]='Login page or changed table'
        with self.assertRaises(ImportErrorSafe):self.run_collect()
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.glob('*.json')})
    def test_empty_source_preserves_history(self):
        self.run_collect();self.sources[SOURCES[0][0]]=HEADER
        with self.assertRaises(ImportErrorSafe):self.run_collect()
        self.assertEqual(len(self.saved()),2)
    def test_fetch_failure_preserves(self):
        self.run_collect();before=self.saved()
        def fail(_):raise ImportErrorSafe('unavailable')
        with self.assertRaises(ImportErrorSafe):collect(self.root,fail,NOW)
        self.assertEqual(before,self.saved())
    def test_malicious_link_rejected(self):
        with self.assertRaises(ImportErrorSafe):parse_table((HEADER+row()).replace('https://jobright.ai/jobs/info/abc','https://evil.example/jobs/info/abc'))
    def test_us_recognition_is_conservative(self):
        for x in ('Austin, TX','Remote, United States','U.S. Remote','Remote US'):
            self.assertTrue(is_us(x),x)
        for x in ('Toronto, ON, Canada','Remote','Worldwide','London, England'):
            self.assertFalse(is_us(x),x)
