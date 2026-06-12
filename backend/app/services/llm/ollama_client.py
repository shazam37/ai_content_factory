import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


class OllamaLLMClient(BaseLLMClient):
    def __init__(self, model: str, base_url: str) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")

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
        payload: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "top_p": 0.9,
                "num_predict": max_tokens,
            },
        }
        if json_mode:
            payload["format"] = "json"

        logger.debug("Ollama request: model=%s json_mode=%s", self._model, json_mode)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            return response.json()["message"]["content"]
