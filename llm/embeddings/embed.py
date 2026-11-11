import httpx
import math
from contextlib import nullcontext
from llm.providers.openai import ProviderError

class EmbeddingClient:
    def __init__(self, settings, http_client=None): self.settings = settings; self.http_client = http_client
    async def embed(self, texts: list[str], input_type: str = "query") -> list[list[float]]:
        if not self.settings.embedding_model: raise ProviderError("Chưa cấu hình EMBEDDING_MODEL.", "EMBEDDING_NOT_CONFIGURED")
        if input_type not in {"query", "passage"}: raise ValueError("Invalid input_type")
        try:
            async with (nullcontext(self.http_client) if self.http_client is not None else httpx.AsyncClient(timeout=self.settings.timeout_seconds)) as client:
                response = await client.post(self.settings.embedding_base_url + "/embeddings", headers={"Authorization": "Bearer " + (self.settings.embedding_api_key or self.settings.api_key)}, json={"model": self.settings.embedding_model, "input": texts, "input_type": input_type, "encoding_format": "float", "truncate": "NONE"})
        except httpx.HTTPError as exc:
            raise ProviderError("Không kết nối được embedding API.", "EMBEDDING_UNAVAILABLE") from exc
        if response.status_code >= 400: raise ProviderError(f"Embedding API trả HTTP {response.status_code}.")
        try:
            data = sorted(response.json()["data"], key=lambda r:r["index"])
            if [r["index"] for r in data] != list(range(len(texts))): raise ValueError("Invalid indexes")
            vectors = [r["embedding"] for r in data]
            if not vectors or not vectors[0] or any(len(v)!=len(vectors[0]) or any(not isinstance(x,(float,int)) or not math.isfinite(x) for x in v) for v in vectors): raise ValueError("Invalid vectors")
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError("Embedding API trả vector không hợp lệ.") from exc
        if len(vectors) != len(texts) or not vectors: raise ProviderError("Số vector không khớp dữ liệu.")
        return vectors
