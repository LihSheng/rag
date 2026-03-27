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
    family_id: str | None = None
    version_id: str | None = None
    is_active: bool = True

    def payload(self) -> dict[str, Any]:
        payload = {
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
        }
        if self.family_id:
            payload["family_id"] = self.family_id
        if self.version_id:
            payload["version_id"] = self.version_id
        return payload


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
