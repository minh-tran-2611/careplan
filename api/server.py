from pathlib import Path
from fastapi import FastAPI,Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from api.routes.agent_routes import router
from api.controllers.agent_controller import AgentController
from config.settings import get_settings
from agent.tools.retrieval import Retriever
from agent.core.agent import NursingAgent
from config.logging_config import configure_logging, request_id
from time import perf_counter
from uuid import uuid4

def create_app(settings=None,provider=None):
    cfg=settings or get_settings();app=FastAPI(title="AI Nursing Assistant",version="0.1.0",debug=False)
    logger = configure_logging(cfg.root)
    retriever=Retriever(cfg)
    app.state.settings=cfg;app.state.retriever=retriever
    app.state.controller=AgentController(NursingAgent(cfg,retriever,provider))
    @app.middleware("http")
    async def request_policy(request:Request,call_next):
        identifier = uuid4().hex[:12]
        request.state.request_id = identifier
        token = request_id.set(identifier)
        started = perf_counter()
        tracked = request.url.path in {"/api/chat", "/api/status", "/api/knowledge"}
        if tracked:
            logger.info("http.request_started", extra={"method": request.method, "path": request.url.path})
        try:
            response = await handle_request(request, call_next)
            response.headers["X-Request-ID"] = identifier
            if tracked:
                logger.info("http.request_completed", extra={"status_code": response.status_code, "elapsed_ms": round((perf_counter()-started)*1000)})
            return response
        except Exception as exc:
            logger.error("http.request_failed", extra={"exception_type": type(exc).__name__, "elapsed_ms": round((perf_counter()-started)*1000)})
            raise
        finally:
            request_id.reset(token)

    async def handle_request(request, call_next):
        try:
            length = int(request.headers.get("content-length", "0") or "0")
        except ValueError:
            return JSONResponse({"detail":"Content-Length không hợp lệ"}, status_code=400)
        if length < 0:
            return JSONResponse({"detail":"Content-Length không hợp lệ"}, status_code=400)
        if length>200000:return JSONResponse({"detail":"Nội dung quá dài"},status_code=413)
        response=await call_next(request)
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="same-origin"
        response.headers["X-Frame-Options"]="DENY"
        return response
    app.include_router(router)
    app.mount("/",StaticFiles(directory=cfg.root/"frontend",html=True),name="frontend")
    return app

app=create_app()
