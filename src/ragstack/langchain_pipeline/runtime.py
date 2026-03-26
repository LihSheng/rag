from __future__ import annotations

from typing import Any

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from ragstack.config import Settings, strip_openai_api_suffix


def build_langchain_embeddings(settings: Settings) -> Any:
    if settings.embed_provider == "ollama":
        return OllamaEmbeddings(
            model=settings.embed_model,
            base_url=strip_openai_api_suffix(settings.embed_base_url),
        )

    if settings.embed_provider == "openai_compatible":
        kwargs: dict[str, Any] = {"model": settings.embed_model, "api_key": settings.embed_api_key}
        if settings.embed_base_url:
            kwargs["base_url"] = settings.embed_base_url
        return OpenAIEmbeddings(**kwargs)

    raise ValueError(f"Unsupported LangChain embedding provider: {settings.embed_provider}")


def build_langchain_chat_model(settings: Settings) -> Any:
    if settings.chat_provider == "ollama":
        return ChatOllama(
            model=settings.chat_model,
            base_url=strip_openai_api_suffix(settings.chat_base_url),
            temperature=0,
        )

    if settings.chat_provider == "openai_compatible":
        kwargs: dict[str, Any] = {
            "model": settings.chat_model,
            "api_key": settings.chat_api_key,
            "temperature": 0,
        }
        if settings.chat_base_url:
            kwargs["base_url"] = settings.chat_base_url
        return ChatOpenAI(**kwargs)

    raise ValueError(f"Unsupported LangChain chat provider: {settings.chat_provider}")


def extract_response_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "\n".join(part.strip() for part in parts if part.strip()).strip()

    return str(content).strip()

