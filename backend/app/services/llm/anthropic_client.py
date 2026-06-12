import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)

# Models that do not accept the temperature parameter
_NO_TEMPERATURE_MODELS = (
    "claude-opus-4-7",
    "claude-opus-4-8",
    "claude-fable-5",
    "claude-mythos-5",
)

_JSON_SUFFIX = "\n\nRespond only with valid JSON. Do not include any other text."


class AnthropicLLMClient(BaseLLMClient):
    def __init__(self, model: str, api_key: str) -> None:
        self._model = model
        self._api_key = api_key

    @property
    def model_name(self) -> str:
        return self._model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.8,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        import anthropic

        effective_system = system + _JSON_SUFFIX if json_mode else system

        kwargs: dict = dict(
            model=self._model,
            max_tokens=max_tokens,
            system=effective_system,
            messages=[{"role": "user", "content": user}],
        )
        # Newer Opus models (4.7+) and Fable 5 reject the temperature param
        if not any(self._model.startswith(m) for m in _NO_TEMPERATURE_MODELS):
            kwargs["temperature"] = temperature

        logger.debug("Anthropic request: model=%s json_mode=%s", self._model, json_mode)
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        response = await client.messages.create(**kwargs)

        for block in response.content:
            if block.type == "text":
                return block.text
        return ""
