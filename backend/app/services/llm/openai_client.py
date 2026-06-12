import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


class OpenAILLMClient(BaseLLMClient):
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
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._api_key)
        kwargs: dict = dict(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        logger.debug("OpenAI request: model=%s json_mode=%s", self._model, json_mode)
        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""
