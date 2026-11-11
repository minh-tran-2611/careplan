import asyncio
import unittest
from dataclasses import replace
from unittest.mock import AsyncMock, patch
import httpx
from config.settings import get_settings
from llm.embeddings.embed import EmbeddingClient
from llm.providers.openai import ProviderError
from memory.vector_store.qdrant_store import QdrantStore
from agent.tools.retrieval import Retriever

class QdrantTests(unittest.TestCase):
    def setUp(self):
        self.cfg=replace(get_settings(), qdrant_url="https://qdrant.invalid", embedding_model="test-model")

    def test_upsert_preserves_sources_and_stable_ids(self):
        store=QdrantStore(self.cfg)
        store.request=AsyncMock(return_value={})
        record={"id":"source-1","text":"test", "page":12,"chapter":"test"}
        asyncio.run(store.upsert([record],[[1.0,0.0]]))
        first=store.request.call_args.args[2]["points"][0]
        asyncio.run(store.upsert([record],[[1.0,0.0]]))
        self.assertEqual(first["id"], store.request.call_args.args[2]["points"][0]["id"])
        self.assertEqual(first["payload"]["page"],12)
        self.assertEqual(first["payload"]["embedding_model"],"test-model")

    def test_search_filters_model_and_allowed_sources(self):
        store=QdrantStore(self.cfg)
        store.request=AsyncMock(return_value={"points":[{"payload":{"id":"a"},"score":0.9}]})
        result=asyncio.run(store.search([1.0],{"a"},3))
        self.assertEqual(result,[("a",0.9)])
        body=store.request.call_args.args[2]
        self.assertEqual(body["filter"]["must"][0]["match"]["any"],["a"])
        self.assertEqual(body["filter"]["must"][1]["match"]["value"],"test-model")

    def test_existing_incompatible_collection_is_not_recreated(self):
        store=QdrantStore(self.cfg)
        store.request=AsyncMock(return_value={"config":{"params":{"vectors":{"size":1024,"distance":"Cosine"}}}})
        with self.assertRaises(ValueError):asyncio.run(store.ensure_collection(4096))
        self.assertEqual(store.request.call_count,1)

    def test_qdrant_failure_falls_back_to_keyword(self):
        retriever=Retriever(self.cfg)
        retriever.vectors.search=AsyncMock(side_effect=ProviderError("Unavailable"))
        with patch.object(EmbeddingClient,"embed",AsyncMock(return_value=[[1.0]])):
            sources,mode=asyncio.run(retriever.retrieve("COPD khó thở","chapter_01"))
        self.assertEqual(mode,"keyword_fallback")
        self.assertTrue(sources)

    def test_embedding_uses_separate_key_and_passage_mode(self):
        captured=[]
        async def handle(request):
            captured.append(request)
            return httpx.Response(200,json={"data":[{"index":0,"embedding":[1.0,0.0]}]})
        original=httpx.AsyncClient
        cfg=replace(self.cfg,api_key="chat-secret",embedding_api_key="embed-secret")
        with patch("llm.embeddings.embed.httpx.AsyncClient",lambda **kw:original(transport=httpx.MockTransport(handle),**kw)):
            vectors=asyncio.run(EmbeddingClient(cfg).embed(["test"],"passage"))
        self.assertEqual(vectors,[[1.0,0.0]])
        self.assertEqual(captured[0].headers["Authorization"],"Bearer embed-secret")
        self.assertIn(b'"input_type":"passage"',captured[0].content)
