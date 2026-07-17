"""Core shared infrastructure for the research agent framework.

Provides the building blocks shared by both executor and coordinator:
- Agent: the ReAct loop
- AgentConfig: runtime configuration
- ContextManager: 4-layer context compression
- LLMProvider + implementations: LLM abstraction
- Tool + built-in tools: tool system
- GitManager / ExperimentTracker: experiment tracking
- create_provider: LLM provider factory
"""

from .agent import Agent
from .config import AgentConfig
from .context import ContextManager
from .experiment import ExperimentTracker, GitManager
from .llm.base import LLMProvider, LLMResponse

__all__ = [
    "Agent",
    "AgentConfig",
    "ContextManager",
    "ExperimentTracker",
    "GitManager",
    "LLMProvider",
    "LLMResponse",
    "create_provider",
    "resolve_backend",
]


def resolve_backend(provider: str | None, openai_api: str | None, model: str | None, base_url: str | None) -> str:
    """Collapse the (provider, openai_api) config onto one backend id.

    Returns one of: ``anthropic`` | ``gemini`` | ``openai-oauth`` |
    ``openai-responses`` | ``openai-chat`` | ``litellm``. ``provider="auto"``
    (the default) routes by model name: ``claude*`` → Anthropic, ``gemini*`` →
    Gemini Interactions API; everything else uses litellm.
    """
    p = (provider or "auto").lower()
    if p in ("claude", "anthropic"):
        return "anthropic"
    if p in ("gemini", "google"):
        return "gemini"
    if p in ("openai-oauth", "chatgpt", "openai_oauth"):
        return "openai-oauth"
    if p in ("openai-responses", "responses"):
        return "openai-responses"
    if p in ("openai-chat", "openai_compat", "chat"):
        return "openai-chat"
    if p == "litellm":
        return "litellm"
    if p == "openai":  # legacy two-axis form
        return "openai-chat" if (openai_api or "responses").lower() == "chat" else "openai-responses"
    if p == "auto":
        bare = (model or "").rsplit("/", 1)[-1].lower()
        if bare.startswith(("claude", "anthropic")) and not base_url:
            return "anthropic"
        if bare.startswith("gemini") and not base_url:
            return "gemini"
        return "litellm"
    return "litellm"  # unknown → most flexible path


def create_provider(config: AgentConfig) -> LLMProvider:
    """Create an LLM provider based on configuration.

    Shared factory used by both executor and coordinator.
    """
    backend = resolve_backend(config.provider, config.openai_api, config.model, config.base_url)

    if backend == "gemini":
        from .llm.gemini import GeminiInteractionsProvider
        return GeminiInteractionsProvider(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            max_retries=config.llm_provider_retries,
            timeout=config.llm_timeout,
            reasoning_effort=config.reasoning_effort,
        )
    if backend == "anthropic":
        from .llm.claude import ClaudeProvider
        return ClaudeProvider(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            max_retries=config.llm_provider_retries,
            timeout=config.llm_timeout,
            reasoning_effort=config.reasoning_effort,
            thinking_budget_tokens=config.thinking_budget_tokens,
        )
    if backend == "openai-oauth":
        from .llm.openai_oauth import OpenAIOAuthProvider
        return OpenAIOAuthProvider(
            model=config.model,
            max_retries=config.llm_provider_retries,
            timeout=config.llm_timeout,
            reasoning_effort=config.reasoning_effort,
            reasoning_summary=config.reasoning_summary,
            text_verbosity=config.text_verbosity,
            parallel_tool_calls=config.parallel_tool_calls,
        )
    if backend == "openai-responses":
        from .llm.openai_responses import OpenAIResponsesProvider
        return OpenAIResponsesProvider(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            max_retries=config.llm_provider_retries,
            timeout=config.llm_timeout,
            reasoning_effort=config.reasoning_effort,
            reasoning_summary=config.reasoning_summary,
            text_verbosity=config.text_verbosity,
            parallel_tool_calls=config.parallel_tool_calls,
        )
    if backend == "openai-chat":
        from .llm.openai_compat import OpenAICompatProvider
        return OpenAICompatProvider(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            max_retries=config.llm_provider_retries,
            timeout=config.llm_timeout,
        )
    # backend == "litellm": unified transport for the chat-completions family
    # (DeepSeek/Qwen/Gemini/OpenAI-compatible proxies). Reasoning chain is
    # preserved where the provider exposes it (thinking_blocks / reasoning_content
    # / Copilot opaque token); use openai-responses for the OpenAI encrypted chain.
    from .llm.litellm_provider import LiteLLMProvider
    return LiteLLMProvider(
        model=config.model,
        api_key=config.api_key,
        base_url=config.base_url,
        max_retries=config.llm_provider_retries,
        timeout=config.llm_timeout,
        reasoning_effort=config.reasoning_effort,
    )
