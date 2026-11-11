from llm.providers.nvidia import NvidiaProvider
from llm.providers.openai import OpenAICompatibleProvider, ProviderError
from llm.providers.anthropic import AnthropicProvider
from llm.providers.local_model import LocalModelProvider

def create_provider(settings):
    cls = {"nvidia": NvidiaProvider, "openai": OpenAICompatibleProvider, "compatible": OpenAICompatibleProvider, "anthropic": AnthropicProvider, "local": LocalModelProvider}.get(settings.provider)
    if cls is None: raise ProviderError("Nhà cung cấp LLM chưa được hỗ trợ.", "CONFIG_ERROR")
    return cls(settings)
