from app.config import settings
from app.llm.base import LLMProvider
from app.llm.ollama_provider import OllamaProvider


def get_llm_provider() -> LLMProvider:
    """Returns the configured LLM provider. Extend this when adding new
    vendors (OpenAI, Anthropic, ...) by branching on settings.llm_provider."""
    if settings.llm_provider == "ollama":
        return OllamaProvider(base_url=settings.ollama_base_url, model=settings.llm_model)

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
