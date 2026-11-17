"""将阅读笔记、证据、综述及操作记录保存在当前系统目录。"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


class Store:
    def __init__(self, root):
        self.path = root / 'user_data' / 'research.sqlite3'
        self.path.parent.mkdir(exist_ok=True)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS notes (paper_id TEXT PRIMARY KEY, note TEXT NOT NULL, status TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evidence (chunk_id TEXT PRIMARY KEY, created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS draft (id INTEGER PRIMARY KEY, text TEXT NOT NULL, revision INTEGER NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, data TEXT NOT NULL, created TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, detail TEXT NOT NULL, created TEXT NOT NULL);
            ''')
            draft = root / 'data/initial_review.md'
            initial = draft.read_text(encoding='utf-8') if draft.is_file() else '# 研究综述\n'
            db.execute('INSERT OR IGNORE INTO draft VALUES (1, ?, 1, ?)', (initial, now()))

    @contextmanager
    def db(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def event(self, kind, detail):
        with self.db() as db:
            db.execute('INSERT INTO events (kind, detail, created) VALUES (?, ?, ?)', (kind, detail[:1200], now()))

    def notes(self):
        with self.db() as db:
            return {x['paper_id']: dict(x) for x in db.execute('SELECT * FROM notes')}

    def save_note(self, paper_id, note, status):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO notes VALUES (?, ?, ?, ?)', (paper_id, note, status, now()))
        self.event('阅读笔记', paper_id + ' · ' + status)

    def collection(self):
        with self.db() as db:
            return [dict(x) for x in db.execute('SELECT * FROM evidence ORDER BY created DESC, chunk_id')]

    def collect(self, chunk_id, selected):
        with self.db() as db:
            if selected:
                db.execute('INSERT OR IGNORE INTO evidence VALUES (?, ?)', (chunk_id, now()))
            else:
                db.execute('DELETE FROM evidence WHERE chunk_id = ?', (chunk_id,))
        self.event('证据收藏' if selected else '取消收藏', chunk_id)

    def draft(self):
        with self.db() as db:
            return dict(db.execute('SELECT * FROM draft WHERE id = 1').fetchone())

    def save_draft(self, text, revision):
        stamp = now()
        with self.db() as db:
            count = db.execute('UPDATE draft SET text = ?, revision = revision + 1, updated = ? WHERE id = 1 AND revision = ?', (text, stamp, revision)).rowcount
            if not count:
                return None
            result = dict(db.execute('SELECT revision, updated FROM draft WHERE id = 1').fetchone())
        return result

    def add_run(self, result):
        stamp = now()
        with self.db() as db:
            cur = db.execute('INSERT INTO runs (data, created) VALUES (?, ?)', (json.dumps(result, ensure_ascii=False), stamp))
            run_id = cur.lastrowid
        self.event('研究问答', result['question'] + ' · ' + result['mode_label'])
        return {**result, 'id': run_id, 'created': stamp}

    def runs(self):
        with self.db() as db:
            return [{**json.loads(x['data']), 'id': x['id'], 'created': x['created']} for x in db.execute('SELECT * FROM runs ORDER BY id DESC LIMIT 50')]

    def events(self):
        with self.db() as db:
            return [dict(x) for x in db.execute('SELECT * FROM events ORDER BY id DESC LIMIT 200')]
