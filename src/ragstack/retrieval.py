from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from ragstack.models import RetrievedChunk

TOKEN_RE = re.compile(r"[a-z0-9]+")


def bm25_rank(
    question: str,
    chunks: list[RetrievedChunk],
    limit: int,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[RetrievedChunk]:
    if not chunks or limit <= 0:
        return []

    query_tokens = _tokenize(question)
    if not query_tokens:
        return []

    tokenized_chunks = [_tokenize(chunk.text) for chunk in chunks]
    doc_freqs = _document_frequencies(tokenized_chunks)
    avg_doc_len = sum(len(tokens) for tokens in tokenized_chunks) / len(tokenized_chunks)

    scored_rows: list[tuple[float, int, RetrievedChunk]] = []
    for index, (chunk, tokens) in enumerate(zip(chunks, tokenized_chunks, strict=True)):
        tf = Counter(tokens)
        score = 0.0
        doc_len = len(tokens) or 1
        for term in query_tokens:
            df = doc_freqs.get(term, 0)
            if df == 0:
                continue

            idf = math.log(1.0 + (len(chunks) - df + 0.5) / (df + 0.5))
            freq = tf.get(term, 0)
            if freq == 0:
                continue

            denominator = freq + k1 * (1.0 - b + b * (doc_len / max(avg_doc_len, 1.0)))
            score += idf * ((freq * (k1 + 1.0)) / denominator)

        scored_rows.append((score, index, chunk))

    max_score = max((row[0] for row in scored_rows), default=0.0)
    ranked = sorted(scored_rows, key=lambda row: (row[0], -row[1]), reverse=True)

    results: list[RetrievedChunk] = []
    for raw_score, _, chunk in ranked[:limit]:
        normalized = raw_score / max_score if max_score > 0 else 0.0
        results.append(_copy_chunk_with_score(chunk, normalized))

    return results


def rrf_fuse(
    ranked_lists: list[list[RetrievedChunk]],
    k: int,
    limit: int,
) -> list[RetrievedChunk]:
    if not ranked_lists or limit <= 0:
        return []

    fused_scores: defaultdict[str, float] = defaultdict(float)
    best_source_score: dict[str, float] = {}
    canonical_chunk: dict[str, RetrievedChunk] = {}
    best_rank: dict[str, int] = {}
    list_hits: defaultdict[str, int] = defaultdict(int)

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            fused_scores[chunk.chunk_id] += 1.0 / (k + rank)
            list_hits[chunk.chunk_id] += 1
            if chunk.chunk_id not in canonical_chunk:
                canonical_chunk[chunk.chunk_id] = chunk
            best_source_score[chunk.chunk_id] = max(best_source_score.get(chunk.chunk_id, float("-inf")), chunk.score)
            best_rank[chunk.chunk_id] = min(best_rank.get(chunk.chunk_id, rank), rank)

    ordered_ids = sorted(
        fused_scores.keys(),
        key=lambda chunk_id: (
            fused_scores[chunk_id],
            list_hits[chunk_id],
            -best_rank[chunk_id],
            best_source_score[chunk_id],
        ),
        reverse=True,
    )

    results: list[RetrievedChunk] = []
    for chunk_id in ordered_ids[:limit]:
        base = canonical_chunk[chunk_id]
        results.append(_copy_chunk_with_score(base, best_source_score[chunk_id]))

    return results


def _tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def _document_frequencies(tokenized_docs: list[list[str]]) -> dict[str, int]:
    frequencies: dict[str, int] = {}
    for tokens in tokenized_docs:
        for token in set(tokens):
            frequencies[token] = frequencies.get(token, 0) + 1
    return frequencies


def _copy_chunk_with_score(chunk: RetrievedChunk, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk.chunk_id,
        source_path=chunk.source_path,
        source_type=chunk.source_type,
        checksum=chunk.checksum,
        pipeline=chunk.pipeline,
        text=chunk.text,
        score=score,
        document_id=chunk.document_id,
        page=chunk.page,
        section=chunk.section,
    )
