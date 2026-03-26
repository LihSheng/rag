from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import OpenAI

from ragstack.config import Settings, normalize_openai_base_url


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class ChatProvider(Protocol):
    def generate_answer(self, messages: list[dict[str, str]]) -> str:
        ...


@dataclass
class OpenAICompatibleEmbeddingProvider:
    model: str
    api_key: str
    base_url: str | None = None

    def __post_init__(self) -> None:
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self.model, input=texts)
        sorted_rows = sorted(response.data, key=lambda row: row.index)
        return [list(row.embedding) for row in sorted_rows]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


@dataclass
class OllamaEmbeddingProvider(OpenAICompatibleEmbeddingProvider):
    def __init__(self, model: str, api_key: str = "ollama", base_url: str | None = None) -> None:
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=normalize_openai_base_url(base_url or "http://localhost:11434"),
        )


@dataclass
class OpenAICompatibleChatProvider:
    model: str
    api_key: str
    base_url: str | None = None

    def __post_init__(self) -> None:
        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def generate_answer(self, messages: list[dict[str, str]]) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0,
        )
        content = response.choices[0].message.content or ""
        return content.strip()


@dataclass
class OllamaChatProvider(OpenAICompatibleChatProvider):
    def __init__(self, model: str, api_key: str = "ollama", base_url: str | None = None) -> None:
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=normalize_openai_base_url(base_url or "http://localhost:11434"),
        )


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embed_provider == "ollama":
        return OllamaEmbeddingProvider(
            model=settings.embed_model,
            api_key=settings.embed_api_key or "ollama",
            base_url=settings.embed_base_url,
        )

    if settings.embed_provider == "openai_compatible":
        return OpenAICompatibleEmbeddingProvider(
            model=settings.embed_model,
            api_key=settings.embed_api_key,
            base_url=settings.embed_base_url,
        )

    raise ValueError(f"Unsupported embedding provider: {settings.embed_provider}")


def build_chat_provider(settings: Settings) -> ChatProvider:
    if settings.chat_provider == "ollama":
        return OllamaChatProvider(
            model=settings.chat_model,
            api_key=settings.chat_api_key or "ollama",
            base_url=settings.chat_base_url,
        )

    if settings.chat_provider == "openai_compatible":
        return OpenAICompatibleChatProvider(
            model=settings.chat_model,
            api_key=settings.chat_api_key,
            base_url=settings.chat_base_url,
        )

    raise ValueError(f"Unsupported chat provider: {settings.chat_provider}")

