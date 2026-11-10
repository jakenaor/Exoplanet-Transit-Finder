"""Exercise real upload/job/cache HTTP boundaries with isolated temporary state."""
import contextlib as Contextlib
from http.server import ThreadingHTTPServer
import io as Io
import json as Json
from pathlib import Path
import sys as Sys
import tempfile as Tempfile
import threading as Threading
import time as Time
import unittest as Unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen as Urlopen

import numpy as Np

APP_DIR = Path(__file__).resolve().parents[1] / 'Exoplanet data parsing tool'
Sys.path.insert(0, str(APP_DIR))
from analysis_jobs import AnalysisJobManager
from main import TransitRequestHandler
from session_cache import SessionCacheManager


#MARK: quiet handler
class QuietHandler(TransitRequestHandler):
    def log_message(self, *Args):
        pass


#MARK: multipart
def Multipart(Fields, Filename='injected.csv', Content=None):
    Boundary = 'transit-integration-boundary'
    if Content is None:
        T = Np.linspace(2459000, 2459010, 1000)
        Phase = ((T - 2459000.7 + 1) % 2) - 1
        F = 1 - .009 * (Np.abs(Phase) < .06)
        F += Np.random.default_rng(623).normal(0, .0003, len(T))
        Content = 'Time,Flux,Flux_err\n' + '\n'.join(f'{A:.10f},{B:.10f},0.0003' for A,B in zip(T,F))
    Pieces = []
    for Name, Value in Fields.items():
        Pieces.append(f'--{Boundary}\r\nContent-Disposition: form-data; name="{Name}"\r\n\r\n{Value}\r\n')
    Pieces.append(f'--{Boundary}\r\nContent-Disposition: form-data; name="datafile"; filename="{Filename}"\r\nContent-Type: text/csv\r\n\r\n{Content}\r\n--{Boundary}--\r\n')
    return ''.join(Pieces).encode(), f'multipart/form-data; boundary={Boundary}'


#MARK: web stuffs
class HTTPIntegrationTests(Unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.Directory = Tempfile.TemporaryDirectory(prefix='transit-http-')
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        cls.server.AnalysisJobs = AnalysisJobManager()
        cls.server.RunCache = SessionCacheManager(DefaultDirectory=cls.Directory.name)
        cls.Thread = Threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.Thread.start()
        cls.Base = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.AnalysisJobs.shutdown()
        cls.server.server_close()
        cls.Thread.join(timeout=3)
        cls.Directory.cleanup()

    def HttpRequest(self, FilePath, Method='GET', Data=None, ContentType='application/json'):
        HttpRequest = Request(self.Base + FilePath, method=Method, data=Data,
                          headers={'Content-Type':ContentType})
        try:
            Response = Urlopen(HttpRequest, timeout=20)
        except HTTPError as Exc:
            Response = Exc
        with Response:
            return Response.status, Response.read(), Response.headers

    def testUploadJobReconnectAndCacheRoundTrip(self):
        Fields = dict(searchMode='bls', minPeriod='1.8', maxPeriod='2.2',
                      analysisRequestId='http-review-623', batchId='http-batch-623',
                      csvTimeFormat='jd', csvTimeScale='tdb', exposureSeconds='0')
        Body, Mime = Multipart(Fields)
        Status, Raw, _ = self.HttpRequest('/analysis-jobs','POST',Body,Mime)
        self.assertEqual(Status,202,Raw)
        Submitted=Json.loads(Raw)
        _, Second, _ = self.HttpRequest('/analysis-jobs','POST',Body,Mime)
        self.assertEqual(Json.loads(Second)['job_id'],Submitted['job_id'])
        Status, Recovered, _ = self.HttpRequest('/analysis-jobs?request_id=http-review-623')
        self.assertEqual(Status,200,Recovered)
        self.assertEqual(Json.loads(Recovered)['job_id'],Submitted['job_id'])
        Deadline=Time.monotonic()+20
        while Time.monotonic()<Deadline:
            _, Raw, _=self.HttpRequest('/analysis-jobs/'+Submitted['job_id'])
            Job=Json.loads(Raw)
            if Job['status'] in ('completed','failed','cancelled'):
                break
            Time.sleep(.25)
        self.assertEqual(Job['status'],'completed',Job)
        Result=Job['result']
        self.assertAlmostEqual(Result['period'],2,delta=.05)
        self.assertEqual(Result['result_schema_version'],2)
        self.assertIsNotNone(Result['provenance']['analyzed_at'])
        self.assertEqual(Result['cleaning']['retained_rows'],1000)
        self.assertEqual(Result['input_metadata']['time_scale'],'TDB')
        self.assertEqual(Result['exposure_metadata']['source'],'explicit per-file override')
        self.assertEqual(Result['exposure_metadata']['known_rows'],1000)
        self.assertEqual(Result['exposure_metadata']['minimum_seconds'],0)
        self.assertEqual(Result['execution'],Job['execution'])
        self.assertGreater(Result['execution']['elapsed_seconds'],0)
        State=dict(results=[dict(file_name='injected.csv',result=Result,error=None)],
                   current_batch_index=0,current_view='phase',active_job_id=None)
        Status, Raw, _=self.HttpRequest('/analysis-sessions/http_review_623','POST',Json.dumps(State).encode())
        self.assertEqual(Status,200,Raw)
        Status, Raw, _=self.HttpRequest('/analysis-sessions/http_review_623')
        self.assertEqual(Status,200,Raw)
        Restored=Json.loads(Raw)['state']['results'][0]['result']
        self.assertEqual(Restored['provenance'],Result['provenance'])
        self.assertEqual(Restored['planet_assessment'],Result['planet_assessment'])
        self.assertEqual(Restored['exposure_metadata'],Result['exposure_metadata'])
        self.assertEqual(Restored['execution'],Result['execution'])

    def testInvalidCacheReturnsRecoverableErrorWithoutOverwriting(self):
        FilePath=Path(self.Directory.name)/'session-bad_cache_623.json'
        Original=b'{broken'
        FilePath.write_bytes(Original)
        Status, Raw, _=self.HttpRequest('/analysis-sessions/bad_cache_623')
        self.assertEqual(Status,400)
        self.assertIn('error',Json.loads(Raw))
        self.assertEqual(FilePath.read_bytes(),Original)
        self.assertEqual(self.HttpRequest('/')[0],200)

    def testStaticAssetsAreServedWithExpectedContentTypes(self):
        for FilePath, Expected in [('/', 'text/html'),('/static/app.js','application/javascript'),('/static/styles.css','text/css')]:
            Status, Data, Headers=self.HttpRequest(FilePath)
            self.assertEqual(Status,200)
            self.assertGreater(len(Data),100)
            self.assertIn(Expected,Headers['Content-Type'])


if __name__=='__main__':
    Unittest.RunApp()
