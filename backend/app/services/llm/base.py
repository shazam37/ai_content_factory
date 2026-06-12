from abc import ABC, abstractmethod


class BaseLLMClient(ABC):
    """Abstract base for all LLM provider clients."""

    @abstractmethod
    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.8,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        """Send a completion request and return the response text."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier used by this client."""
        ...
