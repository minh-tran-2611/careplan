from collections import defaultdict
from time import monotonic
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from api.models import ChatRequest, ChatResponse
from llm.providers.openai import ProviderError
import logging

logger = logging.getLogger("nursing")

router = APIRouter(prefix="/api")
_recent = defaultdict(list)


@router.get("/status")
async def status(request: Request):
    cfg = request.app.state.settings
    return {"configured": bool(cfg.api_key) or cfg.provider == "local", "model": cfg.model, "provider": cfg.provider,
            "timeout_seconds": cfg.timeout_seconds, "stores_patient_data": False,
            "retrieval": "hybrid" if cfg.embedding_model and (cfg.qdrant_url or request.app.state.retriever.vectors.rows) else "keyword"}


@router.get("/knowledge")
async def knowledge(request: Request, q: str = "", chapter: str = ""):
    if len(q) > 1000 or len(chapter) > 80:
        raise HTTPException(400, "Truy vấn quá dài")
    retriever = request.app.state.retriever
    return {"chapters": retriever.corpus["chapters"], "stats": retriever.corpus["stats"],
            "sources": [r.model_dump() for r in retriever.search(q, chapter)] if q or chapter else []}


@router.get("/page-image/{page}")
async def page_image(page: int, request: Request):
    """Ảnh trang gốc của sách để đối chiếu nguồn OCR."""
    if not 1 <= page <= 373:
        raise HTTPException(404, "Không có trang này")
    root = request.app.state.settings.root
    name = f"page_{page:03d}.webp"
    # Bản deploy để ảnh trong data/pages; bản chạy local dùng thư mục ảnh gốc bên cạnh.
    path = next((p for p in (root / "data" / "pages" / name, root.parent / "NANDA_NIC_NOC_pages" / name) if p.is_file()), None)
    if path is None:
        raise HTTPException(404, "Không tìm thấy ảnh trang")
    return FileResponse(path, media_type="image/webp")


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, request: Request):
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Origin không hợp lệ")
    key = request.client.host if request.client else "local"
    now = monotonic()
    _recent[key] = [t for t in _recent[key] if t > now - 300]
    if len(_recent[key]) >= 30:
        raise HTTPException(429, "Bạn đã gửi nhiều yêu cầu. Thử lại sau ít phút.")
    _recent[key].append(now)
    try:
        return await request.app.state.controller.chat(payload)
    except ProviderError as exc:
        status_code = 503 if exc.code == "AI_NOT_CONFIGURED" else 504 if exc.code == "TIMEOUT" else 502
        logger.warning("chat.provider_error", extra={"error_code": exc.code, "status_code": status_code})
        raise HTTPException(status_code, {"error": str(exc), "code": exc.code, "request_id": request.state.request_id}) from exc
