from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from ragstack.models import LoadedDocument, SourceSegment
from ragstack.text_utils import discover_source_files, normalize_text, sha256_bytes, stable_document_id

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def load_corpus_documents(source_dir: Path) -> list[LoadedDocument]:
    documents: list[LoadedDocument] = []
    for path in discover_source_files(source_dir):
        suffix = path.suffix.lower()
        if suffix in {".md", ".markdown"}:
            documents.append(_load_markdown_document(path, source_dir))
        elif suffix == ".pdf":
            documents.append(_load_pdf_document(path, source_dir))

    return documents


def _load_markdown_document(path: Path, source_dir: Path) -> LoadedDocument:
    raw_text = path.read_text(encoding="utf-8")
    relative_path = path.relative_to(source_dir).as_posix()
    checksum = sha256_bytes(path.read_bytes())
    segments: list[SourceSegment] = []

    for section, text in _split_markdown_sections(raw_text):
        normalized = normalize_text(text)
        if normalized:
            segments.append(SourceSegment(text=normalized, section=section))

    return LoadedDocument(
        document_id=stable_document_id(relative_path),
        source_path=relative_path,
        source_type="markdown",
        checksum=checksum,
        segments=segments,
    )


def _split_markdown_sections(text: str) -> list[tuple[str | None, str]]:
    section_stack: dict[int, str] = {}
    current_section: str | None = None
    current_lines: list[str] = []
    sections: list[tuple[str | None, str]] = []

    def flush_section() -> None:
        section_text = "\n".join(current_lines).strip()
        if section_text:
            sections.append((current_section, section_text))

    for line in text.splitlines():
        match = HEADING_RE.match(line.strip())
        if not match:
            current_lines.append(line)
            continue

        flush_section()
        current_lines = []
        level = len(match.group(1))
        heading = match.group(2).strip()

        for stale_level in [key for key in section_stack if key >= level]:
            section_stack.pop(stale_level, None)
        section_stack[level] = heading
        current_section = " > ".join(section_stack[index] for index in sorted(section_stack))
        current_lines.append(heading)

    flush_section()
    return sections


def _load_pdf_document(path: Path, source_dir: Path) -> LoadedDocument:
    reader = PdfReader(str(path))
    relative_path = path.relative_to(source_dir).as_posix()
    checksum = sha256_bytes(path.read_bytes())
    segments: list[SourceSegment] = []

    for page_index, page in enumerate(reader.pages, start=1):
        extracted_text = page.extract_text() or ""
        normalized = normalize_text(extracted_text)
        if normalized:
            segments.append(SourceSegment(text=normalized, page=page_index))

    return LoadedDocument(
        document_id=stable_document_id(relative_path),
        source_path=relative_path,
        source_type="pdf",
        checksum=checksum,
        segments=segments,
    )

