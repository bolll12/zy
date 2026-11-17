"""家目录不参与测试；上传、索引和导出均在临时工作区验证。"""
import base64
import io
import json
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from urllib import request, error
from xml.etree import ElementTree

import server
from exporter import word_document
from knowledge import KnowledgeStore
from storage import Store


def sample_pdf():
    stream = b'BT /F1 12 Tf 50 690 Td (Knowledge source and reference evidence.) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'\nendstream']
    output = b'%PDF-1.4\n'
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output += f'{number} 0 obj\n'.encode() + obj + b'\nendobj\n'
    xref = len(output)
    rows = ''.join(f'{offset:010d} 00000 n \n' for offset in offsets[1:])
    return output + f'xref\n0 6\n0000000000 65535 f \n{rows}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()


class KnowledgeTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        previous = server.STORE, server.KNOWLEDGE, server.LIBRARY
        self.addCleanup(lambda: self.restore(previous))
        server.STORE = Store(self.root)
        server.KNOWLEDGE = KnowledgeStore(self.root)
        server.LIBRARY = server.Library()
        httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.base = 'http://127.0.0.1:' + str(httpd.server_port)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)

    @staticmethod
    def restore(previous):
        server.STORE, server.KNOWLEDGE, server.LIBRARY = previous

    def call(self, path, body=None, headers=None):
        req = request.Request(self.base + path,
                              data=None if body is None else json.dumps(body).encode(),
                              headers=headers if headers is not None else {'Content-Type':'application/json', 'X-Requested-With':'Zhiyan'})
        try:
            response = request.urlopen(req, timeout=20)
        except error.HTTPError as exc:
            response = exc
        with response:
            return response.status, response.read(), response.headers

    def json(self, path, body=None, status=200):
        code, raw, _ = self.call(path, body)
        self.assertEqual(code, status, raw.decode(errors='replace'))
        return json.loads(raw)

    def upload(self, filename, raw, status=200):
        return self.json('/api/knowledge/upload', {'filename':filename, 'content':base64.b64encode(raw).decode()}, status)

    def test_upload_search_original_and_restart(self):
        self.assertEqual(self.json('/api/bootstrap')['stats']['documents'], 0)
        raw = '项目续约率以确认签约为准。\n\n示例中，项目续约率为百分之八十，按已到期项目计算。'.encode()
        paper = self.upload('项目规则.md', raw)['paper']; paper_id = paper['id']
        self.assertEqual(paper['source_unit'], '段')
        self.assertEqual(self.upload('同内容.txt', raw)['paper']['id'], paper_id)
        self.assertEqual(self.json('/api/bootstrap')['stats']['documents'], 1)
        hits = self.json('/api/search', {'query':'项目续约率', 'topic':'自建知识'})['hits']
        self.assertTrue(hits and all(h['paper_id'] == paper_id for h in hits))
        evidence = self.json('/api/research', {'question':'本单位今年的项目续约率是多少？'})
        self.assertIn(f'[{paper_id}·第2段]', evidence['answer'])
        note = '保存证据后核对原文。'
        self.json(f'/api/papers/{paper_id}/note', {'note':note,'status':'已读'})
        self.json('/api/collection', {'chunk_id':hits[0]['chunk_id'],'selected':True})
        self.assertEqual(self.json('/api/collection')[0]['source_unit'], '段')
        server.KNOWLEDGE = KnowledgeStore(self.root)
        server.LIBRARY = server.Library(server.KNOWLEDGE.records())
        self.assertEqual(self.json('/api/bootstrap')['papers'][0]['note'], note)
        self.assertIn('百分之八十', self.json(f'/api/papers/{paper_id}/page?page=2')['text'])
        status, original, headers = self.call(f'/api/knowledge/{paper_id}/original')
        self.assertEqual((status, original), (200, raw))
        self.assertIn('attachment', headers['Content-Disposition'])

    def test_pdf_docx_text_and_invalid_files(self):
        pdf = self.upload('sample.pdf', sample_pdf())['paper']; self.assertEqual(pdf['source_unit'], '页')
        self.assertIn('Knowledge source', self.json(f"/api/papers/{pdf['id']}/page")['text'])
        word = self.upload('word.docx', word_document('可核对的原始证据。'))['paper']
        self.assertIn('可核对', self.json(f"/api/papers/{word['id']}/page?page=2")['text'])
        text = self.upload('text.txt', '文本按段定位。'.encode('gb18030'))['paper']
        self.assertEqual(text['source_unit'], '段')
        for name, raw in [('损坏.docx', b'docx'), ('invalid.pdf', b'PDF'), ('空白.txt', b'\n '), ('../path.txt', b'file')]:
            self.assertIn('error', self.upload(name, raw, 400))
        self.assertEqual(self.json('/api/bootstrap')['stats']['documents'], 3)

    def test_draft_conflict_export_and_origin(self):
        initial = self.json('/api/draft')
        text = '# 研究综述\n\n这是可导出的正文。'
        self.json('/api/draft', {'text':text,'revision':initial['revision']})
        self.json('/api/draft', {'text':'旧版本','revision':initial['revision']}, 409)
        code, blob, _ = self.call('/api/export?format=docx')
        self.assertEqual(code, 200)
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            doc = archive.read('word/document.xml')
            ElementTree.fromstring(doc)
            self.assertIn('这是可导出的正文', doc.decode())
        code, _, _ = self.call('/api/knowledge/upload', {}, {'Content-Type':'application/json','X-Requested-With':'Zhiyan','Origin':'https://example.invalid'})
        self.assertEqual(code, 403)
