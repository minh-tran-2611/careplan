import json
import re
from api.models import ChatResponse, PlanRow
from agent.core.planner import deidentify
from llm.providers.openai import ProviderError

JOURNAL_CHARACTERS = 6000
MAX_PLAN_ROWS = 6


def _strip_thinking(raw: str) -> str:
    return re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S).strip()


def _text(value, limit: int) -> str:
    if isinstance(value, list):
        value = "; ".join(str(v) for v in value if v)
    return str(value or "").strip()[:limit]


class Executor:
    def __init__(self, settings, provider):
        self.settings, self.provider = settings, provider

    def template(self, name: str) -> str:
        return (self.settings.root / "agent/prompts/templates" / name).read_text(encoding="utf-8")

    def build_prompt(self, request, sources, history) -> str:
        journal, used = [], 0
        for entry in reversed(request.journal):  # ưu tiên ghi chép mới nhất
            text = deidentify(entry.text)
            if used + len(text) > JOURNAL_CHARACTERS:
                break
            journal.insert(0, {"time": entry.time, "note": text})
            used += len(text)
        payload = {
            "question": deidentify(request.message),
            "history": [{"role": m["role"], "content": deidentify(m["content"])} for m in history],
            "journal": journal,
            "orders": {"time": request.ordersTime, "text": deidentify(request.orders)} if request.orders.strip() else None,
            "sources": [{"label": f"S{i}", "page": s.page, "chapter": s.chapter, "text": s.text} for i, s in enumerate(sources, 1)],
        }
        return self.template("task_prompt.txt") + "\n" + json.dumps(payload, ensure_ascii=False)

    # ---------- Trả lời thường ----------
    @staticmethod
    def cited(answer: str, sources) -> list[str]:
        labels = dict.fromkeys(int(n) for n in re.findall(r"\[S(\d+)\]", answer))
        return [sources[n - 1].id for n in labels if 1 <= n <= len(sources)]

    @staticmethod
    def clean_answer(raw: str, sources) -> str:
        answer = _strip_thinking(raw)
        if not answer:
            raise ProviderError("Model chưa trả nội dung hợp lệ.", "EMPTY_RESPONSE")
        # Bỏ nhãn trích dẫn trỏ tới nguồn không tồn tại để giao diện không hiện nguồn giả.
        return re.sub(r"\[S(\d+)\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= len(sources) else "", answer)[:12000]

    async def execute(self, request, sources, mode, history) -> ChatResponse:
        raw = await self.provider.complete(self.template("system_prompt.txt"), self.build_prompt(request, sources, history))
        answer = self.clean_answer(raw, sources)
        return ChatResponse(answer=answer, sources=sources, citedSourceIds=self.cited(answer, sources),
                            status="answered", retrieval_mode=mode)

    # ---------- Bảng kế hoạch ----------
    @staticmethod
    def resolve_sources(refs, sources) -> list[str]:
        """Nhận nhãn 'S2' / '[S2]' / 2 hoặc ID nguồn; bỏ mọi nhãn không có thật."""
        ids = {s.id for s in sources}
        found = []
        for ref in refs if isinstance(refs, list) else [refs]:
            ref = str(ref).strip()
            match = re.fullmatch(r"\[?S?(\d+)\]?", ref, flags=re.I)
            if match and 1 <= int(match.group(1)) <= len(sources):
                found.append(sources[int(match.group(1)) - 1].id)
            elif ref in ids:
                found.append(ref)
        return list(dict.fromkeys(found))

    def parse_plan(self, raw: str, sources):
        """Trả (summary, rows, missing). None nếu model không trả JSON."""
        text = _strip_thinking(raw)
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(text[start:end + 1])
        except ValueError:
            return None
        if not isinstance(data, dict) or not isinstance(data.get("plan"), list):
            return None
        rows = []
        for item in data["plan"]:
            if not isinstance(item, dict) or not _text(item.get("diagnosis"), 1000):
                continue
            steps = item.get("interventions", [])
            if isinstance(steps, str):
                steps = [s.strip(" -•\t") for s in steps.split("\n")]
            steps = [str(s).strip()[:500] for s in steps if str(s).strip()][:20]
            rows.append(PlanRow(diagnosis=_text(item.get("diagnosis"), 1000), goal=_text(item.get("goal"), 1500),
                                interventions=steps, evaluation=_text(item.get("evaluation"), 1500),
                                reason=_text(item.get("reason"), 2000),
                                sourceIds=self.resolve_sources(item.get("sources", item.get("sourceIds", [])), sources)))
            if len(rows) >= MAX_PLAN_ROWS:
                break
        missing = data.get("missingInfo", data.get("missingQuestions", []))
        missing = [str(m)[:500] for m in missing if str(m).strip()][:10] if isinstance(missing, list) else []
        return _text(data.get("summary"), 3000), rows, missing

    async def execute_plan(self, request, sources, mode, history) -> ChatResponse:
        raw = await self.provider.complete(self.template("plan_prompt.txt"), self.build_prompt(request, sources, history))
        parsed = self.parse_plan(raw, sources)
        if parsed is None:
            if "{" in (raw or ""):
                raise ProviderError("AI trả bảng kế hoạch sai định dạng. Vui lòng thử lại.", "INVALID_AI_RESPONSE")
            # Model trả lời văn bản thường thay vì bảng: vẫn hiển thị câu trả lời.
            answer = self.clean_answer(raw, sources)
            return ChatResponse(answer=answer, sources=sources, citedSourceIds=self.cited(answer, sources), retrieval_mode=mode)
        summary, rows, missing = parsed
        if not rows:
            summary = (summary + "\n" if summary else "") + "Chưa đủ dữ kiện để lập đầu mục nào. Bổ sung nhật ký diễn biến rồi thử lại."
        cited = list(dict.fromkeys(i for r in rows for i in r.sourceIds))
        return ChatResponse(answer=summary, kind="plan", plan=rows, missingInfo=missing, sources=sources,
                            citedSourceIds=cited, status="answered", retrieval_mode=mode)
