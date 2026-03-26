from __future__ import annotations

from pathlib import Path

from qdrant_client import QdrantClient

from ragstack.config import Settings
from ragstack.models import AnswerResult, ChunkRecord, IngestionStats, LoadedDocument
from ragstack.prompting import (
    INSUFFICIENT_CONTEXT_ANSWER,
    build_rag_messages,
    ensure_citation_markers,
    has_sufficient_context,
)
from ragstack.providers import ChatProvider, EmbeddingProvider, build_chat_provider, build_embedding_provider
from ragstack.qdrant_store import (
    create_qdrant_client,
    delete_document,
    ensure_collection,
    indexed_documents,
    query_similar_chunks,
    upsert_chunk_batch,
)
from ragstack.text_utils import batched, chunk_text

from .loaders import load_corpus_documents


def chunk_loaded_document(
    document: LoadedDocument,
    pipeline: str,
    chunk_size: int,
    overlap: int,
) -> list[ChunkRecord]:
    chunks: list[ChunkRecord] = []
    chunk_index = 0

    for segment in document.segments:
        for text in chunk_text(segment.text, chunk_size=chunk_size, overlap=overlap):
            chunks.append(
                ChunkRecord(
                    document_id=document.document_id,
                    chunk_id=f"{document.document_id}-chunk-{chunk_index:04d}",
                    source_path=document.source_path,
                    source_type=document.source_type,
                    checksum=document.checksum,
                    pipeline=pipeline,
                    text=text,
                    page=segment.page,
                    section=segment.section,
                )
            )
            chunk_index += 1

    return chunks


class ManualRagPipeline:
    def __init__(
        self,
        settings: Settings,
        embedding_provider: EmbeddingProvider | None = None,
        chat_provider: ChatProvider | None = None,
        qdrant_client: QdrantClient | None = None,
    ) -> None:
        self.settings = settings
        self.collection_name = settings.collection_name("manual")
        self.embedding_provider = embedding_provider or build_embedding_provider(settings)
        self.chat_provider = chat_provider or build_chat_provider(settings)
        self.client = qdrant_client or create_qdrant_client(settings.qdrant_url)

    def ingest(self, source_dir: Path | None = None) -> IngestionStats:
        source_dir = source_dir or self.settings.source_dir
        documents = load_corpus_documents(source_dir)
        known_documents = indexed_documents(self.client, self.collection_name)

        documents_to_index: list[LoadedDocument] = []
        deleted_documents = 0
        skipped_files = 0

        for document in documents:
            existing = known_documents.get(document.source_path)
            if existing and existing[0] == document.checksum:
                skipped_files += 1
                continue

            if existing:
                delete_document(self.client, self.collection_name, existing[1])
                deleted_documents += 1

            documents_to_index.append(document)

        chunk_buffer: list[ChunkRecord] = []
        for document in documents_to_index:
            chunk_buffer.extend(
                chunk_loaded_document(
                    document,
                    pipeline="manual",
                    chunk_size=self.settings.chunk_size,
                    overlap=self.settings.chunk_overlap,
                )
            )

        if chunk_buffer:
            vector_size = len(self.embedding_provider.embed_query("dimension probe"))
            ensure_collection(self.client, self.collection_name, vector_size)

            for chunk_batch in batched(chunk_buffer, 32):
                vectors = self.embedding_provider.embed_documents([chunk.text for chunk in chunk_batch])
                upsert_chunk_batch(self.client, self.collection_name, chunk_batch, vectors)

        indexed_files = sum(
            1
            for document in documents_to_index
            if any(chunk.document_id == document.document_id for chunk in chunk_buffer)
        )

        return IngestionStats(
            pipeline="manual",
            discovered_files=len(documents),
            indexed_files=indexed_files,
            skipped_files=skipped_files,
            indexed_chunks=len(chunk_buffer),
            deleted_documents=deleted_documents,
        )

    def ask(self, question: str) -> AnswerResult:
        query_vector = self.embedding_provider.embed_query(question)
        citations = query_similar_chunks(
            self.client,
            self.collection_name,
            query_vector=query_vector,
            limit=self.settings.top_k,
        )

        if not has_sufficient_context(citations, self.settings.min_context_score):
            return AnswerResult(
                pipeline="manual",
                question=question,
                answer=INSUFFICIENT_CONTEXT_ANSWER,
                citations=citations,
                insufficient_context=True,
            )

        answer = self.chat_provider.generate_answer(build_rag_messages(question, citations))
        answer = ensure_citation_markers(answer, citations)
        return AnswerResult(
            pipeline="manual",
            question=question,
            answer=answer,
            citations=citations,
            insufficient_context=False,
        )

