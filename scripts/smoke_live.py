"""Live test with a fictional case only; never prints the API key."""
import asyncio
from api.models import ChatRequest, JournalEntry
from config.settings import get_settings
from agent.tools.retrieval import Retriever
from agent.core.agent import NursingAgent


async def main():
    cfg = get_settings()
    if not cfg.api_key:
        raise SystemExit('API key missing in process environment.')
    request = ChatRequest(
        message='Người bệnh đợt cấp COPD này cần theo dõi và can thiệp điều dưỡng gì?',
        journal=[JournalEntry(time='08:00', text='Ca GIẢ LẬP. Tỉnh, ho có đàm, khó thở khi vận động.'),
                 JournalEntry(time='11:00', text='Khó thở tăng khi đi vệ sinh, cần hỗ trợ.')])
    result = await NursingAgent(cfg, Retriever(cfg)).respond(request)
    assert result.status == 'answered', result.answer
    print({'model': cfg.model, 'status': result.status, 'cited': len(result.citedSourceIds),
           'source_pages': [s.page for s in result.sources], 'retrieval': result.retrieval_mode,
           'answer_preview': result.answer[:300]})


if __name__ == '__main__':
    asyncio.run(main())
