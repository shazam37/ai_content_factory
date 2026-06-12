import json
import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.script_generation.base import BaseScriptGenerator, GeneratedScript
from app.services.script_generation.prompts import (
    NICHE_STYLE_GUIDE,
    SCRIPT_SYSTEM_PROMPT,
    SCRIPT_USER_PROMPT,
)

logger = logging.getLogger(__name__)


class OllamaScriptGenerator(BaseScriptGenerator):
    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.ollama_model
        self.base_url = settings.ollama_base_url

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _call_ollama(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.8,
                        "top_p": 0.9,
                        "num_predict": 2048,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]

    async def generate(
        self, topic: str, niche: str, style: str = "educational"
    ) -> GeneratedScript:
        style_guide = NICHE_STYLE_GUIDE.get(niche, "Be informative and engaging.")
        user_prompt = SCRIPT_USER_PROMPT.format(
            topic=topic, niche=niche, style_guide=style_guide
        )

        logger.info("Generating script for topic=%r niche=%s model=%s", topic, niche, self.model)
        raw = await self._call_ollama(SCRIPT_SYSTEM_PROMPT, user_prompt)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Extract JSON block if model added surrounding text
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start == -1 or end == 0:
                raise ValueError(f"Model returned non-JSON response: {raw[:200]}")
            data = json.loads(raw[start:end])

        scenes = data.get("scenes", [])
        if not scenes:
            # Synthesize scenes from main_content if missing
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
            model_used=self.model,
        )
