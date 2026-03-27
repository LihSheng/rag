from __future__ import annotations

from datetime import datetime, timezone
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
    _create_payload_index(client, collection_name, "tenant_id", models.PayloadSchemaType.KEYWORD)
    _create_payload_index(client, collection_name, "doc_type", models.PayloadSchemaType.KEYWORD)
    _create_payload_index(client, collection_name, "created_at", models.PayloadSchemaType.KEYWORD)
    _create_payload_index(client, collection_name, "embedding_fingerprint", models.PayloadSchemaType.KEYWORD)


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


def collection_vector_sizes(collection_info: Any) -> set[int]:
    sizes: set[int] = set()
    config = getattr(collection_info, "config", None)
    params = getattr(config, "params", None) if config is not None else None
    vectors = getattr(params, "vectors", None) if params is not None else None
    _extract_vector_sizes(vectors, sizes)
    if sizes:
        return sizes

    try:
        dumped = collection_info.model_dump()
    except Exception:
        dumped = {}

    vectors_dump = dumped.get("config", {}).get("params", {}).get("vectors")
    _extract_vector_sizes(vectors_dump, sizes)
    return sizes


def detect_collection_embedding_fingerprint(client: QdrantClient, collection_name: str) -> str | None:
    if not client.collection_exists(collection_name):
        return None

    points, _ = client.scroll(
        collection_name=collection_name,
        limit=1,
        with_payload=["embedding_fingerprint"],
        with_vectors=False,
    )
    if not points:
        return None

    payload = points[0].payload or {}
    value = payload.get("embedding_fingerprint")
    if value in {None, ""}:
        return None
    return str(value)


def backfill_collection_metadata(
    client: QdrantClient,
    collection_name: str,
    *,
    default_tenant_id: str,
    default_access_tags: list[str],
    embedding_fingerprint: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    if not client.collection_exists(collection_name):
        return {
            "total_points": 0,
            "missing_points": 0,
            "updated_points": 0,
            "missing_field_counts": {},
            "dry_run": dry_run,
        }

    required_fields = ("tenant_id", "doc_type", "created_at", "access_tags", "embedding_fingerprint")
    missing_field_counts: dict[str, int] = {field: 0 for field in required_fields}
    total_points = 0
    missing_points = 0
    updated_points = 0
    offset: Any = None

    while True:
        points, offset = client.scroll(
            collection_name=collection_name,
            offset=offset,
            limit=256,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            total_points += 1
            payload = point.payload or {}
            updates: dict[str, Any] = {}

            if not payload.get("tenant_id"):
                updates["tenant_id"] = default_tenant_id
                missing_field_counts["tenant_id"] += 1
            if not payload.get("doc_type"):
                updates["doc_type"] = str(payload.get("source_type") or "unknown")
                missing_field_counts["doc_type"] += 1
            if not payload.get("created_at"):
                updates["created_at"] = _utc_iso()
                missing_field_counts["created_at"] += 1
            if not payload.get("access_tags"):
                updates["access_tags"] = default_access_tags
                missing_field_counts["access_tags"] += 1
            if not payload.get("embedding_fingerprint"):
                updates["embedding_fingerprint"] = embedding_fingerprint
                missing_field_counts["embedding_fingerprint"] += 1

            if updates:
                missing_points += 1
                if not dry_run:
                    client.set_payload(
                        collection_name=collection_name,
                        payload=updates,
                        points=[point.id],
                        wait=True,
                    )
                    updated_points += 1

        if offset is None:
            break

    return {
        "total_points": total_points,
        "missing_points": missing_points,
        "updated_points": updated_points,
        "missing_field_counts": missing_field_counts,
        "dry_run": dry_run,
    }




def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)


def _extract_vector_sizes(vectors: Any, output: set[int]) -> None:
    if vectors is None:
        return
    if isinstance(vectors, dict):
        if "size" in vectors and isinstance(vectors["size"], int):
            output.add(int(vectors["size"]))
            return
        for value in vectors.values():
            _extract_vector_sizes(value, output)
        return

    size = getattr(vectors, "size", None)
    if isinstance(size, int):
        output.add(size)
        return

    for attr in ("values", "vectors"):
        nested = getattr(vectors, attr, None)
        if nested is not None:
            _extract_vector_sizes(nested, output)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
