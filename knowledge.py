"""解析并保存用户知识文档；原文件、定位文本和索引片段在同一事务中提交。"""
import hashlib
import io
import json
import re
import sqlite3
import subprocess
import sys
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 2000000
FORMATS = {'.pdf', '.docx', '.txt', '.md'}
PAPER_ID = r'(?:[CE]\d{2}|U\d{6,})'


def clean_text(text):
    return ''.join(c for c in text.replace('\r\n', '\n').replace('\r', '\n')
                   if c in '\n\t' or not unicodedata.category(c).startswith('C')).strip()


def text_segments(text):
    """按空行划分文本段，过长段落再拆分；段号不冒充打印页码。"""
    parts = re.split(r'\n\s*\n', clean_text(text))
    return [part[start:start + 1600].strip() for part in parts if part.strip()
            for start in range(0, len(part), 1600)]


def extract(blob, suffix):
    if suffix == '.pdf':
        if not blob.startswith(b'%PDF-'):
            raise ValueError('文件不是有效的PDF，请检查后重试。')
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ValueError('未安装PDF解析依赖，请在启动系统所用的Python中安装 requirements.txt。') from None
        try:
            reader = PdfReader(io.BytesIO(blob))
            if reader.is_encrypted:
                raise ValueError('暂不支持加密PDF，请先导出未加密版本。')
            if len(reader.pages) > 1000:
                raise ValueError('PDF超过1000页，请拆分后上传。')
            texts, count = [], 0
            for page in reader.pages:
                text = clean_text(page.extract_text() or '')
                count += len(text)
                if count > MAX_CHARS:
                    raise ValueError('文本超过200万字符，请拆分后上传。')
                texts.append(text)
        except ValueError:
            raise
        except Exception:
            raise ValueError('PDF无法解析，请确认文件完整并包含可复制文字。') from None
        unit = '页'
    elif suffix == '.docx':
        try:
            with zipfile.ZipFile(io.BytesIO(blob)) as archive:
                infos = archive.infolist()
                if len(infos) > 3000 or sum(i.file_size for i in infos) > 50 * 1024 * 1024:
                    raise ValueError('Word解压后过大，请精简或拆分后上传。')
                xml = archive.read('word/document.xml')
            if b'<!DOCTYPE' in xml.upper() or b'<!ENTITY' in xml.upper():
                raise ValueError('Word包含不支持的XML内容，请重新另存为DOCX。')
            root = ET.fromstring(xml)
            ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            paragraphs = []
            for paragraph in root.iter(ns + 'p'):
                text = ''.join(node.text or '' if node.tag == ns + 't' else
                               '\t' if node.tag == ns + 'tab' else '\n'
                               if node.tag in [ns + 'br', ns + 'cr'] else ''
                               for node in paragraph.iter())
                if text.strip():
                    paragraphs.append(text)
            texts = text_segments('\n\n'.join(paragraphs))
        except ValueError:
            raise
        except Exception:
            raise ValueError('Word无法解析，请使用完整的DOCX文件；旧版DOC请先另存为DOCX。') from None
        unit = '段'
    else:
        if b'\x00' in blob[:4096] and not blob.startswith((b'\xff\xfe', b'\xfe\xff')):
            raise ValueError('文件包含二进制内容，请使用纯文本文件。')
        encodings = ['utf-16'] if blob.startswith((b'\xff\xfe', b'\xfe\xff')) else ['utf-8-sig', 'gb18030']
        for encoding in encodings:
            try:
                text = blob.decode(encoding)
                break
            except UnicodeError:
                continue
        else:
            raise ValueError('无法识别文本编码，请另存为UTF-8后上传。')
        texts, unit = text_segments(text), '段'
    count = sum(len(t) for t in texts)
    if count > MAX_CHARS:
        raise ValueError('文本超过200万字符，请拆分后上传。')
    if not any(re.search(r'[\w\u4e00-\u9fff]', t) for t in texts):
        raise ValueError('没有提取到可检索文字。扫描PDF请先做文字识别（OCR），图片或空白文件无法导入。')
    return {'pages': [{'page': i + 1, 'text': t} for i, t in enumerate(texts)],
            'source_unit': unit, 'chars': count}


def parse_document(blob, suffix):
    """在有限时长的独立进程中解析，异常文件不会阻塞HTTP服务。"""
    try:
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--extract', suffix],
                                input=blob, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=45)
        payload = json.loads(result.stdout)
    except subprocess.TimeoutExpired:
        raise ValueError('文档解析超时，请拆分文档或导出为文本后重试。') from None
    except (ValueError, OSError):
        raise ValueError('文档解析失败，请检查文件是否完整。') from None
    if result.returncode or 'error' in payload:
        raise ValueError(payload.get('error', '文档解析失败，请检查文件。'))
    return payload


