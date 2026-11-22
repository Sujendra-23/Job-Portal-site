import copy
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
from automation.sync_jobs import sync, validate, classify, canonical, ImportErrorSafe, fetch_feed, main, LEGACY

NOW = datetime(2026, 11, 22, 20, tzinfo=timezone.utc)
def job(**overrides):
    return dict(company='Example', title='Software Engineer, New Grad 2027', location='Austin, TX', country='US',
                description='Build software. Zero to two years experience.', employment_type='full-time',
                application_link='https://careers.example.com/jobs/123', source_url='https://jobright.ai/jobs/info/abc',
                checked_at=NOW.isoformat(), **overrides)
def feed(*jobs):
    return dict(schema_version=1, generated_at=NOW.isoformat(), jobs=list(jobs))
def changed(**kw):
    j = job(); j.update(kw); return j

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for name in LEGACY:
            (self.root / f'roles_{name}.json').write_text('[]')
    def tearDown(self): self.tmp.cleanup()
    def run_sync(self, data): return sync(data, self.root, NOW)
    def rows(self): return json.loads((self.root / 'roles_jobright.json').read_text())
    def category(self, **kw): return classify(validate(changed(**kw), NOW))
    def test_full_time_and_idempotence(self):
        self.assertEqual(self.run_sync(feed(job()))['added'], 1)
        before = (self.root / 'roles_jobright.json').read_bytes()
        self.assertEqual(self.run_sync(feed(job()))['added'], 0)
        self.assertEqual(before, (self.root / 'roles_jobright.json').read_bytes())
    def test_spring_intern_and_coop(self):
        for title, kind in [('Software Engineering Intern Spring 2027', 'internship'), ('Backend Developer Co-op Spring 2027', 'co-op')]:
            self.assertIsNotNone(self.category(title=title, employment_type=kind)[0])
    def test_plural_internships_route(self):
        self.assertEqual(self.category(title='Software Engineering Internships', employment_type='internship', start_date='2027-01-11')[0], 'Spring 2027 Internship')
    def test_summer_and_wrong_year_excluded(self):
        for term in ['Summer 2027', 'Spring 2026', '2027']:
            self.assertEqual(self.category(title='Software Engineer Intern '+term, employment_type='internship')[1], 'wrong_term')
    def test_conflicting_intern_terms_excluded(self):
        self.assertEqual(self.category(title='Software Engineer Intern Spring 2027', employment_type='internship',term='Summer 2027')[1], 'wrong_term')
    def test_spring_description_graduation_not_start(self):
        self.assertEqual(self.category(title='Software Engineer Intern', employment_type='internship', description='Graduation Spring 2027. Summer internship.')[1], 'wrong_term')
    def test_fulltime_start_before_graduation(self):
        self.assertEqual(self.category(start_date='2027-01-11')[1], 'wrong_start')
    def test_senior_roles(self):
        for title in ['Senior Software Engineer', 'Staff Backend Engineer', 'Software Engineer III', 'Sr. Full Stack Developer']:
            self.assertEqual(self.category(title=title)[1], 'seniority')
    def test_country_required_remote_not_assumed_us(self):
        self.assertEqual(self.category(country='Canada', location='Remote')[1], 'outside_us')
    def test_unrelated(self): self.assertEqual(self.category(title='Sales Engineer 2027')[1], 'unrelated')
    def test_experience(self):
        self.assertEqual(self.category(min_experience_years=4)[1], 'experience')
        self.assertEqual(self.category(description='Requires 5+ years of software development experience.')[1], 'experience')
        self.assertIsNotNone(self.category(title='Software Engineer II', min_experience_years=2)[0])
    def test_restrictive_text(self):
        for desc in ['Must be a US citizen.', 'US citizenship required.', 'Security clearance required.', 'Requires security clearance.', 'No visa sponsorship.', 'We will not sponsor visas.', 'Sponsorship is not available.', 'Permanent unrestricted work authorization required.']:
            self.assertEqual(self.category(description=desc)[1], 'eligibility_restriction', desc)
    def test_unknown_and_historical_not_supported(self):
        self.assertIsNotNone(self.category(description='Security clearance is not required.')[0])
        self.run_sync(feed(changed(sponsorship_history='Employer sponsored in 2025')))
        self.assertEqual(self.rows()[0]['sponsorship'], 'unknown')
    def test_claim_requires_evidence(self):
        with self.assertRaises(ImportErrorSafe): self.run_sync(feed(changed(cpt='supported')))
    def test_supported_with_evidence(self):
        self.run_sync(feed(changed(cpt='supported', eligibility_evidence='CPT students welcome', eligibility_source_url='https://careers.example.com/jobs/123')))
        self.assertEqual(self.rows()[0]['cpt'], 'supported')
    def test_url_and_cross_file_dedupe(self):
        (self.root/'roles_top.json').write_text(json.dumps([changed(application_link='https://careers.example.com/jobs/123?utm_source=abc')]))
        self.assertEqual(self.run_sync(feed(job()))['duplicates'], 1)
        self.assertEqual(self.rows(), [])
    def test_repeated_feed_and_tracking_url(self):
        self.run_sync(feed(job(), changed(application_link='https://careers.example.com/jobs/123?utm_source=jobright')))
        self.assertEqual(len(self.rows()), 1)
    def test_changed_record_preserves_discovery(self):
        self.run_sync(feed(job()))
        before = self.rows()[0]
        report = sync(feed(changed(description='Updated description.')), self.root, NOW+timedelta(hours=3))
        self.assertEqual(report['updated'], 1)
        self.assertEqual(self.rows()[0]['first_discovered'], before['first_discovered'])
        self.assertEqual(self.rows()[0]['id'], before['id'])
    def test_empty_feed_preserves(self):
        self.run_sync(feed(job())); self.run_sync(feed())
        self.assertEqual(len(self.rows()), 1)
    def test_invalid_batch_preserves_bytes(self):
        self.run_sync(feed(job()))
        before = {p.name:p.read_bytes() for p in self.root.glob('*.json')}
        with self.assertRaises(ImportErrorSafe): self.run_sync(feed(job(), changed(application_link='javascript:alert(1)')))
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.root.glob('*.json')})
    def test_missing_field(self):
        j = job(); del j['country']
        with self.assertRaises(ImportErrorSafe): self.run_sync(feed(j))
    def test_stale_feed_and_record(self):
        for data in [dict(feed(job()), generated_at='2026-01-01T00:00:00Z'),feed(changed(checked_at='2026-01-01T00:00:00Z'))]:
            with self.assertRaises(ImportErrorSafe): self.run_sync(data)
    def test_corrupt_legacy_preserves(self):
        (self.root/'roles_top.json').write_text('{}')
        with self.assertRaises(ImportErrorSafe): self.run_sync(feed(job()))
        self.assertFalse((self.root/'roles_jobright.json').exists())
    def test_expired_and_restricted_updates_retained(self):
        self.run_sync(feed(job())); self.run_sync(feed(changed(status='expired')))
        self.assertEqual(self.rows()[0]['status'], 'expired')
        self.run_sync(feed(changed(description='Must be a US citizen.')))
        self.assertEqual(self.rows()[0]['filter_status'], 'excluded')
    def test_no_private_fields_published(self):
        self.run_sync(feed(changed(email='PRIVATE', token='SECRET', resume='PRIVATE')))
        self.assertNotIn('PRIVATE', json.dumps(self.rows()))
        self.assertNotIn('SECRET', json.dumps(self.rows()))
    def test_application_link_aggregator_rejected(self):
        with self.assertRaises(ImportErrorSafe): self.run_sync(feed(changed(application_link='https://jobright.ai/jobs/info/abc')))
    def test_all_original_files_untouched(self):
        before = {p.name:p.read_bytes() for p in self.root.glob('*.json')}
        self.run_sync(feed(job()))
        for name, content in before.items(): self.assertEqual((self.root/name).read_bytes(), content)

