from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import (
    BaseChatModel,
)

from config.settings import settings


def _create_ollama_llm() -> BaseChatModel:
    """
    Create the configured local Ollama model.
    """

    from langchain_ollama import ChatOllama

    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=(
            settings.ollama_temperature
        ),
        num_predict=(
            settings.ollama_num_predict
        ),
        num_ctx=(
            settings.ollama_context_size
        ),
        validate_model_on_init=True,
    )


def _create_gemini_llm() -> BaseChatModel:
    """
    Create Gemini when selected as the provider.
    """

    from langchain_google_genai import (
        ChatGoogleGenerativeAI,
    )

    arguments: dict[str, Any] = {
        "model": settings.llm_model,
        "google_api_key": (
            settings.gemini_api_key
        ),
        "max_retries": (
            settings.llm_max_retries
        ),
        "timeout": (
            settings.llm_timeout_seconds
        ),
    }

    fixed_sampling_models = {
        "gemini-3.5-flash-lite",
    }

    if (
        settings.llm_model
        not in fixed_sampling_models
    ):
        arguments["temperature"] = (
            settings.llm_temperature
        )

    return ChatGoogleGenerativeAI(
        **arguments
    )


def create_llm() -> BaseChatModel:
    """
    Create the selected model provider.

    All agents use this function, so provider selection
    remains centralized.
    """

    settings.validate_llm_configuration()

    provider = (
        settings.llm_provider.strip().lower()
    )

    if provider == "ollama":
        return _create_ollama_llm()

    if provider == "gemini":
        return _create_gemini_llm()

    raise ValueError(
        f"Unsupported LLM provider: {provider}"
    )