from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.documents import Document as LangDocument
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_qdrant import QdrantVectorStore, RetrievalMode
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient

from ragstack.config import Settings
from ragstack.models import AnswerResult, ChunkRecord, IngestionStats, LoadedDocument, RetrievedChunk
from ragstack.prompting import (
    INSUFFICIENT_CONTEXT_ANSWER,
    SYSTEM_PROMPT,
    ensure_citation_markers,
    has_sufficient_context,
)
from ragstack.qdrant_store import (
    create_qdrant_client,
    delete_document,
    ensure_collection,
    indexed_documents,
    qdrant_point_id,
    resolve_query_collection,
)
from ragstack.rerankers import Reranker, build_reranker

from ragstack.manual.loaders import load_corpus_documents
from ragstack.manual.pipeline import chunk_loaded_document

from .runtime import build_langchain_chat_model, build_langchain_embeddings, extract_response_text
from openinference.instrumentation.langchain import LangChainInstrumentor


class LangChainRagPipeline:
    def __init__(
        self,
        settings: Settings,
        qdrant_client: QdrantClient | None = None,
        embeddings: Any | None = None,
        chat_model: Any | None = None,
        reranker: Reranker | None = None,
    ) -> None:
        self.settings = settings
        self.collection_name = settings.collection_name("langchain")
        self.client = qdrant_client or create_qdrant_client(settings.qdrant_url)
        self.embeddings = embeddings or build_langchain_embeddings(settings)
        self.chat_model = chat_model or build_langchain_chat_model(settings)
        self.reranker = reranker or build_reranker(settings)
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", ". ", "? ", "! ", " "],
        )
        try:
            LangChainInstrumentor().instrument()
        except Exception:
            pass

    def ingest(self, source_dir: Path | None = None) -> IngestionStats:
        source_dir = source_dir or self.settings.source_dir
        documents = load_corpus_documents(source_dir)
        known_documents = indexed_documents(self.client, self.collection_name)

        deleted_documents = 0
        skipped_files = 0
        indexed_files = 0
        indexed_chunks = 0

        vector_size = len(self.embeddings.embed_query("dimension probe"))
        ensure_collection(self.client, self.collection_name, vector_size)
        vector_store = self._vector_store()

        for document in documents:
            existing = known_documents.get(document.source_path)
            if existing and existing[0] == document.checksum:
                skipped_files += 1
                continue

            if existing:
                delete_document(self.client, self.collection_name, existing[1])
                deleted_documents += 1

            langchain_docs, ids = self._build_langchain_documents(document)
            if not langchain_docs:
                continue

            vector_store.add_documents(documents=langchain_docs, ids=ids)
            indexed_files += 1
            indexed_chunks += len(langchain_docs)

        return IngestionStats(
            pipeline="langchain",
            discovered_files=len(documents),
            indexed_files=indexed_files,
            skipped_files=skipped_files,
            indexed_chunks=indexed_chunks,
            deleted_documents=deleted_documents,
        )

    def ask(self, question: str) -> AnswerResult:
        query_collection = resolve_query_collection(
            self.client,
            preferred_collection=self.settings.qdrant_active_alias,
            fallback_collection=self.collection_name,
        )
        vector_store = self._vector_store(collection_name=query_collection)
        retrieval_limit = self.settings.top_k
        if self.reranker:
            retrieval_limit = max(self.settings.rerank_top_n, self.settings.top_k)

        raw_results = vector_store.similarity_search_with_score(question, k=retrieval_limit)
        candidates = [self._retrieved_chunk(document, score) for document, score in raw_results]
        citations = candidates[: self.settings.top_k]
        if self.reranker:
            citations = self.reranker.rerank(
                question=question,
                chunks=candidates,
                top_k=self.settings.top_k,
            )

        if not has_sufficient_context(citations, self.settings.min_context_score):
            return AnswerResult(
                pipeline="langchain",
                question=question,
                answer=INSUFFICIENT_CONTEXT_ANSWER,
                citations=citations,
                insufficient_context=True,
            )

        user_prompt = (
            f"Question: {question}\n\n"
            "Retrieved context:\n"
            + "\n\n".join(
                [
                    "\n".join(
                        [
                            f"Chunk ID: {chunk.chunk_id}",
                            f"Source: {chunk.location()}",
                            f"Similarity score: {chunk.score:.4f}",
                            "Text:",
                            chunk.text,
                        ]
                    )
                    for chunk in citations
                ]
            )
            + "\n\nAnswer using only the retrieved context."
        )

        response = self.chat_model.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
        answer = ensure_citation_markers(extract_response_text(response), citations)
        return AnswerResult(
            pipeline="langchain",
            question=question,
            answer=answer,
            citations=citations,
            insufficient_context=False,
        )

    def _vector_store(self, collection_name: str | None = None) -> QdrantVectorStore:
        return QdrantVectorStore(
            client=self.client,
            collection_name=collection_name or self.collection_name,
            embedding=self.embeddings,
            retrieval_mode=RetrievalMode.DENSE,
        )

    def _build_langchain_documents(
        self,
        document: LoadedDocument,
    ) -> tuple[list[LangDocument], list[str]]:
        manual_chunks = chunk_loaded_document(
            document,
            pipeline="langchain",
            chunk_size=self.settings.chunk_size,
            overlap=self.settings.chunk_overlap,
        )

        seed_docs = [
            LangDocument(
                page_content=chunk.text,
                metadata={
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.chunk_id,
                    "source_path": chunk.source_path,
                    "source_type": chunk.source_type,
                    "page": chunk.page,
                    "section": chunk.section,
                    "text": chunk.text,
                    "checksum": chunk.checksum,
                    "pipeline": "langchain",
                },
            )
            for chunk in manual_chunks
        ]

        split_docs = self.splitter.split_documents(seed_docs)
        normalized_docs: list[LangDocument] = []
        ids: list[str] = []

        for index, doc in enumerate(split_docs):
            source_text = doc.page_content.strip()
            if not source_text:
                continue

            chunk_id = f"{document.document_id}-langchain-{index:04d}"
            payload_metadata = dict(doc.metadata)
            payload_metadata.update({"chunk_id": chunk_id, "text": source_text, "pipeline": "langchain"})
            normalized_docs.append(LangDocument(page_content=source_text, metadata=payload_metadata))
            ids.append(qdrant_point_id(chunk_id))

        return normalized_docs, ids

    def _retrieved_chunk(self, document: LangDocument, score: float) -> RetrievedChunk:
        metadata = document.metadata
        return RetrievedChunk(
            chunk_id=str(metadata.get("chunk_id", "")),
            source_path=str(metadata.get("source_path", "")),
            source_type=str(metadata.get("source_type", "")),
            checksum=str(metadata.get("checksum", "")),
            pipeline=str(metadata.get("pipeline", "langchain")),
            text=document.page_content,
            score=float(score),
            document_id=str(metadata.get("document_id", "")),
            page=_optional_int(metadata.get("page")),
            section=_optional_str(metadata.get("section")),
        )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)
