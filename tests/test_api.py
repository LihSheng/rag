from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

import ragstack.api as api_module
from ragstack.models import AnswerResult, RetrievedChunk


@dataclass
class FakePipeline:
    pipeline_name: str = "manual"

    def ask(self, question: str) -> AnswerResult:
        return AnswerResult(
            pipeline=self.pipeline_name,
            question=question,
            answer="Test answer [doc-1-chunk-0001]",
            citations=[
                RetrievedChunk(
                    chunk_id="doc-1-chunk-0001",
                    source_path="/workspace/data/corpus/rag-basics.md",
                    source_type="markdown",
                    checksum="abc123",
                    pipeline=self.pipeline_name,
                    text="Sample citation text",
                    score=0.92,
                    document_id="doc-1",
                    page=None,
                    section="Overview",
                )
            ],
            insufficient_context=False,
        )


def test_query_success_manual(monkeypatch) -> None:
    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FakePipeline("manual"))
    client = TestClient(api_module.create_app())

    response = client.post("/api/query", json={"question": "What keeps this stack portable?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["pipeline"] == "manual"
    assert payload["question"] == "What keeps this stack portable?"
    assert payload["citations"]


def test_query_success_langchain(monkeypatch) -> None:
    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FakePipeline("langchain"))
    client = TestClient(api_module.create_app())

    response = client.post("/api/query", json={"question": "How does langchain path behave?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["pipeline"] == "langchain"


def test_query_rejects_empty_question() -> None:
    client = TestClient(api_module.create_app())

    response = client.post("/api/query", json={"question": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "Question must not be empty."


def test_query_returns_stable_error_payload(monkeypatch) -> None:
    class FailingPipeline:
        def ask(self, question: str) -> AnswerResult:
            raise RuntimeError("qdrant timeout")

    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FailingPipeline())
    client = TestClient(api_module.create_app())

    response = client.post("/api/query", json={"question": "test"})

    assert response.status_code == 500
    assert response.json() == {"error": "PIPELINE_ERROR", "message": "qdrant timeout"}


def test_admin_collections_normalizes_count_shapes(monkeypatch) -> None:
    class FakeCollectionList:
        def __init__(self, names: list[str]) -> None:
            self.collections = [type("CollectionItem", (), {"name": name}) for name in names]

    class FakeCollectionInfo:
        def __init__(self, vectors_count: object, points_count: object) -> None:
            self.vectors_count = vectors_count
            self.points_count = points_count

    class FakeAlias:
        def __init__(self, alias_name: str, collection_name: str) -> None:
            self.alias_name = alias_name
            self.collection_name = collection_name

    class FakeAliasList:
        def __init__(self, aliases: list[FakeAlias]) -> None:
            self.aliases = aliases

    class FakeQdrantClient:
        def get_collections(self) -> FakeCollectionList:
            return FakeCollectionList(["alpha", "beta"])

        def get_collection(self, name: str) -> FakeCollectionInfo:
            if name == "alpha":
                return FakeCollectionInfo(vectors_count={"text": 3, "image": 2}, points_count=5)
            return FakeCollectionInfo(vectors_count=None, points_count={"segment_a": 1, "segment_b": 2})

        def get_aliases(self) -> FakeAliasList:
            return FakeAliasList([FakeAlias(alias_name="rag_active", collection_name="alpha")])

    class FakeOpsLogStore:
        def record(self, *, action: str, target: str, actor: str, status: str, detail: str | None = None) -> None:
            del action, target, actor, status, detail

        def recent(self, limit: int = 50) -> list[dict[str, object]]:
            del limit
            return []

    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FakePipeline("manual"))
    monkeypatch.setattr(api_module, "create_qdrant_client", lambda url: FakeQdrantClient())
    monkeypatch.setattr(
        api_module.OpsLogStore,
        "from_data_dir",
        classmethod(lambda cls, data_dir: FakeOpsLogStore()),
    )
    client = TestClient(api_module.create_app())

    login_response = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})
    token = login_response.json()["access_token"]
    response = client.get("/api/admin/qdrant/collections", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_collection"] == "alpha"
    assert payload["collections"] == [
        {"name": "alpha", "vectors_count": 5, "points_count": 5, "is_active": True},
        {"name": "beta", "vectors_count": 0, "points_count": 3, "is_active": False},
    ]
