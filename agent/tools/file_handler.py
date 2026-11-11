import json
from pathlib import Path

class FileHandler:
    def __init__(self, base: Path): self.base=base.resolve()
    def resolve(self, name: str) -> Path:
        path=(self.base/name).resolve()
        if not path.is_relative_to(self.base): raise PermissionError("Path outside allowed data directory")
        return path
    def read_json(self,name: str):return json.loads(self.resolve(name).read_text(encoding="utf-8"))
    def write_json(self,name: str,data):
        path=self.resolve(name);path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