class KnowledgeStore:
    def __init__(self, root):
        self.path = Path(root) / 'user_data' / 'knowledge.sqlite3'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS documents (
                seq INTEGER PRIMARY KEY AUTOINCREMENT, sha256 TEXT UNIQUE NOT NULL,
                filename TEXT NOT NULL, suffix TEXT NOT NULL, created TEXT NOT NULL,
                paper TEXT NOT NULL, pages TEXT NOT NULL, chunks TEXT NOT NULL,
                original BLOB NOT NULL)''')

    def connect(self):
        db = sqlite3.connect(str(self.path), timeout=30)
        db.row_factory = sqlite3.Row
        return db

    def records(self):
        with self.connect() as db:
            return [{'paper': json.loads(r['paper']), 'pages': json.loads(r['pages']),
                     'chunks': json.loads(r['chunks'])}
                    for r in db.execute('SELECT paper,pages,chunks FROM documents ORDER BY seq')]

    def find_hash(self, digest):
        with self.connect() as db:
            row = db.execute('SELECT paper FROM documents WHERE sha256=?', (digest,)).fetchone()
            return json.loads(row['paper']) if row else None

    def source(self, paper_id):
        with self.connect() as db:
            row = db.execute('SELECT filename,suffix,original FROM documents WHERE seq=?',
                             (int(paper_id[1:]),)).fetchone()
            return dict(row) if row else None

    def add(self, filename, blob, parsed, title='', topic='自建知识', language='自动识别'):
        digest = hashlib.sha256(blob).hexdigest()
        suffix = Path(filename).suffix.lower()
        created = datetime.now(timezone.utc).isoformat()
        sample = '\n'.join(p['text'] for p in parsed['pages'])[:20000]
        if language == '自动识别':
            language = '中文' if len(re.findall(r'[\u4e00-\u9fff]', sample)) >= max(1, len(re.findall(r'[a-zA-Z]', sample)) * .15) else '英文'
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            existing = db.execute('SELECT paper FROM documents WHERE sha256=?', (digest,)).fetchone()
            if existing:
                return {'paper': json.loads(existing['paper']), 'duplicate': True}
            cursor = db.execute('INSERT INTO documents(sha256,filename,suffix,created,paper,pages,chunks,original) VALUES(?,?,?,?,?,?,?,?)',
                                (digest, filename, suffix, created, '{}', '[]', '[]', blob))
            paper_id = 'U' + str(cursor.lastrowid).zfill(6)
            title = title.strip() or Path(filename).stem
            paper = {'id': paper_id, 'title': title, 'display_title': title, 'authors': ['用户上传'],
                     'date': created[:10], 'year': int(created[:4]), 'language': language, 'topic': topic,
                     'pages': len(parsed['pages']), 'source_unit': parsed['source_unit'], 'chars': parsed['chars'],
                     'filename': filename, 'format': suffix[1:].upper(), 'bytes': len(blob), 'uploaded': True,
                     'created': created, 'sha256': digest, 'status': '全文已解析并加入检索',
                     'review': '这份资料由用户上传，尚未撰写人工评述。可先核对原文，再在下方记录阅读笔记。',
                     'pdf_url_local': '/api/knowledge/' + paper_id + '/original', 'url': ''}
            chunks = []
            for page in parsed['pages']:
                for n, start in enumerate(range(0, len(page['text']), 720), 1):
                    text = page['text'][start:start + 900].strip()
                    if not text:
                        continue
                    chunks.append({'chunk_id': f"{paper_id}-p{page['page']}-{n}", 'paper_id': paper_id,
                                   'title': title, 'page': page['page'], 'text': text, 'language': language,
                                   'source_unit': parsed['source_unit'], 'url': paper['pdf_url_local']})
            paper['chunks'] = len(chunks)
            db.execute('UPDATE documents SET paper=?,pages=?,chunks=? WHERE seq=?',
                       (json.dumps(paper, ensure_ascii=False), json.dumps(parsed['pages'], ensure_ascii=False),
                        json.dumps(chunks, ensure_ascii=False), cursor.lastrowid))
        return {'paper': paper, 'duplicate': False}


if __name__ == '__main__' and len(sys.argv) == 3 and sys.argv[1] == '--extract':
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (35, 35))
        except (ImportError, ValueError, OSError):
            pass
        value = extract(sys.stdin.buffer.read(MAX_BYTES + 1), sys.argv[2])
    except Exception as exc:
        value = {'error': str(exc) if isinstance(exc, ValueError) else '无法解析文档，请检查格式和文件内容。'}
    print(json.dumps(value, ensure_ascii=False))
