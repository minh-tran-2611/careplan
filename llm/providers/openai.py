import asyncio
import logging
from time import perf_counter
import httpx

logger = logging.getLogger("nursing")

class ProviderError(RuntimeError):
    def __init__(self, message: str, code: str = "UPSTREAM_ERROR"):
        super().__init__(message)
        self.code = code

class OpenAICompatibleProvider:
    def __init__(self, settings):
        self.settings = settings

    def payload(self, system: str, prompt: str) -> dict:
        return {"model": self.settings.model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                "max_tokens": self.settings.max_tokens, "stream": False}

    async def complete(self, system: str, prompt: str) -> str:
        if not self.settings.api_key and self.settings.provider != "local":
            raise ProviderError("Chưa cấu hình API key ở server. Chạy start.ps1 hoặc đặt biến môi trường.", "AI_NOT_CONFIGURED")
        started = perf_counter()
        context = {"provider": self.settings.provider, "model": self.settings.model, "timeout_seconds": self.settings.timeout_seconds}
        logger.info("llm.request_started", extra={**context, "prompt_characters": len(prompt)})
        try:
            async with asyncio.timeout(self.settings.timeout_seconds):
                async with httpx.AsyncClient(timeout=httpx.Timeout(self.settings.timeout_seconds, connect=min(15, self.settings.timeout_seconds)), follow_redirects=False) as client:
                    response = await client.post(self.settings.base_url + "/chat/completions", headers={"Authorization": "Bearer " + (self.settings.api_key or "local")}, json=self.payload(system, prompt))
            logger.info("llm.response_received", extra={**context, "elapsed_ms": round((perf_counter()-started)*1000), "status_code": response.status_code})
            if response.status_code in (401, 403): raise ProviderError("API từ chối xác thực. Kiểm tra key và quyền model.", "AUTH_ERROR")
            if response.status_code == 429: raise ProviderError("API đang giới hạn tốc độ hoặc hết hạn mức.", "RATE_LIMIT")
            if response.status_code >= 400: raise ProviderError(f"API AI chưa xử lý được yêu cầu (HTTP {response.status_code}).")
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content")
            if not isinstance(content, str) or not content.strip(): raise ProviderError("Model chưa trả nội dung hợp lệ.", "EMPTY_RESPONSE")
            usage = data.get("usage") or {}
            logger.info("llm.request_completed", extra={**context, "elapsed_ms": round((perf_counter()-started)*1000), "response_characters": len(content), "finish_reason": data["choices"][0].get("finish_reason"), "input_tokens": usage.get("prompt_tokens"), "output_tokens": usage.get("completion_tokens")})
            return content
        except (httpx.TimeoutException, TimeoutError) as exc:
            logger.warning("llm.timeout", extra={**context, "elapsed_ms": round((perf_counter()-started)*1000), "error_code": "TIMEOUT", "exception_type": type(exc).__name__})
            raise ProviderError("Model phản hồi chậm. Vui lòng thử lại.", "TIMEOUT") from exc
        except httpx.HTTPError as exc:
            logger.warning("llm.network_error", extra={**context, "elapsed_ms": round((perf_counter()-started)*1000), "error_code": "NETWORK_ERROR", "exception_type": type(exc).__name__})
            raise ProviderError("Không kết nối được API AI. Kiểm tra mạng.", "NETWORK_ERROR") from exc
        except (ValueError, IndexError, KeyError, AttributeError) as exc:
            logger.warning("llm.invalid_response", extra={**context, "elapsed_ms": round((perf_counter()-started)*1000), "error_code": "INVALID_RESPONSE", "exception_type": type(exc).__name__})
            raise ProviderError("Phản hồi API không đúng định dạng.", "INVALID_RESPONSE") from exc
