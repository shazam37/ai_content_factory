import json
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.script_generation.base import GeneratedScript
from app.services.script_generation.prompts import QUALITY_PROMPT

logger = logging.getLogger(__name__)

MINIMUM_QUALITY_SCORE = 5.5


class QualityScorer:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.ollama_quality_model
        self.base_url = settings.ollama_base_url

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    async def score(self, script: GeneratedScript) -> tuple[float, dict]:
        prompt = QUALITY_PROMPT.format(
            hook=script.hook,
            main_content=script.main_content,
            cta=script.cta,
            title=script.title,
        )
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.2},
                },
            )
            response.raise_for_status()
            raw = response.json()["message"]["content"]

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}") + 1
            data = json.loads(raw[start:end]) if start != -1 else {}

        overall = float(data.get("overall_score", 5.0))
        return overall, data

    def passes_threshold(self, score: float) -> bool:
        return score >= MINIMUM_QUALITY_SCORE
