from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """A vendor-agnostic text-generation interface. Add new vendors by
    implementing this and registering them in llm/factory.py."""

    @abstractmethod
    async def generate(self, prompt: str) -> str:
        ...
