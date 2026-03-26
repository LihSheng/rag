from __future__ import annotations

import hashlib
import re
from pathlib import Path
from types import SimpleNamespace

from ragstack.config import Settings
from ragstack.langchain_pipeline.pipeline import LangChainRagPipeline
from ragstack.manual.pipeline import ManualRagPipeline


FIXTURE_ROOT = Path(__file__).resolve().parents[1]


class FakeEmbeddingProvider:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * 24
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int(hashlib.sha1(token.encode("utf-8")).hexdigest()[:8], 16) % len(vector)
            vector[bucket] += 1.0

        if not any(vector):
            vector[0] = 1.0
        return vector


class FakeChatProvider:
    def generate_answer(self, messages: list[dict[str, str]]) -> str:
        return "Manual pipeline test answer."


class FakeLangChainChatModel:
    def invoke(self, messages: list[object]) -> SimpleNamespace:
        return SimpleNamespace(content="LangChain pipeline test answer.")


def make_settings() -> Settings:
    return Settings(
        chat_provider="ollama",
        chat_base_url="http://localhost:11434/v1",
        chat_api_key="ollama",
        chat_model="qwen2.5:3b",
        embed_provider="ollama",
        embed_base_url="http://localhost:11434/v1",
        embed_api_key="ollama",
        embed_model="nomic-embed-text",
        qdrant_url=":memory:",
        qdrant_collection_prefix="rag",
        source_dir=FIXTURE_ROOT / "data" / "corpus",
        eval_path=FIXTURE_ROOT / "data" / "eval" / "questions.json",
        chunk_size=1000,
        chunk_overlap=150,
        top_k=5,
        min_context_score=0.05,
        bootstrap_ollama_url=None,
        bootstrap_qdrant_url=None,
        bootstrap_pull_models=False,
        bootstrap_wait_timeout=1,
    )


def test_manual_ingest_is_idempotent() -> None:
    pipeline = ManualRagPipeline(
        make_settings(),
        embedding_provider=FakeEmbeddingProvider(),
        chat_provider=FakeChatProvider(),
    )

    first = pipeline.ingest()
    second = pipeline.ingest()

    assert first.discovered_files >= 2
    assert first.indexed_files >= 2
    assert first.indexed_chunks > 0
    assert second.indexed_files == 0
    assert second.skipped_files == first.discovered_files


def test_manual_ask_returns_citations() -> None:
    pipeline = ManualRagPipeline(
        make_settings(),
        embedding_provider=FakeEmbeddingProvider(),
        chat_provider=FakeChatProvider(),
    )
    pipeline.ingest()

    answer = pipeline.ask("How does Docker Compose help portability?")

    assert answer.insufficient_context is False
    assert answer.citations
    assert any(citation.source_path.endswith(".md") or citation.source_path.endswith(".pdf") for citation in answer.citations)
    assert "[" in answer.answer


def test_langchain_ingest_and_ask() -> None:
    pipeline = LangChainRagPipeline(
        make_settings(),
        embeddings=FakeEmbeddingProvider(),
        chat_model=FakeLangChainChatModel(),
    )

    result = pipeline.ingest()
    answer = pipeline.ask("What keeps the manual and LangChain pipelines comparable?")

    assert result.discovered_files >= 2
    assert result.indexed_chunks > 0
    assert answer.insufficient_context is False
    assert answer.citations
    assert "[" in answer.answer
