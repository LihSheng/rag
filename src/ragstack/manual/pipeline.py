from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from qdrant_client import QdrantClient

from ragstack.config import Settings
from ragstack.models import AnswerResult, BackfillStats, ChunkRecord, IngestionStats, LoadedDocument
from ragstack.prompting import (
    INSUFFICIENT_CONTEXT_ANSWER,
    build_rag_messages,
    ensure_citation_markers,
    has_sufficient_context,
)
from ragstack.providers import ChatProvider, EmbeddingProvider, build_chat_provider, build_embedding_provider
from ragstack.qdrant_store import (
    backfill_collection_metadata,
    create_qdrant_client,
    delete_document,
    ensure_collection,
    indexed_documents,
    list_chunks,
    query_similar_chunks,
    resolve_query_collection,
    upsert_chunk_batch,
)
from ragstack.retrieval import bm25_rank, rrf_fuse
from ragstack.rerankers import Reranker, build_reranker
from ragstack.text_utils import batched, chunk_text
from opentelemetry import trace as otel_trace

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
                    created_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
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
        reranker: Reranker | None = None,
        qdrant_client: QdrantClient | None = None,
    ) -> None:
        self.settings = settings
        self.collection_name = settings.collection_name("manual")
        self.embedding_provider = embedding_provider or build_embedding_provider(settings)
        self.chat_provider = chat_provider or build_chat_provider(settings)
        self.reranker = reranker or build_reranker(settings)
        self.client = qdrant_client or create_qdrant_client(settings.qdrant_url)
        self.embedding_fingerprint = settings.embedding_fingerprint()

    def ingest(self, source_dir: Path | None = None, collection_name: str | None = None) -> IngestionStats:
        source_dir = source_dir or self.settings.source_dir
        target_collection = collection_name or self.collection_name
        documents = load_corpus_documents(source_dir)
        known_documents = indexed_documents(self.client, target_collection)

        documents_to_index: list[LoadedDocument] = []
        deleted_documents = 0
        skipped_files = 0

        for document in documents:
            existing = known_documents.get(document.source_path)
            if existing and existing[0] == document.checksum:
                skipped_files += 1
                continue

            if existing:
                delete_document(self.client, target_collection, existing[1])
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
        chunk_buffer = [
            ChunkRecord(
                document_id=chunk.document_id,
                chunk_id=chunk.chunk_id,
                source_path=chunk.source_path,
                source_type=chunk.source_type,
                checksum=chunk.checksum,
                pipeline=chunk.pipeline,
                text=chunk.text,
                page=chunk.page,
                section=chunk.section,
                is_active=chunk.is_active,
                tenant_id=self.settings.default_tenant_id,
                doc_type=chunk.source_type,
                created_at=chunk.created_at,
                access_tags=[tag.strip() for tag in self.settings.default_access_tags.split(",") if tag.strip()],
                embedding_fingerprint=self.embedding_fingerprint,
            )
            for chunk in chunk_buffer
        ]

        if chunk_buffer:
            vector_size = len(self.embedding_provider.embed_query("dimension probe"))
            ensure_collection(self.client, target_collection, vector_size)

            for chunk_batch in batched(chunk_buffer, 32):
                vectors = self.embedding_provider.embed_documents([chunk.text for chunk in chunk_batch])
                upsert_chunk_batch(self.client, target_collection, chunk_batch, vectors)

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

    def backfill_metadata(self, *, dry_run: bool = True, collection_name: str | None = None) -> BackfillStats:
        target_collection = collection_name or self.collection_name
        result = backfill_collection_metadata(
            self.client,
            target_collection,
            default_tenant_id=self.settings.default_tenant_id,
            default_access_tags=[tag.strip() for tag in self.settings.default_access_tags.split(",") if tag.strip()],
            embedding_fingerprint=self.embedding_fingerprint,
            dry_run=dry_run,
        )
        return BackfillStats(
            pipeline="manual",
            collection_name=target_collection,
            total_points=int(result["total_points"]),
            missing_points=int(result["missing_points"]),
            updated_points=int(result["updated_points"]),
            missing_field_counts=dict(result["missing_field_counts"]),
            dry_run=bool(result["dry_run"]),
        )

    def ask(self, question: str) -> AnswerResult:
        tracer = otel_trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            "ManualPipeline.retrieve",
            attributes={"question": question, "openinference.span.kind": "RETRIEVER"}
        ) as retrieve_span:
            query_vector = self.embedding_provider.embed_query(question)
        active_collection = resolve_query_collection(
            self.client,
            preferred_collection=self.settings.qdrant_active_alias,
            fallback_collection=self.collection_name,
        )
        final_limit = self.settings.top_k
        if self.reranker:
            final_limit = max(self.settings.rerank_top_n, self.settings.top_k)

        semantic_limit = final_limit
        if self.settings.hybrid_enabled:
            semantic_limit = max(self.settings.semantic_top_n, final_limit)

        semantic_candidates = query_similar_chunks(
            self.client,
            active_collection,
            query_vector=query_vector,
            limit=semantic_limit,
        )
        candidates = semantic_candidates
        if self.settings.hybrid_enabled:
            lexical_pool = list_chunks(self.client, active_collection)
            lexical_limit = max(self.settings.bm25_top_n, final_limit)
            lexical_candidates = bm25_rank(
                question=question,
                chunks=lexical_pool,
                limit=lexical_limit,
            )
            candidates = rrf_fuse(
                ranked_lists=[semantic_candidates, lexical_candidates],
                k=self.settings.rrf_k,
                limit=max(len(semantic_candidates), len(lexical_candidates), final_limit),
            )

        citations = candidates[: self.settings.top_k]
        if self.reranker:
            citations = self.reranker.rerank(
                question=question,
                chunks=candidates,
                top_k=self.settings.top_k,
            )

        if not has_sufficient_context(citations, self.settings.min_context_score):
            return AnswerResult(
                pipeline="manual",
                question=question,
                answer=INSUFFICIENT_CONTEXT_ANSWER,
                citations=citations,
                insufficient_context=True,
            )

        with tracer.start_as_current_span(
            "ManualPipeline.generate",
            attributes={"openinference.span.kind": "LLM"}
        ) as llm_span:
            answer = self.chat_provider.generate_answer(build_rag_messages(question, citations))
            
        answer = ensure_citation_markers(answer, citations)
        return AnswerResult(
            pipeline="manual",
            question=question,
            answer=answer,
            citations=citations,
            insufficient_context=False,
        )
