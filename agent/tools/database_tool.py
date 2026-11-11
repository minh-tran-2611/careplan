import sqlite3
from pathlib import Path

class DatabaseTool:
    """Read-only case lookup; not exposed to model-generated SQL."""
    def __init__(self,path:Path):self.path=path.resolve()
    def get_case(self,case_id:str):
        if not self.path.exists(): return None
        with sqlite3.connect(self.path.as_uri()+"?mode=ro",uri=True) as db:
            row=db.execute("SELECT data FROM cases WHERE id=?",(case_id,)).fetchone()
            return row[0] if row else None
