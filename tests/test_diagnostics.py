import asyncio
import io
import json
import logging
import unittest
from dataclasses import replace
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from config.settings import get_settings
from config.logging_config import JsonFormatter, request_id
from llm.providers.nvidia import NvidiaProvider
from llm.providers.openai import ProviderError
from api.server import create_app
from api.routes.agent_routes import _recent
from agent.core.agent import NursingAgent
from agent.tools.retrieval import Retriever


class TimeoutClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, *args, **kwargs):
        raise httpx.ReadTimeout('SECRET_EXCEPTION_TEXT must not be logged')


class TimeoutProvider:
    async def complete(self, system, prompt):
        raise ProviderError('Model phản hồi chậm. Vui lòng thử lại.', 'TIMEOUT')


class ForbiddenProvider:
    async def complete(self, system, prompt):
        raise AssertionError('Dengue without a matching source must not call the model')


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        _recent.clear()
        self.cfg = replace(get_settings(), embedding_model="", qdrant_url="")

    def test_timeout_log_is_useful_without_content_or_key(self):
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger('nursing')
        logger.addHandler(handler)
        token = request_id.set('timeout-test')
        try:
            with patch('llm.providers.openai.httpx.AsyncClient', TimeoutClient):
                with self.assertRaises(ProviderError) as exc:
                    asyncio.run(NvidiaProvider(replace(self.cfg, api_key='SECRET_KEY')).complete('SECRET_SYSTEM', 'SECRET_CASE'))
                self.assertEqual(exc.exception.code, 'TIMEOUT')
        finally:
            logger.removeHandler(handler)
            request_id.reset(token)
        raw = output.getvalue()
        for secret in ['SECRET_KEY', 'SECRET_CASE', 'SECRET_SYSTEM', 'SECRET_EXCEPTION_TEXT']:
            self.assertNotIn(secret, raw)
        events = [json.loads(line) for line in raw.splitlines()]
        timeout = next(event for event in events if event['event'] == 'llm.timeout')
        self.assertEqual(timeout['request_id'], 'timeout-test')
        self.assertEqual(timeout['exception_type'], 'ReadTimeout')
        self.assertIn('elapsed_ms', timeout)
        self.assertEqual(timeout['timeout_seconds'], self.cfg.timeout_seconds)

    def test_api_timeout_returns_504_and_matching_request_id(self):
        with TestClient(create_app(self.cfg, TimeoutProvider())) as client:
            response = client.post('/api/chat', json={'message': 'COPD khó thở cần chăm sóc gì?', 'chapter': 'chapter_01'})
            self.assertEqual(response.status_code, 504)
            detail = response.json()['detail']
            self.assertEqual(detail['code'], 'TIMEOUT')
            self.assertEqual(detail['request_id'], response.headers['X-Request-ID'])
            self.assertEqual(detail['error'], 'Model phản hồi chậm. Vui lòng thử lại.')


    def test_status_exposes_timeout_without_secret(self):
        with TestClient(create_app(replace(self.cfg, api_key='SECRET_STATUS_KEY'), TimeoutProvider())) as client:
            response = client.get('/api/status')
            self.assertEqual(response.json()['timeout_seconds'], self.cfg.timeout_seconds)
            self.assertNotIn('SECRET_STATUS_KEY', response.text)
