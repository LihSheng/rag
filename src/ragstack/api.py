from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Protocol

import jwt
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
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


class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str

SECRET_KEY = "dev_secret_key"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


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

    @app.post("/api/auth/login", response_model=TokenResponse)
    def login(payload: LoginRequest):
        if payload.username == "admin" and payload.password == "admin":
            access_token = create_access_token(data={"sub": payload.username})
            return {"access_token": access_token, "token_type": "bearer"}
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    @app.get("/api/admin/health")
    def admin_health(current_user: str = Depends(get_current_user)):
        # Provide extended system health for admin
        return {
            "status": "ok", 
            "pipeline": settings.default_pipeline,
            "document_count": 0, # Placeholder
            "storage_used": "150MB", # Placeholder
            "uptime": "24h" # Placeholder
        }

    @app.get("/api/admin/metrics")
    def admin_metrics(current_user: str = Depends(get_current_user)):
        # Phoenix performance metrics stub
        return {
            "query_latency_ms": 120,
            "retrieval_score": 0.85,
            "total_queries": 1500,
            "phoenix_integration": "pending"
        }

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
