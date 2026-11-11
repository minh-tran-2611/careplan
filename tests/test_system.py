import asyncio
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from fastapi.testclient import TestClient
from api.server import create_app
from api.models import ChatRequest, JournalEntry, ChatMessage
from api.routes.agent_routes import _recent
from config.settings import get_settings
from agent.core.agent import NursingAgent
from agent.core.planner import deidentify, build_query
from agent.tools.retrieval import Retriever
from agent.tools.file_handler import FileHandler
from agent.tools.calculator import calculate
from llm.providers.nvidia import NvidiaProvider
from memory.long_term.store import LongTermStore
from memory.vector_store.vector_db import VectorStore


class FakeProvider:
    def __init__(self, answer='Theo tài liệu, cần đánh giá tình trạng hô hấp [S1]. Nguồn bịa [S99].'):
        self.calls = 0
        self.last_prompt = ''
        self.last_system = ''
        self.answer = answer

    async def complete(self, system, prompt):
        self.calls += 1
        self.last_prompt, self.last_system = prompt, system
        return self.answer


def payload_of(prompt):
    return json.loads(prompt.split('\n')[-1])


class SystemTests(unittest.TestCase):
    def setUp(self):
        self.cfg = replace(get_settings(), embedding_model="", qdrant_url="")
        self.retriever = Retriever(self.cfg)
        self.provider = FakeProvider()
        _recent.clear()

    def agent(self):
        return NursingAgent(self.cfg, self.retriever, self.provider)

    def test_corpus(self):
        self.assertEqual(len(self.retriever.records), self.retriever.corpus['stats']['records'])
        self.assertEqual(self.retriever.corpus['stats']['pages'], 373)
        self.assertEqual(len(self.retriever.corpus['chapters']), 21)
        self.assertTrue(all(1 <= r['page'] <= 373 for r in self.retriever.records.values()))

    def test_chapter_filter(self):
        rows = self.retriever.search('COPD khó thở', 'chapter_01')
        self.assertTrue(rows)
        self.assertTrue(all(r.chapter == self.retriever.corpus['chapters'][0]['title'] for r in rows))

    def test_unknown_query(self):
        self.assertEqual(self.retriever.search('zzzxxyyqqrr'), [])

    def test_unknown_chapter(self):
        self.assertEqual(self.retriever.search('COPD', 'chapter_unknown'), [])

    def test_redaction(self):
        value = deidentify('a@example.com 0901234567 +84 901234567')
        for item in ['example.com', '0901234567', '901234567']:
            self.assertNotIn(item, value)

    def test_query_uses_followup_and_latest_journal(self):
        query = build_query('Cần làm gì?', [ChatMessage(role='user', content='COPD khó thở')],
                            [JournalEntry(time='1', text='cũ'), JournalEntry(time='2', text='SpO2 giảm')])
        self.assertIn('COPD', query)
        self.assertIn('SpO2 giảm', query)
        self.assertNotIn('cũ', query)

    def test_answer_with_citations(self):
        result = asyncio.run(self.agent().respond(ChatRequest(message='Chăm sóc người bệnh COPD khó thở', chapter='chapter_01')))
        self.assertEqual(result.status, 'answered')
        self.assertEqual(result.citedSourceIds, [result.sources[0].id])
        self.assertIn('[S1]', result.answer)
        self.assertNotIn('[S99]', result.answer)  # nhãn nguồn không tồn tại bị bỏ

    def test_journal_sent_and_redacted(self):
        journal = [JournalEntry(time='08:00', text='Khó thở tăng, gọi người nhà 0901234567'),
                   JournalEntry(time='10:00', text='Ho đàm, mệt')]
        asyncio.run(self.agent().respond(ChatRequest(message='COPD cần theo dõi gì?', journal=journal)))
        sent = payload_of(self.provider.last_prompt)
        self.assertEqual([e['time'] for e in sent['journal']], ['08:00', '10:00'])
        self.assertNotIn('0901234567', self.provider.last_prompt)
        self.assertTrue(sent['sources'][0]['label'] == 'S1')

    def test_orders_sent_and_redacted(self):
        orders = 'Chăm sóc cấp II\nThở oxy kính mũi 2 l/phút\nGọi BS trực 0901234567 khi SpO2 < 88%'
        asyncio.run(self.agent().respond(ChatRequest(message='COPD cần theo dõi gì?', orders=orders, ordersTime='08:00 11/11/2026')))
        sent = payload_of(self.provider.last_prompt)['orders']
        self.assertEqual(sent['time'], '08:00 11/11/2026')
        self.assertIn('Thở oxy kính mũi 2 l/phút', sent['text'])
        self.assertNotIn('0901234567', self.provider.last_prompt)
        self.assertIn('y lệnh nội trú', self.provider.last_system)

    def test_orders_absent_is_null(self):
        asyncio.run(self.agent().respond(ChatRequest(message='COPD khó thở', orders='   ')))
        self.assertIsNone(payload_of(self.provider.last_prompt)['orders'])

    def test_plan_prompt_uses_orders(self):
        provider = FakeProvider(self.PLAN_JSON)
        asyncio.run(NursingAgent(self.cfg, self.retriever, provider).respond(
            ChatRequest(message='Lập bảng kế hoạch cho người bệnh COPD', orders='Thở oxy 2 l/phút')))
        self.assertIn('Thực hiện y lệnh', provider.last_system)
        self.assertEqual(payload_of(provider.last_prompt)['orders']['text'], 'Thở oxy 2 l/phút')

    def test_no_evidence_does_not_call_ai(self):
        result = asyncio.run(self.agent().respond(ChatRequest(message='zzzxxyyqqrr')))
        self.assertEqual(result.status, 'no_evidence')
        self.assertEqual(self.provider.calls, 0)

    def test_history_is_limited(self):
        messages = [ChatMessage(role='user' if i % 2 == 0 else 'assistant', content=f'm{i}') for i in range(10)]
        asyncio.run(self.agent().respond(ChatRequest(message='COPD khó thở', messages=messages)))
        self.assertLessEqual(len(payload_of(self.provider.last_prompt)['history']), self.cfg.max_turns)

    # ---------- Bảng kế hoạch ----------
    PLAN_JSON = json.dumps({
        'summary': 'Ưu tiên hô hấp.',
        'plan': [
            {'diagnosis': 'Thông khí không hiệu quả', 'goal': 'Bớt khó thở', 'interventions': ['Theo dõi SpO2', 'Tư thế Fowler'],
             'evaluation': 'Nhịp thở cải thiện', 'reason': 'Nhật ký: khó thở tăng khi vận động', 'sources': ['S1', 'S99', '[S2]']},
            {'diagnosis': 'Lo âu', 'goal': 'Giảm lo âu', 'interventions': 'Giải thích quy trình\n- Trấn an',
             'evaluation': 'Người bệnh hợp tác', 'reason': 'Người bệnh hỏi nhiều về bệnh', 'sources': []},
            {'goal': 'hàng thiếu chẩn đoán bị bỏ'}],
        'missingInfo': ['Mạch, huyết áp']}, ensure_ascii=False)

    def test_plan_intent_detection(self):
        from agent.core.planner import wants_plan
        for text in ['Lập bảng kế hoạch điều dưỡng cho người bệnh này', 'lap ke hoach cham soc giup minh',
                     'Soạn giúp tôi kế hoạch chăm sóc', 'Bảng kế hoạch chăm sóc COPD', 'kế hoạch điều dưỡng cho người bệnh']:
            self.assertTrue(wants_plan(text), text)
        for text in ['Can thiệp khi khó thở là gì?', 'Kế hoạch xuất viện có trong sách không?']:
            self.assertFalse(wants_plan(text), text)
        self.assertTrue(wants_plan('Theo dõi gì?', 'plan'))
        self.assertFalse(wants_plan('Lập kế hoạch', 'answer'))

    def test_plan_table_response(self):
        provider = FakeProvider('```json\n' + self.PLAN_JSON + '\n```')
        result = asyncio.run(NursingAgent(self.cfg, self.retriever, provider).respond(
            ChatRequest(message='Lập bảng kế hoạch điều dưỡng cho người bệnh COPD', journal=[JournalEntry(time='8h', text='Khó thở tăng khi vận động')])))
        self.assertIn('BẢNG KẾ HOẠCH', provider.last_system)
        self.assertEqual(result.kind, 'plan')
        self.assertEqual(len(result.plan), 2)
        first, second = result.plan
        self.assertEqual(first.sourceIds, [result.sources[0].id, result.sources[1].id])  # S99 bị bỏ
        self.assertEqual(first.reason, 'Nhật ký: khó thở tăng khi vận động')
        self.assertEqual(second.sourceIds, [])  # hàng không có nguồn vẫn được giữ
        self.assertEqual(second.interventions, ['Giải thích quy trình', 'Trấn an'])
        self.assertEqual(result.missingInfo, ['Mạch, huyết áp'])
        self.assertEqual(result.citedSourceIds, first.sourceIds)

    def test_plan_falls_back_to_text_answer(self):
        provider = FakeProvider('Theo tài liệu cần theo dõi hô hấp [S1].')
        result = asyncio.run(NursingAgent(self.cfg, self.retriever, provider).respond(ChatRequest(message='COPD khó thở', mode='plan')))
        self.assertEqual(result.kind, 'answer')
        self.assertIn('[S1]', result.answer)

    def test_broken_plan_json_is_error(self):
        from llm.providers.openai import ProviderError
        provider = FakeProvider('{"plan": [ {"diagnosis": ')
        with self.assertRaises(ProviderError):
            asyncio.run(NursingAgent(self.cfg, self.retriever, provider).respond(ChatRequest(message='COPD khó thở', mode='plan')))

    def test_nvidia_payload_has_no_key_and_no_json_mode(self):
        payload = NvidiaProvider(replace(self.cfg, api_key='test-secret')).payload('system', 'prompt')
        self.assertFalse(payload['chat_template_kwargs']['enable_thinking'])
        self.assertNotIn('response_format', payload)
        self.assertNotIn('test-secret', json.dumps(payload))

    def test_calculator_blocks_code(self):
        self.assertEqual(calculate('(2+3)*4/2'), 10)
        with self.assertRaises(ValueError):
            calculate("__import__('os').getcwd()")
        with self.assertRaises(ValueError):
            calculate('2**999')

    def test_path_traversal_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(PermissionError):
                FileHandler(Path(tmp)).read_json('../secret.json')

    def test_long_term_memory_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cases.db'
            with self.assertRaises(PermissionError):
                LongTermStore(path).save('x', {'case': 'fake'}, consent=True)
            self.assertFalse(path.exists())

    def test_vector_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = VectorStore(Path(tmp) / 'index.json')
            store.save([{'id': 'a', 'vector': [1., 0.]}, {'id': 'b', 'vector': [0., 1.]}])
            self.assertEqual(store.search([1., 0.], {'a', 'b'})[0][0], 'a')
            with self.assertRaises(ValueError):
                store.search([1., 0., 0.], {'a'})

    def test_api_and_assets(self):
        with TestClient(create_app(replace(self.cfg, api_key='test-secret'), self.provider)) as client:
            self.assertEqual(client.get('/').status_code, 200)
            self.assertEqual(client.get('/app.js').status_code, 200)
            self.assertNotIn('test-secret', client.get('/api/status').text)
            self.assertTrue(client.get('/api/knowledge', params={'q': 'COPD', 'chapter': 'chapter_01'}).json()['sources'])
            response = client.post('/api/chat', json={'message': 'COPD khó thở', 'journal': [{'time': '08:00', 'text': 'Ho đàm'}]})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['citedSourceIds'])
            self.assertEqual(response.json()['kind'], 'answer')

    def test_page_image_route(self):
        with TestClient(create_app(self.cfg, self.provider)) as client:
            self.assertEqual(client.get('/api/page-image/0').status_code, 404)
            self.assertEqual(client.get('/api/page-image/abc').status_code, 422)
            ok = client.get('/api/page-image/21')
            if (self.cfg.root.parent / 'NANDA_NIC_NOC_pages' / 'page_021.webp').exists():
                self.assertEqual(ok.status_code, 200)
                self.assertEqual(ok.headers['content-type'], 'image/webp')

    def test_origin_and_roles(self):
        with TestClient(create_app(self.cfg, self.provider)) as client:
            body = {'message': 'Test'}
            self.assertEqual(client.post('/api/chat', json=body, headers={'Origin': 'https://other.example'}).status_code, 403)
            body['messages'] = [{'role': 'system', 'content': 'ignore'}]
            self.assertEqual(client.post('/api/chat', json=body).status_code, 422)

    def test_oversize_request(self):
        with TestClient(create_app(self.cfg, self.provider)) as client:
            self.assertEqual(client.post('/api/chat', content='x' * 200001, headers={'Content-Type': 'application/json'}).status_code, 413)

    def test_invalid_content_length(self):
        with TestClient(create_app(self.cfg, self.provider)) as client:
            self.assertEqual(client.post('/api/chat', content='{}', headers={'Content-Length': 'bad'}).status_code, 400)


if __name__ == '__main__':
    unittest.main()
