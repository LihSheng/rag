from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SourceSegment:
    text: str
    page: int | None = None
    section: str | None = None


@dataclass(frozen=True)
class LoadedDocument:
    document_id: str
    source_path: str
    source_type: str
    checksum: str
    segments: list[SourceSegment]


@dataclass(frozen=True)
class ChunkRecord:
    document_id: str
    chunk_id: str
    source_path: str
    source_type: str
    checksum: str
    pipeline: str
    text: str
    page: int | None = None
    section: str | None = None
    is_active: bool = True
    tenant_id: str | None = None
    doc_type: str | None = None
    created_at: str | None = None
    access_tags: list[str] | None = None
    embedding_fingerprint: str | None = None

    def payload(self) -> dict[str, Any]:
        return {
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "source_path": self.source_path,
            "source_type": self.source_type,
            "page": self.page,
            "section": self.section,
            "text": self.text,
            "checksum": self.checksum,
            "pipeline": self.pipeline,
            "is_active": self.is_active,
            "tenant_id": self.tenant_id,
            "doc_type": self.doc_type,
            "created_at": self.created_at,
            "access_tags": self.access_tags,
            "embedding_fingerprint": self.embedding_fingerprint,
        }


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    source_path: str
    source_type: str
    checksum: str
    pipeline: str
    text: str
    score: float
    document_id: str
    page: int | None = None
    section: str | None = None

    def location(self) -> str:
        parts = [self.source_path]
        if self.page is not None:
            parts.append(f"page {self.page}")
        if self.section:
            parts.append(f"section {self.section}")
        return " | ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnswerResult:
    pipeline: str
    question: str
    answer: str
    citations: list[RetrievedChunk]
    insufficient_context: bool

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["citations"] = [citation.to_dict() for citation in self.citations]
        return data


@dataclass(frozen=True)
class IngestionStats:
    pipeline: str
    discovered_files: int
    indexed_files: int
    skipped_files: int
    indexed_chunks: int
    deleted_documents: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BackfillStats:
    pipeline: str
    collection_name: str
    total_points: int
    missing_points: int
    updated_points: int
    missing_field_counts: dict[str, int]
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
