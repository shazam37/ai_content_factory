import json
import logging

from app.services.llm.base import BaseLLMClient
from app.services.script_generation.base import GeneratedScript
from app.services.script_generation.prompts import QUALITY_PROMPT

logger = logging.getLogger(__name__)

MINIMUM_QUALITY_SCORE = 5.5

_QUALITY_SYSTEM = (
    "You are a social media content quality evaluator. "
    "Respond only with a JSON object containing your scores and feedback."
)


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start != -1 and end > 0:
            return json.loads(raw[start:end])
        return {}


class QualityScorer:
    def __init__(self, client: BaseLLMClient) -> None:
        self._client = client

    async def score(self, script: GeneratedScript) -> tuple[float, dict]:
        prompt = QUALITY_PROMPT.format(
            hook=script.hook,
            main_content=script.main_content,
            cta=script.cta,
            title=script.title,
        )

        try:
            raw = await self._client.complete(
                system=_QUALITY_SYSTEM,
                user=prompt,
                temperature=0.2,
                max_tokens=1024,
                json_mode=True,
            )
            data = _parse_json(raw)
        except Exception as exc:
            logger.warning("Quality scoring failed (%s), using neutral score", exc)
            data = {}

        overall = float(data.get("overall_score", 5.0))
        return overall, data

    def passes_threshold(self, score: float) -> bool:
        return score >= MINIMUM_QUALITY_SCORE
