from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

import ragstack.api as api_module
from ragstack.models import AnswerResult, RetrievedChunk

TEST_ADMIN_USERNAME = "admin-user"
TEST_ADMIN_PASSWORD = "admin-pass"
TEST_VIEWER_USERNAME = "viewer-user"
TEST_VIEWER_PASSWORD = "viewer-pass"


def _set_auth_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("ADMIN_USERNAME", TEST_ADMIN_USERNAME)
    monkeypatch.setenv("ADMIN_PASSWORD", TEST_ADMIN_PASSWORD)
    monkeypatch.setenv("VIEWER_USERNAME", TEST_VIEWER_USERNAME)
    monkeypatch.setenv("VIEWER_PASSWORD", TEST_VIEWER_PASSWORD)
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-with-minimum-32-bytes")


def _login_admin(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": TEST_ADMIN_USERNAME, "password": TEST_ADMIN_PASSWORD},
    )
    return str(response.json()["access_token"])


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
    _set_auth_env(monkeypatch)
    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FakePipeline("manual"))
    client = TestClient(api_module.create_app())

    response = client.post("/api/query", json={"question": "What keeps this stack portable?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "2026-03-27"
    assert payload["pipeline"] == "manual"
    assert payload["question"] == "What keeps this stack portable?"
    assert payload["citations"]


def test_query_success_langchain(monkeypatch) -> None:
    _set_auth_env(monkeypatch)
    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FakePipeline("langchain"))
    client = TestClient(api_module.create_app())

    response = client.post("/api/query", json={"question": "How does langchain path behave?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "2026-03-27"
    assert payload["pipeline"] == "langchain"


def test_query_rejects_empty_question() -> None:
    client = TestClient(api_module.create_app())

    response = client.post("/api/query", json={"question": "   "})

    assert response.status_code == 400
    assert response.json()["detail"] == "Question must not be empty."


def test_query_returns_stable_error_payload(monkeypatch) -> None:
    _set_auth_env(monkeypatch)
    class FailingPipeline:
        def ask(self, question: str) -> AnswerResult:
            raise RuntimeError("qdrant timeout")

    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FailingPipeline())
    client = TestClient(api_module.create_app())

    response = client.post("/api/query", json={"question": "test"})

    assert response.status_code == 500
    assert response.json() == {"error": "PIPELINE_ERROR", "message": "qdrant timeout"}


def test_admin_collections_normalizes_count_shapes(monkeypatch) -> None:
    _set_auth_env(monkeypatch)
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
        def record(
            self,
            *,
            action: str,
            target: str,
            actor: str,
            status: str,
            detail: str | None = None,
            job_id: str | None = None,
        ) -> None:
            del action, target, actor, status, detail, job_id

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

    token = _login_admin(client)
    response = client.get("/api/admin/qdrant/collections", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_collection"] == "alpha"
    assert payload["collections"] == [
        {"name": "alpha", "vectors_count": 5, "points_count": 5, "is_active": True},
        {"name": "beta", "vectors_count": 0, "points_count": 3, "is_active": False},
    ]


def test_admin_collection_ingest_upload(monkeypatch, tmp_path) -> None:
    _set_auth_env(monkeypatch)
    records: list[dict[str, object]] = []

    class FakeStats:
        indexed_files = 1
        indexed_chunks = 2
        skipped_files = 0

    class FakePipelineForIngest:
        def ask(self, question: str) -> AnswerResult:
            del question
            return FakePipeline("manual").ask("noop")

        def ingest(self, source_dir=None, collection_name=None):  # type: ignore[no-untyped-def]
            del collection_name
            files = list(source_dir.iterdir()) if source_dir is not None else []
            assert any(path.name == "sample.md" for path in files)
            return FakeStats()

    class FakeQdrantClient:
        def collection_exists(self, name: str) -> bool:
            return name == "alpha"

        def get_collections(self):  # type: ignore[no-untyped-def]
            return type("CollectionList", (), {"collections": []})()

        def get_aliases(self):  # type: ignore[no-untyped-def]
            return type("AliasList", (), {"aliases": []})()

    class FakeOpsLogStore:
        def record(
            self,
            *,
            action: str,
            target: str,
            actor: str,
            status: str,
            detail: str | None = None,
            job_id: str | None = None,
        ) -> None:
            records.append(
                {
                    "action": action,
                    "target": target,
                    "actor": actor,
                    "status": status,
                    "job_id": job_id,
                    "detail": detail,
                }
            )

        def recent(self, limit: int = 50) -> list[dict[str, object]]:
            del limit
            return []

    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FakePipelineForIngest())
    monkeypatch.setattr(api_module, "create_qdrant_client", lambda url: FakeQdrantClient())
    monkeypatch.setattr(
        api_module.OpsLogStore,
        "from_data_dir",
        classmethod(lambda cls, data_dir: FakeOpsLogStore()),
    )
    monkeypatch.setenv("SOURCE_DIR", str(tmp_path / "corpus"))

    client = TestClient(api_module.create_app())

    token = _login_admin(client)
    response = client.post(
        "/api/admin/qdrant/collections/alpha/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sample.md", b"# demo content", "text/markdown")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert response.json()["job_id"]
    statuses = [str(record["status"]) for record in records if record["action"] == "collection:ingest"]
    ingest_job_ids = {
        str(record["job_id"])
        for record in records
        if record["action"] == "collection:ingest" and record.get("job_id")
    }
    assert "queued" in statuses
    assert "running" in statuses
    assert "completed" in statuses
    assert len(ingest_job_ids) == 1
    assert response.json()["job_id"] in ingest_job_ids


def test_admin_collection_ingest_accepts_docx(monkeypatch, tmp_path) -> None:
    _set_auth_env(monkeypatch)
    class FakeStats:
        indexed_files = 1
        indexed_chunks = 1
        skipped_files = 0

    class FakePipelineForIngest:
        def ask(self, question: str) -> AnswerResult:
            del question
            return FakePipeline("manual").ask("noop")

        def ingest(self, source_dir=None, collection_name=None):  # type: ignore[no-untyped-def]
            del collection_name
            files = list(source_dir.iterdir()) if source_dir is not None else []
            assert any(path.suffix == ".docx" for path in files)
            return FakeStats()

    class FakeQdrantClient:
        def collection_exists(self, name: str) -> bool:
            return name == "alpha"

        def get_collections(self):  # type: ignore[no-untyped-def]
            return type("CollectionList", (), {"collections": []})()

        def get_aliases(self):  # type: ignore[no-untyped-def]
            return type("AliasList", (), {"aliases": []})()

    class FakeOpsLogStore:
        def record(
            self,
            *,
            action: str,
            target: str,
            actor: str,
            status: str,
            detail: str | None = None,
            job_id: str | None = None,
        ) -> None:
            del action, target, actor, status, detail, job_id

        def recent(self, limit: int = 50) -> list[dict[str, object]]:
            del limit
            return []

    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FakePipelineForIngest())
    monkeypatch.setattr(api_module, "create_qdrant_client", lambda url: FakeQdrantClient())
    monkeypatch.setattr(
        api_module.OpsLogStore,
        "from_data_dir",
        classmethod(lambda cls, data_dir: FakeOpsLogStore()),
    )
    monkeypatch.setenv("SOURCE_DIR", str(tmp_path / "corpus"))

    client = TestClient(api_module.create_app())
    token = _login_admin(client)

    response = client.post(
        "/api/admin/qdrant/collections/alpha/ingest",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sample.docx", b"fake docx bytes", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"


def test_admin_endpoints_reject_non_admin_user(monkeypatch) -> None:
    _set_auth_env(monkeypatch)
    class FakeOpsLogStore:
        def record(
            self,
            *,
            action: str,
            target: str,
            actor: str,
            status: str,
            detail: str | None = None,
            job_id: str | None = None,
        ) -> None:
            del action, target, actor, status, detail, job_id

        def recent(self, limit: int = 50) -> list[dict[str, object]]:
            del limit
            return []

    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FakePipeline("manual"))
    monkeypatch.setattr(
        api_module.OpsLogStore,
        "from_data_dir",
        classmethod(lambda cls, data_dir: FakeOpsLogStore()),
    )
    client = TestClient(api_module.create_app())

    login_response = client.post(
        "/api/auth/login",
        json={"username": TEST_VIEWER_USERNAME, "password": TEST_VIEWER_PASSWORD},
    )
    token = login_response.json()["access_token"]
    response = client.get("/api/admin/config", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_activate_collection_rejects_incompatible_fingerprint(monkeypatch) -> None:
    _set_auth_env(monkeypatch)
    class FakeCollectionInfo:
        points_count = 1

    class FakeQdrantClient:
        def collection_exists(self, name: str) -> bool:
            return name == "alpha"

        def get_collection(self, name: str) -> FakeCollectionInfo:
            del name
            return FakeCollectionInfo()

        def get_aliases(self):  # type: ignore[no-untyped-def]
            return type("AliasList", (), {"aliases": []})()

        def update_collection_aliases(self, change_aliases_operations):  # type: ignore[no-untyped-def]
            del change_aliases_operations
            raise AssertionError("Should not update aliases when fingerprint is incompatible")

    class FakeEmbeddingProvider:
        def embed_query(self, text: str) -> list[float]:
            del text
            return [0.1, 0.2, 0.3]

    class FakeOpsLogStore:
        def record(
            self,
            *,
            action: str,
            target: str,
            actor: str,
            status: str,
            detail: str | None = None,
            job_id: str | None = None,
        ) -> None:
            del action, target, actor, status, detail, job_id

        def recent(self, limit: int = 50) -> list[dict[str, object]]:
            del limit
            return []

    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FakePipeline("manual"))
    monkeypatch.setattr(api_module, "create_qdrant_client", lambda url: FakeQdrantClient())
    monkeypatch.setattr(api_module, "collection_vector_sizes", lambda info: {3})
    monkeypatch.setattr(api_module, "detect_collection_embedding_fingerprint", lambda client, name: "wrong-fp")
    monkeypatch.setattr(api_module, "build_embedding_provider", lambda settings: FakeEmbeddingProvider())
    monkeypatch.setattr(
        api_module.OpsLogStore,
        "from_data_dir",
        classmethod(lambda cls, data_dir: FakeOpsLogStore()),
    )
    client = TestClient(api_module.create_app())

    token = _login_admin(client)
    response = client.post(
        "/api/admin/qdrant/collections/alpha/activate",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "Embedding fingerprint mismatch" in response.json()["detail"]


def test_login_rejects_old_demo_credentials(monkeypatch) -> None:
    _set_auth_env(monkeypatch)
    client = TestClient(api_module.create_app())

    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin"})

    assert response.status_code == 401


def test_admin_collection_backfill_returns_job_and_stats(monkeypatch) -> None:
    _set_auth_env(monkeypatch)
    records: list[dict[str, object]] = []

    class FakeQdrantClient:
        def collection_exists(self, name: str) -> bool:
            return name == "alpha"

    class FakeOpsLogStore:
        def record(
            self,
            *,
            action: str,
            target: str,
            actor: str,
            status: str,
            detail: str | None = None,
            job_id: str | None = None,
        ) -> None:
            records.append(
                {
                    "action": action,
                    "target": target,
                    "actor": actor,
                    "status": status,
                    "detail": detail,
                    "job_id": job_id,
                }
            )

        def recent(self, limit: int = 50) -> list[dict[str, object]]:
            del limit
            return []

    monkeypatch.setattr(api_module, "_build_pipeline", lambda settings: FakePipeline("manual"))
    monkeypatch.setattr(api_module, "create_qdrant_client", lambda url: FakeQdrantClient())
    monkeypatch.setattr(
        api_module,
        "backfill_collection_metadata",
        lambda client, collection_name, default_tenant_id, default_access_tags, embedding_fingerprint, dry_run: {
            "total_points": 5,
            "missing_points": 2,
            "updated_points": 0 if dry_run else 2,
            "missing_field_counts": {"tenant_id": 2},
            "dry_run": dry_run,
        },
    )
    monkeypatch.setattr(
        api_module.OpsLogStore,
        "from_data_dir",
        classmethod(lambda cls, data_dir: FakeOpsLogStore()),
    )
    client = TestClient(api_module.create_app())

    token = _login_admin(client)
    response = client.post(
        "/api/admin/qdrant/collections/alpha/backfill",
        params={"apply": "false"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["job_id"]
    assert payload["result"]["collection_name"] == "alpha"
    assert payload["result"]["dry_run"] is True
    statuses = [str(record["status"]) for record in records if record["action"] == "collection:backfill"]
    job_ids = {
        str(record["job_id"])
        for record in records
        if record["action"] == "collection:backfill" and record.get("job_id")
    }
    assert statuses == ["queued", "running", "completed"]
    assert len(job_ids) == 1
    assert payload["job_id"] in job_ids
