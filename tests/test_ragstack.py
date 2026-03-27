from __future__ import annotations

import hashlib
import re
from pathlib import Path
from types import SimpleNamespace

from langchain_core.embeddings import Embeddings

from ragstack.config import Settings
from ragstack.langchain_pipeline.pipeline import LangChainRagPipeline
from ragstack.manual.pipeline import ManualRagPipeline
from ragstack.models import RetrievedChunk


FIXTURE_ROOT = Path(__file__).resolve().parents[1]


class FakeEmbeddingProvider(Embeddings):
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


class FakeReranker:
    def __init__(self) -> None:
        self.called = 0

    def rerank(self, question: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        self.called += 1
        return chunks[-1:][:top_k]


def make_settings(
    *,
    top_k: int = 5,
    min_context_score: float = 0.05,
    hybrid_enabled: bool = False,
    semantic_top_n: int = 20,
    bm25_top_n: int = 20,
    rrf_k: int = 60,
    rerank_enabled: bool = False,
    rerank_top_n: int = 20,
) -> Settings:
    return Settings(
        default_pipeline="manual",
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
        qdrant_active_alias="rag_active",
        source_dir=FIXTURE_ROOT / "data" / "corpus",
        eval_path=FIXTURE_ROOT / "data" / "eval" / "questions.json",
        chunk_size=1000,
        chunk_overlap=150,
        top_k=top_k,
        min_context_score=min_context_score,
        hybrid_enabled=hybrid_enabled,
        semantic_top_n=semantic_top_n,
        bm25_top_n=bm25_top_n,
        rrf_k=rrf_k,
        rerank_enabled=rerank_enabled,
        rerank_provider="token_overlap",
        rerank_model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        rerank_top_n=rerank_top_n,
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


def test_manual_ask_uses_reranker_when_configured() -> None:
    reranker = FakeReranker()
    pipeline = ManualRagPipeline(
        make_settings(min_context_score=0.0, rerank_enabled=True, top_k=5, rerank_top_n=20),
        embedding_provider=FakeEmbeddingProvider(),
        chat_provider=FakeChatProvider(),
        reranker=reranker,
    )
    pipeline.ingest()

    answer = pipeline.ask("How does Docker Compose help portability?")

    assert reranker.called == 1
    assert answer.insufficient_context is False
    assert len(answer.citations) == 1


def test_manual_hybrid_query_path_returns_results() -> None:
    pipeline = ManualRagPipeline(
        make_settings(hybrid_enabled=True, semantic_top_n=20, bm25_top_n=20, min_context_score=0.0),
        embedding_provider=FakeEmbeddingProvider(),
        chat_provider=FakeChatProvider(),
    )
    pipeline.ingest()

    answer = pipeline.ask("docker portability compose stack")

    assert answer.insufficient_context is False
    assert answer.citations


def test_langchain_ask_uses_reranker_when_configured() -> None:
    reranker = FakeReranker()
    pipeline = LangChainRagPipeline(
        make_settings(min_context_score=0.0, rerank_enabled=True, top_k=5, rerank_top_n=20),
        embeddings=FakeEmbeddingProvider(),
        chat_model=FakeLangChainChatModel(),
        reranker=reranker,
    )
    pipeline.ingest()

    answer = pipeline.ask("What keeps the manual and LangChain pipelines comparable?")

    assert reranker.called == 1
    assert answer.insufficient_context is False
    assert len(answer.citations) == 1
