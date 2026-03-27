from __future__ import annotations

from ragstack.models import RetrievedChunk

INSUFFICIENT_CONTEXT_ANSWER = "Insufficient context to answer from the indexed documents."

SYSTEM_PROMPT = (
    "You answer questions only from the retrieved context. "
    "If the context is insufficient, reply exactly with: "
    f"{INSUFFICIENT_CONTEXT_ANSWER} "
    # "When you answer, cite the supporting chunk IDs in square brackets."
)


def build_rag_messages(question: str, citations: list[RetrievedChunk]) -> list[dict[str, str]]:
    context_blocks: list[str] = []
    for chunk in citations:
        context_blocks.append(
            "\n".join(
                [
                    f"Chunk ID: {chunk.chunk_id}",
                    f"Source: {chunk.location()}",
                    f"Similarity score: {chunk.score:.4f}",
                    "Text:",
                    chunk.text,
                ]
            )
        )

    user_prompt = (
        f"Question: {question}\n\n"
        "Retrieved context:\n"
        f"{'\n\n'.join(context_blocks)}\n\n"
        "Answer using only the retrieved context."
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def has_sufficient_context(citations: list[RetrievedChunk], min_score: float) -> bool:
    if not citations:
        return False
    return max(citation.score for citation in citations) >= min_score


def ensure_citation_markers(answer: str, citations: list[RetrievedChunk]) -> str:
    if not citations:
        return answer

    if any(f"[{citation.chunk_id}]" in answer for citation in citations):
        return answer

    markers = " ".join(f"[{citation.chunk_id}]" for citation in citations[:3])
    return f"{answer}\n\nSupporting chunks: {markers}"
