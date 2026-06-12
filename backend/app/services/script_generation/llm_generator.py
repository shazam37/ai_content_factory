import json
import logging

from app.services.llm.base import BaseLLMClient
from app.services.script_generation.base import BaseScriptGenerator, GeneratedScript
from app.services.script_generation.prompts import (
    NICHE_STYLE_GUIDE,
    SCRIPT_SYSTEM_PROMPT,
    SCRIPT_USER_PROMPT,
)

logger = logging.getLogger(__name__)


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"No JSON found in LLM response: {raw[:200]}")
        return json.loads(raw[start:end])


class LLMScriptGenerator(BaseScriptGenerator):
    """Provider-agnostic script generator backed by any BaseLLMClient."""

    def __init__(self, client: BaseLLMClient) -> None:
        self._client = client

    async def generate(
        self, topic: str, niche: str, style: str = "educational"
    ) -> GeneratedScript:
        style_guide = NICHE_STYLE_GUIDE.get(niche, "Be informative and engaging.")
        user_prompt = SCRIPT_USER_PROMPT.format(
            topic=topic, niche=niche, style_guide=style_guide
        )

        logger.info(
            "Generating script: topic=%r niche=%s model=%s",
            topic,
            niche,
            self._client.model_name,
        )
        raw = await self._client.complete(
            system=SCRIPT_SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0.8,
            max_tokens=2048,
            json_mode=True,
        )

        data = _parse_json(raw)

        scenes = data.get("scenes", [])
        if not scenes:
            content = data.get("main_content", "")
            sentences = [s.strip() for s in content.split(".") if s.strip()]
            scenes = [
                {
                    "index": i,
                    "text": s + ".",
                    "image_prompt": f"{niche} educational illustration: {s[:50]}",
                    "duration_seconds": max(3.0, len(s.split()) * 0.4),
                }
                for i, s in enumerate(sentences[:6])
            ]

        return GeneratedScript(
            hook=data["hook"],
            main_content=data["main_content"],
            cta=data["cta"],
            title=data["title"],
            description=data["description"],
            hashtags=data.get("hashtags", []),
            scenes=scenes,
            estimated_duration_seconds=data.get("estimated_duration_seconds", 45),
            model_used=self._client.model_name,
        )
