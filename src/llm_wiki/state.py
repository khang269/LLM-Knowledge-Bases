import sqlite3
import json
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from .models import RawNoteRecord, WikiArticleRecord

class StateDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=15)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock, self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS raw_notes (
                    path TEXT PRIMARY KEY,
                    content_hash TEXT,
                    status TEXT,
                    summary TEXT,
                    quality TEXT,
                    language TEXT,
                    error TEXT,
                    ingested_at TIMESTAMP
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS articles (
                    path TEXT PRIMARY KEY,
                    title TEXT,
                    sources TEXT,
                    content_hash TEXT,
                    is_draft BOOLEAN,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS concepts (
                    source_path TEXT,
                    concept_name TEXT,
                    PRIMARY KEY (source_path, concept_name)
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS stubs (
                    concept_name TEXT PRIMARY KEY
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS rejections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    concept_name TEXT,
                    feedback TEXT,
                    body TEXT,
                    rejected_at TIMESTAMP
                )
            """)

    # --- Raw Notes ---
    def upsert_raw(self, record: RawNoteRecord):
        with self._lock, self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO raw_notes (path, content_hash, status, summary, quality, language, error, ingested_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (record.path, record.content_hash, record.status, record.summary, record.quality, record.language, record.error, record.ingested_at))

    def get_raw_by_hash(self, h: str) -> Optional[RawNoteRecord]:
        with self._lock:
            cur = self.conn.execute("SELECT * FROM raw_notes WHERE content_hash = ?", (h,))
            row = cur.fetchone()
            if row:
                return RawNoteRecord(**dict(row))
            return None

    def get_raw(self, path: str) -> Optional[RawNoteRecord]:
        with self._lock:
            cur = self.conn.execute("SELECT * FROM raw_notes WHERE path = ?", (path,))
            row = cur.fetchone()
            if row:
                return RawNoteRecord(**dict(row))
            return None

    def list_raw(self, status: Optional[str] = None) -> List[RawNoteRecord]:
        with self._lock:
            if status:
                cur = self.conn.execute("SELECT * FROM raw_notes WHERE status = ?", (status,))
            else:
                cur = self.conn.execute("SELECT * FROM raw_notes")
            return [RawNoteRecord(**dict(row)) for row in cur.fetchall()]

    def mark_raw_status(self, path: str, status: str):
        with self._lock, self.conn:
            self.conn.execute("UPDATE raw_notes SET status = ? WHERE path = ?", (status, path))

    # --- Concepts ---
    def upsert_concepts(self, source_path: str, concepts: List[str]):
        with self._lock, self.conn:
            self.conn.execute("DELETE FROM concepts WHERE source_path = ?", (source_path,))
            for concept in concepts:
                self.conn.execute("INSERT INTO concepts (source_path, concept_name) VALUES (?, ?)", (source_path, concept))

    def list_all_concept_names(self) -> List[str]:
        with self._lock:
            cur = self.conn.execute("SELECT DISTINCT concept_name FROM concepts WHERE concept_name IS NOT NULL AND concept_name != ''")
            return [row["concept_name"] for row in cur.fetchall() if row["concept_name"]]

    def concepts_needing_compile(self) -> List[str]:
        """Concepts that have linked sources with status 'ingested', plus stubs."""
        with self._lock:
            cur = self.conn.execute("""
                SELECT DISTINCT c.concept_name 
                FROM concepts c
                JOIN raw_notes r ON c.source_path = r.path
                WHERE r.status = 'ingested' AND c.concept_name IS NOT NULL
                UNION
                SELECT concept_name FROM stubs WHERE concept_name IS NOT NULL
            """)
            return [row["concept_name"] for row in cur.fetchall() if row["concept_name"]]

    def get_sources_for_concept(self, concept_name: str) -> List[str]:
        with self._lock:
            cur = self.conn.execute("SELECT source_path FROM concepts WHERE concept_name = ?", (concept_name,))
            return [row["source_path"] for row in cur.fetchall()]

    def has_stub(self, concept_name: str) -> bool:
        with self._lock:
            cur = self.conn.execute("SELECT 1 FROM stubs WHERE concept_name = ?", (concept_name,))
            return bool(cur.fetchone())

    def add_stub(self, concept_name: str):
        with self._lock, self.conn:
            self.conn.execute("INSERT OR IGNORE INTO stubs (concept_name) VALUES (?)", (concept_name,))

    def delete_stub(self, concept_name: str):
        with self._lock, self.conn:
            self.conn.execute("DELETE FROM stubs WHERE concept_name = ?", (concept_name,))

    # --- Articles ---
    def upsert_article(self, record: WikiArticleRecord):
        now = datetime.now()
        sources_json = json.dumps(record.sources)
        with self._lock, self.conn:
            cur = self.conn.execute("SELECT created_at FROM articles WHERE path = ?", (record.path,))
            existing = cur.fetchone()
            created_at = existing["created_at"] if existing else now
            self.conn.execute("""
                INSERT OR REPLACE INTO articles (path, title, sources, content_hash, is_draft, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (record.path, record.title, sources_json, record.content_hash, record.is_draft, created_at, now))

    def get_article(self, path: str) -> Optional[WikiArticleRecord]:
        with self._lock:
            cur = self.conn.execute("SELECT * FROM articles WHERE path = ?", (path,))
            row = cur.fetchone()
            if row:
                d = dict(row)
                d["sources"] = json.loads(d["sources"])
                return WikiArticleRecord(**d)
            return None

    def list_articles(self, drafts_only: bool = False) -> List[WikiArticleRecord]:
        with self._lock:
            q = "SELECT * FROM articles"
            if drafts_only:
                q += " WHERE is_draft = 1"
            cur = self.conn.execute(q)
            res = []
            for row in cur.fetchall():
                d = dict(row)
                d["sources"] = json.loads(d["sources"])
                res.append(WikiArticleRecord(**d))
            return res

    def publish_article(self, draft_path: str, target_path: str):
        with self._lock, self.conn:
            self.conn.execute("UPDATE articles SET path = ?, is_draft = 0, updated_at = ? WHERE path = ?", (target_path, datetime.now(), draft_path))

    def delete_article(self, path: str):
        with self._lock, self.conn:
            self.conn.execute("DELETE FROM articles WHERE path = ?", (path,))

    def approve_article(self, path: str, notes: str = ""):
        with self._lock, self.conn:
            self.conn.execute("UPDATE articles SET is_draft = 0, updated_at = ? WHERE path = ?", (datetime.now(), path))

    # --- Rejections ---
    def add_rejection(self, concept_name: str, feedback: str, body: str = ""):
        with self._lock, self.conn:
            self.conn.execute("INSERT INTO rejections (concept_name, feedback, body, rejected_at) VALUES (?, ?, ?, ?)", (concept_name, feedback, body, datetime.now()))

    def get_rejections(self, concept_name: str, limit: int = 3) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self.conn.execute("SELECT * FROM rejections WHERE concept_name = ? ORDER BY rejected_at DESC LIMIT ?", (concept_name, limit))
            return [dict(row) for row in cur.fetchall()]
