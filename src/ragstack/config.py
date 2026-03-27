from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

ProviderName = Literal["ollama", "openai_compatible"]
RerankProviderName = Literal["token_overlap", "cross_encoder"]
PipelineName = Literal["manual", "langchain"]


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    return int(value.strip())


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    return float(value.strip())


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(name: str, default: str) -> Path:
    return Path(_env_str(name, default)).expanduser()


def normalize_openai_base_url(base_url: str | None) -> str | None:
    if not base_url:
        return None

    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized
    return f"{normalized}/v1"


def strip_openai_api_suffix(base_url: str | None) -> str | None:
    if not base_url:
        return None

    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return normalized[:-3]
    return normalized


@dataclass(frozen=True)
class Settings:
    default_pipeline: PipelineName
    chat_provider: ProviderName
    chat_base_url: str | None
    chat_api_key: str
    chat_model: str
    embed_provider: ProviderName
    embed_base_url: str | None
    embed_api_key: str
    embed_model: str
    qdrant_url: str
    qdrant_collection_prefix: str
    qdrant_active_alias: str
    source_dir: Path
    eval_path: Path
    chunk_size: int
    chunk_overlap: int
    top_k: int
    min_context_score: float
    hybrid_enabled: bool
    semantic_top_n: int
    bm25_top_n: int
    rrf_k: int
    rerank_enabled: bool
    rerank_provider: RerankProviderName
    rerank_model: str
    rerank_top_n: int
    bootstrap_ollama_url: str | None
    bootstrap_qdrant_url: str | None
    bootstrap_pull_models: bool
    bootstrap_wait_timeout: int

    def collection_name(self, pipeline: str) -> str:
        return f"{self.qdrant_collection_prefix}_{pipeline}"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            default_pipeline=_env_str("DEFAULT_PIPELINE", "manual"),  # type: ignore[arg-type]
            chat_provider=_env_str("CHAT_PROVIDER", "ollama"),  # type: ignore[arg-type]
            chat_base_url=normalize_openai_base_url(
                _env_str("CHAT_BASE_URL", "http://localhost:11434/v1")
            ),
            chat_api_key=_env_str("CHAT_API_KEY", "ollama"),
            chat_model=_env_str("CHAT_MODEL", "qwen2.5:3b"),
            embed_provider=_env_str("EMBED_PROVIDER", "ollama"),  # type: ignore[arg-type]
            embed_base_url=normalize_openai_base_url(
                _env_str("EMBED_BASE_URL", "http://localhost:11434/v1")
            ),
            embed_api_key=_env_str("EMBED_API_KEY", "ollama"),
            embed_model=_env_str("EMBED_MODEL", "nomic-embed-text"),
            qdrant_url=_env_str("QDRANT_URL", "http://localhost:6333"),
            qdrant_collection_prefix=_env_str("QDRANT_COLLECTION_PREFIX", "rag"),
            qdrant_active_alias=_env_str("QDRANT_ACTIVE_ALIAS", "rag_active"),
            source_dir=_env_path("SOURCE_DIR", "data/corpus"),
            eval_path=_env_path("EVAL_PATH", "data/eval/questions.json"),
            chunk_size=_env_int("CHUNK_SIZE", 1000),
            chunk_overlap=_env_int("CHUNK_OVERLAP", 150),
            top_k=_env_int("TOP_K", 5),
            min_context_score=_env_float("MIN_CONTEXT_SCORE", 0.25),
            hybrid_enabled=_env_bool("HYBRID_ENABLED", False),
            semantic_top_n=_env_int("SEMANTIC_TOP_N", 20),
            bm25_top_n=_env_int("BM25_TOP_N", 20),
            rrf_k=_env_int("RRF_K", 60),
            rerank_enabled=_env_bool("RERANK_ENABLED", False),
            rerank_provider=_env_str("RERANK_PROVIDER", "token_overlap"),  # type: ignore[arg-type]
            rerank_model=_env_str("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2"),
            rerank_top_n=_env_int("RERANK_TOP_N", 20),
            bootstrap_ollama_url=strip_openai_api_suffix(
                os.getenv("BOOTSTRAP_OLLAMA_URL") or _env_str("CHAT_BASE_URL", "http://localhost:11434/v1")
            ),
            bootstrap_qdrant_url=os.getenv("BOOTSTRAP_QDRANT_URL") or _env_str("QDRANT_URL", "http://localhost:6333"),
            bootstrap_pull_models=_env_bool("BOOTSTRAP_PULL_MODELS", True),
            bootstrap_wait_timeout=_env_int("BOOTSTRAP_WAIT_TIMEOUT", 180),
        )
