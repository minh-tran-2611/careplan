from typing import Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class JournalEntry(BaseModel):
    """Một dòng nhật ký theo dõi diễn biến do điều dưỡng ghi."""
    time: str = Field(default="", max_length=40)
    text: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)
    messages: list[ChatMessage] = Field(default_factory=list, max_length=10)
    journal: list[JournalEntry] = Field(default_factory=list, max_length=50)
    chapter: str = Field(default="", max_length=80)
    # Y lệnh nội trú hiện hành do bác sĩ chỉ định (dán/gõ tự do)
    orders: str = Field(default="", max_length=6000)
    ordersTime: str = Field(default="", max_length=40)
    # auto: tự nhận biết yêu cầu lập kế hoạch; plan: luôn trả bảng; answer: luôn trả lời thường
    mode: Literal["auto", "plan", "answer"] = "auto"


class PlanRow(BaseModel):
    """Một đầu mục trong bảng kế hoạch điều dưỡng."""
    diagnosis: str = Field(max_length=1000)
    goal: str = Field(default="", max_length=1500)
    interventions: list[str] = Field(default_factory=list, max_length=20)
    evaluation: str = Field(default="", max_length=1500)
    reason: str = Field(default="", max_length=2000)
    sourceIds: list[str] = Field(default_factory=list, max_length=10)


class Source(BaseModel):
    id: str
    page: int
    chapter: str
    type: str
    text: str
    reviewFlags: list[str] = Field(default_factory=list)
    blockIds: list[str] = Field(default_factory=list)
    contextSources: list[dict] = Field(default_factory=list)
    sourceImage: str = ""
    originalText: str = ""


class ChatResponse(BaseModel):
    answer: str
    kind: Literal["answer", "plan"] = "answer"
    plan: list[PlanRow] = Field(default_factory=list)
    missingInfo: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    citedSourceIds: list[str] = Field(default_factory=list)
    status: Literal["answered", "no_evidence"] = "answered"
    retrieval_mode: str = "keyword"
