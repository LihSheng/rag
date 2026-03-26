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
