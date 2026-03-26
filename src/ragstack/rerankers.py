from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from ragstack.config import Settings
from ragstack.models import RetrievedChunk


class Reranker(Protocol):
    def rerank(self, question: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        ...


@dataclass
class TokenOverlapReranker:
    def rerank(self, question: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        if not chunks:
            return []

        query_tokens = _tokenize(question)
        scored_rows = [
            (_overlap_score(query_tokens, _tokenize(chunk.text)), index, chunk)
            for index, chunk in enumerate(chunks)
        ]
        scored_rows.sort(key=lambda row: (row[0], -row[1]), reverse=True)
        return [row[2] for row in scored_rows[:top_k]]


@dataclass
class CrossEncoderReranker:
    model_name: str

    def __post_init__(self) -> None:
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover - depends on optional install
            raise RuntimeError(
                "Cross-encoder reranker requires sentence-transformers. "
                "Install with: pip install sentence-transformers"
            ) from exc

        self._model = CrossEncoder(self.model_name)

    def rerank(self, question: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        if not chunks:
            return []

        pairs = [(question, chunk.text) for chunk in chunks]
        scores = self._model.predict(pairs)
        scored_rows = [(float(score), index, chunk) for index, (score, chunk) in enumerate(zip(scores, chunks, strict=True))]
        scored_rows.sort(key=lambda row: (row[0], -row[1]), reverse=True)
        return [row[2] for row in scored_rows[:top_k]]


def build_reranker(settings: Settings) -> Reranker | None:
    if not settings.rerank_enabled:
        return None

    if settings.rerank_provider == "token_overlap":
        return TokenOverlapReranker()

    if settings.rerank_provider == "cross_encoder":
        return CrossEncoderReranker(settings.rerank_model)

    raise ValueError(f"Unsupported reranker provider: {settings.rerank_provider}")


TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(TOKEN_RE.findall(text.lower()))


def _overlap_score(query_tokens: set[str], text_tokens: set[str]) -> float:
    if not query_tokens or not text_tokens:
        return 0.0

    intersection = len(query_tokens & text_tokens)
    denominator = len(query_tokens | text_tokens)
    if denominator == 0:
        return 0.0
    return intersection / denominator
