import logging
from time import perf_counter
from api.models import ChatResponse
from agent.core.planner import build_query, wants_plan
from agent.core.executor import Executor
from agent.core.memory import build_memory
from llm.providers.factory import create_provider

logger = logging.getLogger("nursing")

NO_EVIDENCE = ("Không tìm thấy nội dung liên quan trong tài liệu NANDA – NIC – NOC hiện có. "
               "Thử hỏi bằng từ khóa khác hoặc bỏ lọc quy trình.")


class NursingAgent:
    """Chatbot RAG: tìm nguồn → gửi câu hỏi, nhật ký và nguồn cho model → trả lời có trích dẫn."""

    def __init__(self, settings, retriever, provider=None):
        self.settings, self.retriever = settings, retriever
        self.executor = Executor(settings, provider or create_provider(settings))

    async def respond(self, request) -> ChatResponse:
        started = perf_counter()
        plan = wants_plan(request.message, request.mode)
        query = build_query(request.message, request.messages, request.journal, plan)
        sources, mode = await self.retriever.retrieve(query, request.chapter)
        logger.info("retrieval.completed", extra={"source_count": len(sources), "retrieval_mode": mode,
                                                   "elapsed_ms": round((perf_counter() - started) * 1000)})
        if not sources:
            return ChatResponse(answer=NO_EVIDENCE, status="no_evidence", retrieval_mode=mode)
        history = build_memory(request.messages, self.settings.max_turns).snapshot()
        run = self.executor.execute_plan if plan else self.executor.execute
        response = await run(request, sources, mode, history)
        logger.info("agent.completed", extra={"kind": response.kind, "plan_rows": len(response.plan),
                                              "cited_sources": len(response.citedSourceIds),
                                              "elapsed_ms": round((perf_counter() - started) * 1000)})
        return response
