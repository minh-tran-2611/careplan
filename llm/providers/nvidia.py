from llm.providers.openai import OpenAICompatibleProvider

class NvidiaProvider(OpenAICompatibleProvider):
    def payload(self, system: str, prompt: str) -> dict:
        return {**super().payload(system, prompt), "chat_template_kwargs": {"enable_thinking": False}}
