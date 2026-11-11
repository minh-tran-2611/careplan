from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import os
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    root: Path
    provider: str
    model: str
    base_url: str
    api_key: str
    timeout_seconds: float
    max_tokens: int
    corpus_path: Path
    vector_index_path: Path
    embedding_model: str
    embedding_base_url: str
    embedding_api_key: str = ""
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "nursing_nemotron35_8b_v1"
    top_k: int = 8
    max_context_characters: int = 18000
    max_turns: int = 6
    persist_cases: bool = False

@lru_cache
def get_settings() -> Settings:
    load_dotenv(ROOT / ".env", override=False)
    conf = yaml.safe_load((ROOT / "config/config.yaml").read_text(encoding="utf-8"))
    llm, retrieval = conf["llm"], conf["retrieval"]
    provider = os.getenv("LLM_PROVIDER", llm["provider"])
    key_name = {"nvidia": "NVIDIA_API_KEY", "openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "local": "LOCAL_API_KEY"}.get(provider, "NVIDIA_API_KEY")
    return Settings(root=ROOT, provider=provider, model=os.getenv("LLM_MODEL", llm["model"]),
        base_url=os.getenv("LLM_BASE_URL", llm["base_url"]).rstrip("/"), api_key=os.getenv(key_name, ""),
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", llm["timeout_seconds"])), max_tokens=llm["max_tokens"],
        corpus_path=ROOT / retrieval["corpus_path"], vector_index_path=ROOT / retrieval["vector_index_path"],
        embedding_model=os.getenv("EMBEDDING_MODEL", ""), embedding_base_url=os.getenv("EMBEDDING_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/"),
        embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""), qdrant_url=os.getenv("QDRANT_URL", "").rstrip("/"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY", ""), qdrant_collection=os.getenv("QDRANT_COLLECTION", "nursing_nemotron35_8b_v1"),
        top_k=retrieval["top_k"], max_context_characters=retrieval["max_context_characters"], max_turns=conf["memory"]["max_turns"],
        persist_cases=os.getenv("ENABLE_LONG_TERM_MEMORY", "false").lower() == "true")
