"""Exercise real upload/job/cache HTTP boundaries with isolated temporary state."""
import contextlib
from http.server import ThreadingHTTPServer
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

APP_DIR = Path(__file__).resolve().parents[1] / 'Exoplanet data parsing tool'
sys.path.insert(0, str(APP_DIR))
from analysis_jobs import AnalysisJobManager
from main import TransitRequestHandler
from session_cache import SessionCacheManager


class QuietHandler(TransitRequestHandler):
    def log_message(self, *args):
        pass


def multipart(fields, filename='injected.csv', content=None):
    boundary = 'transit-integration-boundary'
    if content is None:
        t = np.linspace(2459000, 2459010, 1000)
        phase = ((t - 2459000.7 + 1) % 2) - 1
        f = 1 - .009 * (np.abs(phase) < .06)
        f += np.random.default_rng(623).normal(0, .0003, len(t))
        content = 'Time,Flux,Flux_err\n' + '\n'.join(f'{a:.10f},{b:.10f},0.0003' for a,b in zip(t,f))
    pieces = []
    for name, value in fields.items():
        pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n')
    pieces.append(f'--{boundary}\r\nContent-Disposition: form-data; name="datafile"; filename="{filename}"\r\nContent-Type: text/csv\r\n\r\n{content}\r\n--{boundary}--\r\n')
    return ''.join(pieces).encode(), f'multipart/form-data; boundary={boundary}'


class HTTPIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix='transit-http-')
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        cls.server.analysis_jobs = AnalysisJobManager()
        cls.server.session_cache = SessionCacheManager(default_directory=cls.directory.name)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.analysis_jobs.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.directory.cleanup()

    def request(self, path, method='GET', data=None, content_type='application/json'):
        request = Request(self.base + path, method=method, data=data,
                          headers={'Content-Type':content_type})
        try:
            response = urlopen(request, timeout=20)
        except HTTPError as exc:
            response = exc
        with response:
            return response.status, response.read(), response.headers

    def test_upload_job_reconnect_and_cache_round_trip(self):
        fields = dict(searchMode='bls', minPeriod='1.8', maxPeriod='2.2',
                      analysisRequestId='http-review-623', batchId='http-batch-623',
                      csvTimeFormat='jd', csvTimeScale='tdb')
        body, mime = multipart(fields)
        status, raw, _ = self.request('/analysis-jobs','POST',body,mime)
        self.assertEqual(status,202,raw)
        submitted=json.loads(raw)
        _, second, _ = self.request('/analysis-jobs','POST',body,mime)
        self.assertEqual(json.loads(second)['job_id'],submitted['job_id'])
        status, recovered, _ = self.request('/analysis-jobs?request_id=http-review-623')
        self.assertEqual(status,200,recovered)
        self.assertEqual(json.loads(recovered)['job_id'],submitted['job_id'])
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            _, raw, _=self.request('/analysis-jobs/'+submitted['job_id'])
            job=json.loads(raw)
            if job['status'] in ('completed','failed','cancelled'):
                break
            time.sleep(.25)
        self.assertEqual(job['status'],'completed',job)
        result=job['result']
        self.assertAlmostEqual(result['period'],2,delta=.05)
        self.assertEqual(result['result_schema_version'],2)
        self.assertIsNotNone(result['provenance']['analyzed_at'])
        self.assertEqual(result['cleaning']['retained_rows'],1000)
        self.assertEqual(result['input_metadata']['time_scale'],'TDB')
        state=dict(results=[dict(file_name='injected.csv',result=result,error=None)],
                   current_batch_index=0,current_view='phase',active_job_id=None)
        status, raw, _=self.request('/analysis-sessions/http_review_623','POST',json.dumps(state).encode())
        self.assertEqual(status,200,raw)
        status, raw, _=self.request('/analysis-sessions/http_review_623')
        self.assertEqual(status,200,raw)
        restored=json.loads(raw)['state']['results'][0]['result']
        self.assertEqual(restored['provenance'],result['provenance'])
        self.assertEqual(restored['planet_assessment'],result['planet_assessment'])

    def test_invalid_cache_returns_recoverable_error_without_overwriting(self):
        path=Path(self.directory.name)/'session-bad_cache_623.json'
        original=b'{broken'
        path.write_bytes(original)
        status, raw, _=self.request('/analysis-sessions/bad_cache_623')
        self.assertEqual(status,400)
        self.assertIn('error',json.loads(raw))
        self.assertEqual(path.read_bytes(),original)
        self.assertEqual(self.request('/')[0],200)

    def test_static_assets_are_served_with_expected_content_types(self):
        for path, expected in [('/', 'text/html'),('/static/app.js','application/javascript'),('/static/styles.css','text/css')]:
            status, data, headers=self.request(path)
            self.assertEqual(status,200)
            self.assertGreater(len(data),100)
            self.assertIn(expected,headers['Content-Type'])


if __name__=='__main__':
    unittest.main()
