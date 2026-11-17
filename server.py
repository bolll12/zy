"""启动知研本地文献研究系统，仅监听本机地址。"""
import argparse
import base64
import binascii
import hashlib
import json
import mimetypes
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from engine import Library, TOPICS
from exporter import word_document
from storage import Store
from browser_util import open_browser
from model_client import DEFAULT_BASE_URL, DEFAULT_MODEL, test_connection
from knowledge import KnowledgeStore, MAX_BYTES, FORMATS, PAPER_ID, parse_document

ROOT = Path(__file__).resolve().parent
KNOWLEDGE = KnowledgeStore(ROOT)
LIBRARY = Library(KNOWLEDGE.records())
STORE = Store(ROOT)
UPLOAD_LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    server_version = 'Zhiyan/1.0'

    def log_message(self, fmt, *args):
        # 不将问题、笔记、API密钥等请求内容写入终端。
        pass

    def send_bytes(self, body, content_type, status=200, filename=None):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store' if content_type.startswith('application/json') else 'no-cache')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        if filename:
            self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(filename))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def json(self, obj, status=200):
        self.send_bytes(json.dumps(obj, ensure_ascii=False).encode(), 'application/json; charset=utf-8', status)

    def valid_host(self):
        return self.headers.get('Host', '') in ['127.0.0.1:' + str(self.server.server_port), 'localhost:' + str(self.server.server_port)]

    def do_GET(self):
        if not self.valid_host():
            return self.json({'error': '请通过本机地址访问。'}, 403)
        try:
            self.route_get()
        except (ValueError, KeyError, TypeError):
            self.json({'error': '请求参数不正确。'}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.json({'error': '读取失败，请重试。'}, 500)

    def do_HEAD(self):
        self.do_GET()

    def route_get(self):
        library = LIBRARY
        u = urlparse(self.path)
        q = parse_qs(u.query)
        path = unquote(u.path)
        if path == '/api/bootstrap':
            notes = STORE.notes()
            papers = [{**p, 'note': notes.get(p['id'], {}).get('note', ''), 'reading_status': notes.get(p['id'], {}).get('status', '未读')} for p in library.papers.values()]
            return self.json({'papers': papers, 'stats': library.manifest, 'topics': list(TOPICS) + ['自建知识'],
                              'collection': STORE.collection()})
        if path == '/api/health':
            return self.json({'ok': True, 'app': '知研', 'documents': len(library.papers), 'chunks': len(library.chunks), 'instance': hashlib.sha256(str(ROOT).encode()).hexdigest()[:16]})
        if path == '/api/draft':
            return self.json(STORE.draft())
        if path == '/api/history':
            return self.json(STORE.runs())
        if path == '/api/events':
            return self.json(STORE.events())
        if path == '/api/collection':
            return self.json([{**library.chunks[x['chunk_id']], 'created': x['created'], 'display_title': library.papers[library.chunks[x['chunk_id']]['paper_id']]['display_title']} for x in STORE.collection() if x['chunk_id'] in library.chunks])
        match = re.fullmatch(r'/api/knowledge/(U\d{6,})/original', path)
        if match:
            source = KNOWLEDGE.source(match[1])
            if not source:
                return self.json({'error': '未找到上传的原文。'}, 404)
            STORE.event('查看原文', match[1])
            content_type = mimetypes.guess_type('file' + source['suffix'])[0] or 'application/octet-stream'
            return self.send_bytes(source['original'], content_type, filename=None if source['suffix'] == '.pdf' else source['filename'])
        match = re.fullmatch(r'/api/papers/(' + PAPER_ID + r')/page', path)
        if match and match[1] in library.papers:
            number = int(q.get('page', ['1'])[0])
            page = library.page(match[1], number)
            return self.json(page if page else {'error': '没有这一页。'}, 200 if page else 404)
        if path == '/api/export':
            fmt = q.get('format', ['md'])[0]
            if fmt == 'json':
                payload = {'notes': STORE.notes(), 'evidence': STORE.collection(), 'draft': STORE.draft(), 'history': STORE.runs(), 'events': STORE.events()}
                body = json.dumps(payload, ensure_ascii=False, indent=2).encode()
                content_type = 'application/json; charset=utf-8'
                name = '知研_研究记录.json'
            elif fmt in ['md', 'docx']:
                text = STORE.draft()['text']
                body = word_document(text) if fmt == 'docx' else text.encode()
                content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if fmt == 'docx' else 'text/markdown; charset=utf-8'
                name = '知研_文献综述.' + fmt
            else:
                return self.json({'error': '不支持此导出格式。'}, 400)
            STORE.event('导出文件', name)
            return self.send_bytes(body, content_type, filename=name)
        match = re.fullmatch(r'/papers/([CE]\d{2})\.pdf', path)
        if match and match[1] in library.papers:
            target = ROOT / library.papers[match[1]]['file']
            STORE.event('查看原文', match[1])
            return self.send_bytes(target.read_bytes(), 'application/pdf')
        if path.startswith('/api/') or path.startswith('/papers/') or path.startswith('/documents/'):
            return self.json({'error': '未找到。'}, 404)
        target = (ROOT / 'web' / path.lstrip('/')).resolve()
        web = (ROOT / 'web').resolve()
        if not str(target).startswith(str(web) + os.sep) and target != web:
            return self.json({'error': '无效路径。'}, 403)
        if path == '/' or (not target.exists() and '.' not in Path(path).name):
            target = web / 'index.html'
        if not target.is_file():
            return self.json({'error': '未找到文件。'}, 404)
        self.send_bytes(target.read_bytes(), (mimetypes.guess_type(str(target))[0] or 'application/octet-stream') + ('; charset=utf-8' if target.suffix in ['.html', '.js', '.css'] else ''))

    def do_POST(self):
        expected = 'http://' + self.headers.get('Host', '')
        if not self.valid_host() or self.headers.get('Origin', expected) != expected or self.headers.get('X-Requested-With') != 'Zhiyan':
            return self.json({'error': '请求来源不正确。'}, 403)
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            return self.json({'error': '需要JSON请求。'}, 415)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            maximum = (MAX_BYTES * 4 // 3 + 100000) if urlparse(self.path).path == '/api/knowledge/upload' else 2000000
            if not 0 < size <= maximum:
                return self.json({'error': '请求过大或为空。'}, 413)
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict):
                raise ValueError('无效请求。')
            self.route_post(urlparse(self.path).path, body)
        except (ValueError, TypeError, KeyError) as exc:
            self.json({'error': str(exc) if isinstance(exc, ValueError) else '请求参数不正确。'}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.json({'error': '保存或执行失败，请重试；已有内容不会删除。'}, 500)

    def route_post(self, path, body):
        global LIBRARY
        library = LIBRARY
        if path == '/api/knowledge/upload':
            filename = body.get('filename', '')
            title = body.get('title', '')
            topic = body.get('topic', '自建知识')
            language = body.get('language', '自动识别')
            if not isinstance(filename, str) or not filename.strip() or len(filename) > 240 or any(c in filename for c in '/\\\x00\r\n'):
                raise ValueError('文件名不正确，请使用不含路径的文件名。')
            suffix = Path(filename).suffix.lower()
            if suffix not in FORMATS:
                raise ValueError('支持PDF、DOCX、TXT和MD；旧版DOC请先另存为DOCX。')
            if not isinstance(title, str) or len(title) > 200 or topic not in list(TOPICS) + ['自建知识'] or language not in ['自动识别', '中文', '英文']:
                raise ValueError('资料标题、主题或语种参数不正确。')
            encoded = body.get('content', '')
            if not isinstance(encoded, str) or len(encoded) > MAX_BYTES * 4 // 3 + 8:
                raise ValueError('单个文件最大10MB，请拆分后上传。')
            try:
                blob = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError('文件内容不完整，请重新选择文件。') from None
            if not blob or len(blob) > MAX_BYTES:
                raise ValueError('文件为空或超过10MB，请检查后上传。')
            digest = hashlib.sha256(blob).hexdigest()
            existing = next((p for p in library.papers.values() if p.get('sha256') == digest), None)
            if existing:
                return self.json({'paper': existing, 'duplicate': True})
            parsed = parse_document(blob, suffix)
            with UPLOAD_LOCK:
                result = KNOWLEDGE.add(filename, blob, parsed, title, topic, language)
                if not result['duplicate']:
                    # 以完整新快照替换；同时进行的检索可继续使用旧快照。
                    LIBRARY = Library(KNOWLEDGE.records())
                    STORE.event('上传知识', result['paper']['id'] + ' · ' + result['paper']['display_title'] + ' · ' + str(result['paper']['chunks']) + '个片段')
            return self.json(result)
        if path == '/api/model/test':
            return self.json(test_connection(body.get('base_url', DEFAULT_BASE_URL),
                                             body.get('model', DEFAULT_MODEL), body.get('api_key', '')))
        if path == '/api/search':
            query = str(body.get('query', '')).strip()[:600]
            if not query:
                raise ValueError('请输入检索内容。')
            paper_ids = body.get('paper_ids')
            if paper_ids is not None and (not isinstance(paper_ids, list) or any(x not in library.papers for x in paper_ids)):
                raise ValueError('文献范围不正确。')
            result = library.search(query, str(body.get('language', '')), str(body.get('topic', '')), min(20, max(1, int(body.get('limit', 10)))), paper_ids)
            STORE.event('全文检索', query + ' · ' + str(len(result['hits'])) + '个片段')
            return self.json(result)
        if path == '/api/research':
            question = str(body.get('question', '')).strip()[:600]
            if len(question) < 2:
                raise ValueError('请写下你要研究的问题。')
            mode = body.get('mode', 'local')
            if mode not in ['local', 'deepseek', 'api']:
                raise ValueError('模式不正确。')
            paper_ids = body.get('paper_ids')
            if paper_ids is not None and (not isinstance(paper_ids, list) or any(x not in library.papers for x in paper_ids)):
                raise ValueError('文献范围不正确。')
            result = library.research(question, mode, body.get('api_key', ''), body.get('model', DEFAULT_MODEL),
                                      paper_ids, body.get('base_url', DEFAULT_BASE_URL))
            return self.json(STORE.add_run(result))
        match = re.fullmatch(r'/api/papers/(' + PAPER_ID + r')/note', path)
        if match and match[1] in library.papers:
            note = str(body.get('note', ''))[:30000]
            status = body.get('status', '未读')
            if status not in ['未读', '阅读中', '已读']:
                raise ValueError('阅读状态不正确。')
            STORE.save_note(match[1], note, status)
            return self.json({'ok': True})
        if path == '/api/collection':
            chunk_id = str(body.get('chunk_id', ''))
            if chunk_id not in library.chunks or not isinstance(body.get('selected'), bool):
                raise ValueError('证据参数不正确。')
            STORE.collect(chunk_id, body['selected'])
            return self.json({'ok': True, 'collection': STORE.collection()})
        if path == '/api/draft':
            text = body.get('text')
            revision = body.get('revision')
            if not isinstance(text, str) or len(text) > 300000 or not isinstance(revision, int):
                raise ValueError('正文过长或版本参数不正确。')
            result = STORE.save_draft(text, revision)
            if result is None:
                return self.json({'error': '其他窗口已更新正文。当前输入仍在页面中，请先复制保存，再重新载入最新版本。'}, 409)
            return self.json(result)
        return self.json({'error': '未找到操作。'}, 404)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8878)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    url = 'http://127.0.0.1:' + str(args.port)
    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
        server.daemon_threads = True
    except OSError as exc:
        if exc.errno in [1, 13]:
            print('当前环境未允许本机网络服务，请先开放本地网络访问权限。')
        else:
            print('端口已被占用。请查看已有窗口，或使用 --port 8879 启动。')
        raise SystemExit(1)
    if not (ROOT / 'web/index.html').exists():
        print('缺少界面构建文件，请在frontend目录运行npm run build。')
        raise SystemExit(1)
    print('知研 · Agent文献研究系统\n' + url + '\n关闭终端窗口或按Control+C停止。', flush=True)
    if args.open:
        open_browser(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