class FetchTests(unittest.TestCase):
    @patch.dict(os.environ, {'JOBRIGHT_FEED_URL':'https://jobright.ai/api/jobs','JOBRIGHT_FEED_HOST':'jobright.ai'})
    def test_no_scraping(self):
        with self.assertRaises(ImportErrorSafe): fetch_feed()
    @patch.dict(os.environ, {'JOBRIGHT_FEED_URL':'https://exports.example.com/feed','JOBRIGHT_FEED_HOST':'exports.example.com'})
    @patch('automation.sync_jobs.socket.getaddrinfo', return_value=[(None,None,None,None,('127.0.0.1',443))])
    def test_no_private_network(self, _):
        with self.assertRaises(ImportErrorSafe): fetch_feed()
    @patch.dict(os.environ, {'JOBRIGHT_FEED_URL':'https://exports.example.com/feed','JOBRIGHT_FEED_HOST':'exports.example.com'})
    @patch('automation.sync_jobs.socket.getaddrinfo', return_value=[(None,None,None,None,('8.8.8.8',443))])
    @patch('automation.sync_jobs.build_opener')
    @patch('automation.sync_jobs.time.sleep')
    def test_bounded_retries(self, sleep, opener, _):
        opener.return_value.open.side_effect = URLError('SECRET URL')
        with self.assertRaisesRegex(ImportErrorSafe, 'three attempts'): fetch_feed()
        self.assertEqual(opener.return_value.open.call_count,3)
        self.assertEqual(sleep.call_count,2)
    def test_canonical_keeps_job_identifiers(self):
        self.assertNotEqual(canonical('https://example.com/?job=1'),canonical('https://example.com/?job=2'))

if __name__ == '__main__': unittest.main()
