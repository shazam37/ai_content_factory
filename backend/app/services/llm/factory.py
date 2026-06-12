import logging

from app.services.llm.base import BaseLLMClient

logger = logging.getLogger(__name__)

# Explicit prefix → provider mapping (checked in order)
_PREFIX_PROVIDERS: list[tuple[str, str]] = [
    ("gpt-", "openai"),
    ("o1-", "openai"),
    ("o3-", "openai"),
    ("o4-", "openai"),
    ("claude-", "anthropic"),
    ("gemini-", "gemini"),
    ("palm-", "gemini"),
]

# Substrings that indicate a Groq-hosted open-source model
_GROQ_KEYWORDS = frozenset(
    ["llama", "mixtral", "mistral", "gemma", "whisper", "qwen-groq"]
)


def _infer_provider(model: str) -> str:
    m = model.lower()
    if ":" in m:
        return "ollama"
    for prefix, provider in _PREFIX_PROVIDERS:
        if m.startswith(prefix):
            return provider
    for kw in _GROQ_KEYWORDS:
        if kw in m:
            return "groq"
    # Unknown open-source model name — default to Groq
    return "groq"


def get_llm_client(settings, model: str | None = None) -> BaseLLMClient:
    """Create and return the appropriate LLM client based on settings."""
    effective_model = model or settings.llm_model or settings.ollama_model
    provider = (settings.llm_provider or "auto").lower()

    if provider == "auto":
        provider = _infer_provider(effective_model)
        logger.info("Auto-detected provider=%s for model=%s", provider, effective_model)

    if provider == "groq":
        from app.services.llm.groq_client import GroqLLMClient
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required for the Groq provider")
        return GroqLLMClient(model=effective_model, api_key=settings.groq_api_key)

    if provider == "openai":
        from app.services.llm.openai_client import OpenAILLMClient
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider")
        return OpenAILLMClient(model=effective_model, api_key=settings.openai_api_key)

    if provider == "anthropic":
        from app.services.llm.anthropic_client import AnthropicLLMClient
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        return AnthropicLLMClient(model=effective_model, api_key=settings.anthropic_api_key)

    if provider == "gemini":
        from app.services.llm.gemini_client import GeminiLLMClient
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for the Gemini provider")
        return GeminiLLMClient(model=effective_model, api_key=settings.gemini_api_key)

    if provider == "ollama":
        from app.services.llm.ollama_client import OllamaLLMClient
        return OllamaLLMClient(model=effective_model, base_url=settings.ollama_base_url)

    raise ValueError(
        f"Unknown LLM provider: {provider!r}. "
        "Valid values: groq, openai, anthropic, gemini, ollama, auto"
    )


def get_quality_client(settings) -> BaseLLMClient:
    """Return the LLM client for quality scoring (may use a lighter model)."""
    quality_model = (
        settings.llm_quality_model
        or settings.llm_model
        or settings.ollama_quality_model
    )
    return get_llm_client(settings, model=quality_model)
