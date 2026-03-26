from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Iterable, Iterator, Sequence, TypeVar

T = TypeVar("T")

SUPPORTED_SUFFIXES = {".md", ".markdown", ".pdf"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_document_id(source_path: str) -> str:
    digest = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:16]
    stem = source_path.replace("/", "-").replace("\\", "-").replace(".", "-")
    return f"{stem}-{digest}"


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]

    cleaned: list[str] = []
    previous_blank = False
    for line in lines:
        if not line:
            if not previous_blank and cleaned:
                cleaned.append("")
            previous_blank = True
            continue

        cleaned.append(line)
        previous_blank = False

    return "\n".join(cleaned).strip()


def discover_source_files(source_dir: Path) -> list[Path]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    files = [
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    ]
    return sorted(files)


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []

    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    chunks: list[str] = []
    start = 0
    total_length = len(normalized)

    while start < total_length:
        end = min(start + chunk_size, total_length)
        if end < total_length:
            adjusted = _find_breakpoint(normalized[start:end], int(chunk_size * 0.6))
            if adjusted is not None:
                end = start + adjusted

        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= total_length:
            break

        start = max(end - overlap, start + 1)

    return chunks


def _find_breakpoint(text: str, minimum_index: int) -> int | None:
    separators = ["\n\n", "\n", ". ", "? ", "! ", " "]
    best: int | None = None

    for separator in separators:
        candidate = text.rfind(separator)
        if candidate >= minimum_index:
            index = candidate + len(separator)
            if best is None or index > best:
                best = index

    return best


def batched(items: Sequence[T] | Iterable[T], batch_size: int) -> Iterator[list[T]]:
    batch: list[T] = []
    for item in items:
        batch.append(item)
        if len(batch) == batch_size:
            yield batch
            batch = []

    if batch:
        yield batch

