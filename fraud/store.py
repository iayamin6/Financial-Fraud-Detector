import sqlite3
from pathlib import Path
from contextlib import contextmanager

class Store:
    def __init__(self,path):
        self.path=str(path); Path(path).parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('''
              PRAGMA journal_mode=WAL;
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
