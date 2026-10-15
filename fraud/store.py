import sqlite3
from pathlib import Path
from contextlib import contextmanager

class Store:
    def __init__(self,path):
        self.path=str(path); Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                transaction_id TEXT NOT NULL UNIQUE REFERENCES scores(transaction_id),
                status TEXT NOT NULL DEFAULT 'open',
                assigned_to TEXT,
                outcome TEXT,
                revision INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
              );
              CREATE TABLE IF NOT EXISTS case_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL REFERENCES cases(case_id),
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                detail_json TEXT NOT NULL,
                created_at TEXT NOT NULL
              );
              CREATE TABLE IF NOT EXISTS investigations (
                run_id TEXT PRIMARY KEY,
                case_id TEXT NOT NULL REFERENCES cases(case_id),
                status TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
              );
              CREATE TABLE IF NOT EXISTS scores (
                transaction_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                request_json TEXT NOT NULL,
                result_json TEXT NOT NULL,
                explanation_json TEXT
              );
              CREATE INDEX IF NOT EXISTS scores_timestamp ON scores(timestamp);
              CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT NOT NULL REFERENCES scores(transaction_id),
                correct_label INTEGER NOT NULL CHECK(correct_label IN (0,1)),
                classification TEXT NOT NULL,
                comment TEXT,
                created_at TEXT NOT NULL
              );
            ''')
    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()
