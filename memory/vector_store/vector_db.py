import json
from pathlib import Path
from llm.embeddings.utils import cosine

class VectorStore:
    """Small local document index. Never stores patient queries."""
    def __init__(self, path: Path):
        self.path = path
        self.rows = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        if len({r["id"] for r in self.rows}) != len(self.rows): raise ValueError("Duplicate vector IDs")
    def save(self, rows: list[dict]):
        if len({r["id"] for r in rows}) != len(rows): raise ValueError("Duplicate vector IDs")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.path)
        self.rows = rows
    def search(self, vector: list[float], allowed_ids: set[str], limit: int = 8):
        scored = [(r["id"], cosine(vector, r["vector"])) for r in self.rows if r["id"] in allowed_ids]
        return sorted(scored, key=lambda r:r[1], reverse=True)[:limit]
