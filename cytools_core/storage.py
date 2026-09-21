import json
import sqlite3
import threading
from pathlib import Path
from .errors import CyToolError


class RuntimeLock:
    """OS-managed SQLite lock, released even after process death; no stale PID file."""
    def __init__(self, path):
        self.db = sqlite3.connect(path, timeout=0, check_same_thread=False)
        try:
            self.db.execute('BEGIN EXCLUSIVE')
        except sqlite3.OperationalError as exc:
            self.db.close()
            raise CyToolError('Busy', 'Data directory already owned by another runtime') from exc

    def close(self):
        self.db.rollback()
        self.db.close()


class Store:
    """One connection per runtime, serialized transactions and crash-safe metadata."""
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT, value TEXT, PRIMARY KEY(kind,id))')
        self.db.commit()

    def put(self, kind, identifier, value):
        data = json.dumps(value, allow_nan=False)
        with self.lock, self.db:
            self.db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)', (kind, identifier, data))

    def all(self, kind):
        with self.lock:
            return {key:json.loads(value) for key,value in self.db.execute('SELECT id,value FROM records WHERE kind=?',(kind,))}

    def close(self):
        with self.lock:
            self.db.close()
