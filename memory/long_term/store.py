import json
import sqlite3
from pathlib import Path

class LongTermStore:
    """Opt-in only. Caller must provide an anonymized case and explicit consent."""
    def __init__(self, path: Path, enabled: bool = False): self.path, self.enabled = path, enabled
    def save(self, case_id: str, data: dict, consent: bool = False):
        if not self.enabled or not consent: raise PermissionError("Persistent case storage is disabled or consent missing")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, data TEXT NOT NULL)")
            db.execute("INSERT OR REPLACE INTO cases VALUES (?,?)", (case_id, json.dumps(data,ensure_ascii=False)))
    def load(self, case_id: str):
        if not self.enabled: raise PermissionError("Persistent storage disabled")
        if not self.path.exists(): return None
        with sqlite3.connect(self.path) as db: row = db.execute("SELECT data FROM cases WHERE id=?", (case_id,)).fetchone()
        return json.loads(row[0]) if row else None
