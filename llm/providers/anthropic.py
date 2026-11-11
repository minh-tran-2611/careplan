import httpx
from llm.providers.openai import ProviderError

class AnthropicProvider:
    def __init__(self, settings): self.settings = settings
    async def complete(self, system: str, prompt: str) -> str:
        if not self.settings.api_key: raise ProviderError("Chưa cấu hình ANTHROPIC_API_KEY.", "AI_NOT_CONFIGURED")
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout_seconds, follow_redirects=False) as client:
                response = await client.post(self.settings.base_url + "/messages", headers={"x-api-key": self.settings.api_key, "anthropic-version": "2023-06-01"}, json={"model": self.settings.model, "system": system, "max_tokens": self.settings.max_tokens, "messages": [{"role": "user", "content": prompt}]})
            if response.status_code >= 400: raise ProviderError(f"Anthropic trả HTTP {response.status_code}.")
            return "".join(p.get("text", "") for p in response.json().get("content", []) if p.get("type") == "text")
        except httpx.HTTPError as exc: raise ProviderError("Không kết nối được Anthropic.", "NETWORK_ERROR") from exc
