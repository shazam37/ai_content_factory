import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)


class GeminiLLMClient(BaseLLMClient):
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
        import google.generativeai as genai

        genai.configure(api_key=self._api_key)

        gen_config_kwargs: dict = dict(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if json_mode:
            gen_config_kwargs["response_mime_type"] = "application/json"

        model = genai.GenerativeModel(
            model_name=self._model,
            system_instruction=system,
            generation_config=genai.GenerationConfig(**gen_config_kwargs),
        )

        logger.debug("Gemini request: model=%s json_mode=%s", self._model, json_mode)
        response = await model.generate_content_async(user)
        return response.text or ""
