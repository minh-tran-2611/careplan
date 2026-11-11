from llm.providers.openai import OpenAICompatibleProvider

class LocalModelProvider(OpenAICompatibleProvider):
    """OpenAI-compatible local server such as vLLM. Configure LLM_BASE_URL."""
    def payload(self, system: str, prompt: str) -> dict:
        payload = super().payload(system, prompt)
        payload.pop("response_format", None)
        return payload
