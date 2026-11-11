"""Qdrant REST adapter. Stores reference documents only, never patient queries."""
from uuid import uuid5, NAMESPACE_URL
import httpx
from contextlib import nullcontext
from llm.providers.openai import ProviderError

class QdrantStore:
    def __init__(self, settings):
        self.settings = settings
        self.rows = []  # Compatibility with the optional local store.
        self.http_client = None

    async def request(self, method, suffix="", body=None):
        cfg = self.settings
        try:
            async with (nullcontext(self.http_client) if self.http_client is not None else httpx.AsyncClient(timeout=30)) as client:
                response = await client.request(method, cfg.qdrant_url + "/collections/" + cfg.qdrant_collection + suffix,
                    headers={"api-key": cfg.qdrant_api_key}, json=body,timeout=90 if suffix.startswith('/points?') else 30)
            if response.status_code >= 400:
                raise ProviderError(f"Qdrant trả HTTP {response.status_code}.", "QDRANT_UNAVAILABLE")
            return response.json()["result"]
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise ProviderError("Không kết nối được Qdrant.", "QDRANT_UNAVAILABLE") from exc

    async def ensure_collection(self, dimension):
        # Never recreate or delete an existing collection.
        try:
            result = await self.request("GET")
        except ProviderError as exc:
            if "HTTP 404" not in str(exc): raise
            await self.request("PUT", body={"vectors": {"size": dimension, "distance": "Cosine"}})
            return
        config = result["config"]["params"]["vectors"]
        if config.get("size") != dimension or config.get("distance") != "Cosine":
            raise ValueError("Collection không khớp kích thước vector/Cosine; hãy dùng collection mới.")

    async def upsert(self, records, vectors):
        points = [{"id": str(uuid5(NAMESPACE_URL, r["id"])), "vector": v,
                   "payload": {**r, "embedding_model": self.settings.embedding_model}}
                  for r,v in zip(records,vectors)]
        await self.request("PUT", "/points?wait=true", {"points": points})

    async def search(self, vector, allowed_ids, limit=8):
        result = await self.request("POST", "/points/query", {
            "query": vector, "limit": limit, "with_payload": True,
            "filter": {"must": [
                {"key": "id", "match": {"any": sorted(allowed_ids)}},
                {"key": "embedding_model", "match": {"value": self.settings.embedding_model}}
            ]}})
        return [(p["payload"]["id"], p["score"]) for p in result["points"]]
