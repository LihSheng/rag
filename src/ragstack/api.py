from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Protocol

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ragstack.config import Settings
from ragstack.langchain_pipeline.pipeline import LangChainRagPipeline
from ragstack.manual.pipeline import ManualRagPipeline
from ragstack.models import AnswerResult


logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    question: str


class ApiError(BaseModel):
    error: str
    message: str


class QueryResponse(BaseModel):
    pipeline: str
    question: str
    answer: str
    citations: list[dict[str, object]]
    insufficient_context: bool


class RagPipeline(Protocol):
    def ask(self, question: str) -> AnswerResult:
        ...


def _resolve_static_dir() -> Path:
    explicit = os.getenv("FRONTEND_DIST_DIR")
    if explicit:
        return Path(explicit)
    return Path("/opt/ragstack-ui")


def _build_pipeline(settings: Settings) -> RagPipeline:
    if settings.default_pipeline == "manual":
        return ManualRagPipeline(settings)
    if settings.default_pipeline == "langchain":
        return LangChainRagPipeline(settings)
    raise ValueError(f"Unsupported DEFAULT_PIPELINE: {settings.default_pipeline}")


def create_app() -> FastAPI:
    settings = Settings.from_env()
    app = FastAPI(title="RAGStack API")
    static_dir = _resolve_static_dir()
    pipeline = _build_pipeline(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "pipeline": settings.default_pipeline}

    @app.post("/api/query", response_model=QueryResponse, responses={500: {"model": ApiError}})
    def query(payload: QueryRequest) -> QueryResponse | JSONResponse:
        question = payload.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail="Question must not be empty.")

        try:
            result = pipeline.ask(question)
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            logger.exception("Query failed")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "PIPELINE_ERROR",
                    "message": str(exc),
                },
            )

        return QueryResponse(**result.to_dict())

    if static_dir.exists():
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/")
        def index() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        @app.get("/{path:path}")
        def spa(path: str) -> FileResponse:
            if path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")

            target = (static_dir / path).resolve()
            static_root = static_dir.resolve()
            if target.exists() and static_root in target.parents:
                return FileResponse(target)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
