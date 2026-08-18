from app.config import settings
from app.llm.base import LLMProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.openai_provider import OpenAIProvider


def get_llm_provider() -> LLMProvider:
    """Returns the configured LLM provider. Extend this when adding new
    vendors (Anthropic, ...) by branching on settings.llm_provider."""
    if settings.llm_provider == "ollama":
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.llm_model)

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY must be set when LLM_PROVIDER=openai")
        return OpenAIProvider(api_key=settings.openai_api_key, model=settings.llm_model)

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
