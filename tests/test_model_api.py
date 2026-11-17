"""用本机模拟API核验配置、模型调用和错误处理，不调用付费模型。"""
import json
import re
import base64
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server
from model_client import configuration
from storage import Store


class ModelHandler(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.calls.append({'path': self.path, 'body': body, 'auth': self.headers.get('Authorization')})
        status = 200
        if self.path.startswith('/unauthorized/'):
            status, payload = 401, {'error': self.headers.get('Authorization')}
        elif self.path.startswith('/redirect/'):
            self.send_response(302)
            self.send_header('Location', '/v1/chat/completions')
            self.end_headers()
            return
        elif self.path.startswith('/malformed/'):
            payload = {'choices': []}
        else:
            content = 'OK'
            if body['max_tokens'] > 256:
                source = re.search(r'\[(?:[CE]\d{2}|U\d{6,})·第\d+[页段]\]', body['messages'][-1]['content'])[0]
                content = '根据文献证据，应分别核对检索质量与生成质量。' + source
                if body['model'] == 'bad-citation':
                    content += '[U999999·第999段]'
            payload = {'choices': [{'message': {'content': content}}]}
        raw = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class ModelAPITest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = Path(cls.temp.name)
        cls.previous = server.STORE, server.KNOWLEDGE, server.LIBRARY
        server.STORE = Store(root)
        server.KNOWLEDGE = server.KnowledgeStore(root)
        server.LIBRARY = server.Library()
        cls.app = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.model = ThreadingHTTPServer(('127.0.0.1', 0), ModelHandler)
        cls.base = 'http://127.0.0.1:' + str(cls.app.server_port)
        cls.model_base = 'http://127.0.0.1:' + str(cls.model.server_port)
        cls.threads=[]
        for httpd in [cls.app, cls.model]:
            thread=threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start();cls.threads.append(thread)
        raw = (ROOT / 'examples/检索与证据.md').read_bytes()
        status, _ = cls.call('/api/knowledge/upload', {'filename': '检索与证据.md', 'content': base64.b64encode(raw).decode()})
        assert status == 200

    @classmethod
    def tearDownClass(cls):
        for httpd in [cls.app, cls.model]:
            httpd.shutdown();httpd.server_close()
        for thread in cls.threads:thread.join()
        server.STORE, server.KNOWLEDGE, server.LIBRARY = cls.previous
        cls.temp.cleanup()

    @classmethod
    def call(cls, path, body=None):
        req = request.Request(cls.base+path, data=None if body is None else json.dumps(body).encode(),
                              headers={'Content-Type':'application/json', 'X-Requested-With':'Zhiyan'})
        try:
            with request.urlopen(req, timeout=10) as response:
                return response.status,json.load(response)
        except error.HTTPError as exc:
            return exc.code,json.load(exc)

    def test_connection_and_full_endpoint(self):
        for url in [self.model_base+'/v1/', self.model_base+'/v1/chat/completions']:
            status,result=self.call('/api/model/test',{'base_url':url,'model':'arbitrary/model:1','api_key':'test-key'})
            self.assertEqual(status,200)
            self.assertTrue(result['ok'])
            self.assertEqual(ModelHandler.calls[-1]['path'],'/v1/chat/completions')
            self.assertEqual(ModelHandler.calls[-1]['body']['model'],'arbitrary/model:1')
            self.assertEqual(ModelHandler.calls[-1]['auth'],'Bearer test-key')
        self.assertEqual(self.call('/api/model/test',{'base_url':self.model_base+'/v1','model':'local-model'})[0],200)
        self.assertIsNone(ModelHandler.calls[-1]['auth'])

    def test_research_uses_configured_model_with_sources(self):
        status,result=self.call('/api/research',{'question':'如何评价RAG知识库的检索与生成质量？','mode':'api',
                               'base_url':self.model_base+'/v1','model':'custom-model','api_key':'private-test-key'})
        self.assertEqual(status,200)
        self.assertEqual(result['mode_label'],'模型归纳 · custom-model')
        self.assertTrue(result['evidence'])
        self.assertIn('根据文献证据',result['answer'])
        allowed={(h['paper_id'],str(h['page']),h['source_unit']) for h in result['evidence']}
        cited=set(re.findall(r'\[(U\d{6,})·第(\d+)(页|段)\]',result['answer']))
        self.assertTrue(cited and cited.issubset(allowed))
        _,exported=self.call('/api/export?format=json')
        serialized=json.dumps(exported)
        for secret in ['private-test-key','api_key','base_url']:
            self.assertNotIn(secret,serialized)
        self.assertNotIn(b'private-test-key',(Path(self.temp.name)/'user_data/research.sqlite3').read_bytes())

    def test_bad_citation_is_not_saved(self):
        before=len(server.STORE.runs())
        status,result=self.call('/api/research',{'question':'如何评价RAG知识库的检索与生成质量？','mode':'api','base_url':self.model_base+'/v1','model':'bad-citation'})
        self.assertEqual(status,400)
        self.assertIn('不在本次证据',result['error'])
        self.assertEqual(len(server.STORE.runs()),before)

    def test_upstream_errors_do_not_echo_key(self):
        for prefix,message in [('unauthorized','HTTP 401'),('redirect','重定向'),('malformed','未返回可用正文')]:
            before=len(ModelHandler.calls)
            status,result=self.call('/api/model/test',{'base_url':self.model_base+'/'+prefix,'model':'model','api_key':'private-test-key'})
            self.assertEqual(status,400)
            self.assertIn(message,result['error'])
            self.assertNotIn('private-test-key',json.dumps(result))
            self.assertEqual(len(ModelHandler.calls),before+1)

    def test_configuration_rejects_invalid_or_unsafe_fields(self):
        for base,model,key in [('https://example.com','model',''),('http://example.com/v1','model','key'),
                               ('https://user:key@example.com','model','key'),('https://example.com?token=secret','model','key'),
                               ('file:///tmp/api','model','key'),('https://example.com','bad\nmodel','key'),
                               ('https://example.com','model','key\nheader'),(None,'model','key')]:
            with self.assertRaises(ValueError):configuration(base,model,key)
        for model in ['',None,'invalid model']:
            self.assertEqual(self.call('/api/model/test',{'base_url':self.model_base,'model':model})[0],400)

    def test_no_evidence_never_calls_model(self):
        before=len(ModelHandler.calls)
        status,result=self.call('/api/research',{'question':'本单位今年的续约率是多少？','mode':'api',
                               'base_url':self.model_base,'model':'local-model'})
        self.assertEqual(status,200)
        self.assertEqual(result['mode_label'],'资料不足')
        self.assertEqual(len(ModelHandler.calls),before)


if __name__=='__main__':unittest.main(verbosity=2)
