from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import QdrantClient, models

from ragstack.models import ChunkRecord, RetrievedChunk


def create_qdrant_client(qdrant_url: str) -> QdrantClient:
    normalized = qdrant_url.strip()
    if normalized in {":memory:", "memory://", "memory"}:
        return QdrantClient(":memory:")
    return QdrantClient(url=normalized)


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int) -> None:
    if client.collection_exists(collection_name):
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
        on_disk_payload=True,
    )

    _create_payload_index(client, collection_name, "document_id", models.PayloadSchemaType.KEYWORD)
    _create_payload_index(client, collection_name, "source_path", models.PayloadSchemaType.KEYWORD)
    _create_payload_index(client, collection_name, "source_type", models.PayloadSchemaType.KEYWORD)
    _create_payload_index(client, collection_name, "checksum", models.PayloadSchemaType.KEYWORD)
    _create_payload_index(client, collection_name, "pipeline", models.PayloadSchemaType.KEYWORD)
    _create_payload_index(client, collection_name, "is_active", models.PayloadSchemaType.BOOL)


def _create_payload_index(
    client: QdrantClient,
    collection_name: str,
    field_name: str,
    schema: models.PayloadSchemaType,
) -> None:
    try:
        client.create_payload_index(
            collection_name=collection_name,
            field_name=field_name,
            field_schema=schema,
        )
    except Exception:
        return


def indexed_documents(client: QdrantClient, collection_name: str) -> dict[str, tuple[str, str]]:
    if not client.collection_exists(collection_name):
        return {}

    results: dict[str, tuple[str, str]] = {}
    offset: Any = None

    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            offset=offset,
            limit=256,
            with_payload=["source_path", "checksum", "document_id"],
            with_vectors=False,
        )

        for point in points:
            payload = point.payload or {}
            source_path = payload.get("source_path")
            checksum = payload.get("checksum")
            document_id = payload.get("document_id")
            if source_path and checksum and document_id:
                results[str(source_path)] = (str(checksum), str(document_id))

        if offset is None:
            break

    return results


def delete_document(
    client: QdrantClient,
    collection_name: str,
    document_id: str,
    payload_key: str = "document_id",
) -> None:
    if not client.collection_exists(collection_name):
        return

    client.delete(
        collection_name=collection_name,
        points_selector=models.Filter(
            must=[
                models.FieldCondition(
                    key=payload_key,
                    match=models.MatchValue(value=document_id),
                )
            ]
        ),
        wait=True,
    )


def upsert_chunk_batch(
    client: QdrantClient,
    collection_name: str,
    chunks: list[ChunkRecord],
    vectors: list[list[float]],
) -> None:
    points = [
        models.PointStruct(
            id=qdrant_point_id(chunk.chunk_id),
            vector=vector,
            payload=chunk.payload(),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    client.upsert(collection_name=collection_name, points=points, wait=True)


def query_similar_chunks(
    client: QdrantClient,
    collection_name: str,
    query_vector: list[float],
    limit: int,
) -> list[RetrievedChunk]:
    if not client.collection_exists(collection_name):
        return []

    response = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=limit,
        query_filter=models.Filter(
            must_not=[
                models.FieldCondition(
                    key="is_active",
                    match=models.MatchValue(value=False),
                )
            ]
        ),
        with_payload=True,
        with_vectors=False,
    )

    points = response.points if hasattr(response, "points") else response
    results: list[RetrievedChunk] = []
    for point in points:
        payload = point.payload or {}
        results.append(
            RetrievedChunk(
                chunk_id=str(payload.get("chunk_id", point.id)),
                source_path=str(payload.get("source_path", "")),
                source_type=str(payload.get("source_type", "")),
                checksum=str(payload.get("checksum", "")),
                pipeline=str(payload.get("pipeline", "")),
                text=str(payload.get("text", "")),
                score=float(point.score),
                document_id=str(payload.get("document_id", "")),
                page=_optional_int(payload.get("page")),
                section=_optional_str(payload.get("section")),
            )
        )

    return results


def list_chunks(client: QdrantClient, collection_name: str) -> list[RetrievedChunk]:
    if not client.collection_exists(collection_name):
        return []

    results: list[RetrievedChunk] = []
    offset: Any = None

    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            offset=offset,
            limit=256,
            scroll_filter=models.Filter(
                must_not=[
                    models.FieldCondition(
                        key="is_active",
                        match=models.MatchValue(value=False),
                    )
                ]
            ),
            with_payload=True,
            with_vectors=False,
        )

        for point in points:
            payload = point.payload or {}
            results.append(
                RetrievedChunk(
                    chunk_id=str(payload.get("chunk_id", point.id)),
                    source_path=str(payload.get("source_path", "")),
                    source_type=str(payload.get("source_type", "")),
                    checksum=str(payload.get("checksum", "")),
                    pipeline=str(payload.get("pipeline", "")),
                    text=str(payload.get("text", "")),
                    score=0.0,
                    document_id=str(payload.get("document_id", "")),
                    page=_optional_int(payload.get("page")),
                    section=_optional_str(payload.get("section")),
                )
            )

        if offset is None:
            break

    return results


def qdrant_point_id(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, value))


def resolve_query_collection(
    client: QdrantClient,
    preferred_collection: str,
    fallback_collection: str,
) -> str:
    if client.collection_exists(preferred_collection):
        return preferred_collection
    return fallback_collection




def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)
