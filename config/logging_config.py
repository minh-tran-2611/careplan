"""Application diagnostics with an explicit allowlist; never log clinical text."""
import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler

request_id = ContextVar("request_id", default="-")
SAFE_FIELDS = {
    "method", "path", "status_code", "elapsed_ms", "model", "provider",
    "timeout_seconds", "error_code", "exception_type", "source_count",
    "retrieval_mode", "plan_rows", "missing_questions", "prompt_characters",
    "response_characters", "finish_reason", "input_tokens", "output_tokens",
}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": request_id.get(),
        }
        for field in SAFE_FIELDS:
            if hasattr(record, field):
                value = getattr(record, field)
                if value is None or isinstance(value, (str, int, float, bool)):
                    entry[field] = value
        return json.dumps(entry, ensure_ascii=False)


def configure_logging(root):
    logger = logging.getLogger("nursing")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    destination = (root / "logs" / "app.log").resolve()
    if any(isinstance(h, RotatingFileHandler) and h.baseFilename == str(destination) for h in logger.handlers):
        return logger
    destination.parent.mkdir(parents=True, exist_ok=True)
    formatter = JsonFormatter()
    file_handler = RotatingFileHandler(destination, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in logger.handlers):
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)
    return logger
