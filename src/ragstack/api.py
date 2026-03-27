from __future__ import annotations

import logging
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol

import jwt
from qdrant_client import models as qdrant_models
from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ragstack.config import Settings
from ragstack.langchain_pipeline.pipeline import LangChainRagPipeline
from ragstack.manual.pipeline import ManualRagPipeline
from ragstack.models import AnswerResult
from ragstack.ops_log import OpsLogStore
from ragstack.providers import build_embedding_provider
from ragstack.qdrant_store import (
    backfill_collection_metadata,
    collection_vector_sizes,
    create_qdrant_client,
    detect_collection_embedding_fingerprint,
)

logger = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    question: str


class ApiError(BaseModel):
    error: str
    message: str


class QueryResponse(BaseModel):
    schema_version: str
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


class CreateCollectionRequest(BaseModel):
    name: str
    vector_size: int = 384
    distance: str = "cosine"


class AuthenticatedUser(BaseModel):
    username: str
    role: str


def _coerce_count(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, dict):
        return sum(_coerce_count(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return sum(_coerce_count(item) for item in value)
    return 0


def _collection_count(collection_info: Any, key: str, fallback_key: str | None = None) -> int:
    primary = getattr(collection_info, key, None)
    if primary is not None:
        return _coerce_count(primary)

    if fallback_key:
        fallback = getattr(collection_info, fallback_key, None)
        if fallback is not None:
            return _coerce_count(fallback)

    try:
        dumped = collection_info.model_dump()
    except Exception:
        dumped = {}

    if key in dumped:
        return _coerce_count(dumped.get(key))
    if fallback_key and fallback_key in dumped:
        return _coerce_count(dumped.get(fallback_key))
    return 0


oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/login')


def create_access_token(
    data: dict[str, Any],
    *,
    secret_key: str,
    algorithm: str,
    exp_hours: int,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=exp_hours)
    to_encode.update({'exp': expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def decode_access_token(
    token: str,
    *,
    secret_key: str,
    algorithm: str,
) -> AuthenticatedUser:
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        username = payload.get('sub')
        if username is None:
            raise HTTPException(status_code=401, detail='Invalid token')
        role = str(payload.get('role', 'user'))
        return AuthenticatedUser(username=str(username), role=role)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail='Invalid token') from exc


class RagPipeline(Protocol):
    def ask(self, question: str) -> AnswerResult:
        ...

    def ingest(self, source_dir: Path | None = None, collection_name: str | None = None) -> Any:
        ...


def _resolve_static_dir() -> Path:
    explicit = os.getenv('FRONTEND_DIST_DIR')
    if explicit:
        return Path(explicit)
    return Path('/opt/ragstack-ui')


def _build_pipeline(settings: Settings) -> RagPipeline:
    if settings.default_pipeline == 'manual':
        return ManualRagPipeline(settings)
    if settings.default_pipeline == 'langchain':
        return LangChainRagPipeline(settings)
    raise ValueError(f'Unsupported DEFAULT_PIPELINE: {settings.default_pipeline}')


def create_app() -> FastAPI:
    settings = Settings.from_env()
    app = FastAPI(title='RAGStack API')
    static_dir = _resolve_static_dir()
    pipeline = _build_pipeline(settings)
    ops_log = OpsLogStore.from_data_dir(settings.source_dir.parent)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_credentials=False,
        allow_methods=['*'],
        allow_headers=['*'],
    )

    def alias_target(client: Any) -> str | None:
        try:
            aliases = client.get_aliases()
            for alias_item in aliases.aliases:
                if alias_item.alias_name == settings.qdrant_active_alias:
                    return alias_item.collection_name
        except Exception:
            return None
        return None

    def get_current_user(token: str = Depends(oauth2_scheme)) -> AuthenticatedUser:
        return decode_access_token(
            token,
            secret_key=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )

    def require_admin(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return current_user

    def _ingest_uploaded_file(
        *,
        upload_dir: Path,
        collection_name: str,
        actor: str,
        original_name: str,
        job_id: str,
    ) -> None:
        ops_log.record(
            action="collection:ingest",
            target=collection_name,
            actor=actor,
            status="running",
            job_id=job_id,
            detail=original_name,
        )
        try:
            ingest_pipeline = _build_pipeline(settings)
            stats = ingest_pipeline.ingest(source_dir=upload_dir, collection_name=collection_name)
            ops_log.record(
                action="collection:ingest",
                target=collection_name,
                actor=actor,
                status="completed",
                job_id=job_id,
                detail=(
                    f"{original_name} indexed_files={stats.indexed_files} "
                    f"indexed_chunks={stats.indexed_chunks} skipped_files={stats.skipped_files}"
                ),
            )
        except Exception as exc:
            logger.exception("Collection ingest failed for %s", collection_name)
            ops_log.record(
                action="collection:ingest",
                target=collection_name,
                actor=actor,
                status="failed",
                job_id=job_id,
                detail=f"{original_name}: {exc}",
            )
        finally:
            shutil.rmtree(upload_dir, ignore_errors=True)

    @app.get('/api/health')
    def health() -> dict[str, str]:
        return {'status': 'ok', 'pipeline': settings.default_pipeline}

    @app.post('/api/auth/login', response_model=TokenResponse)
    def login(payload: LoginRequest) -> dict[str, str]:
        role = "user"
        if payload.username == settings.admin_username and payload.password == settings.admin_password:
            role = "admin"
        elif (
            settings.viewer_username
            and settings.viewer_password
            and payload.username == settings.viewer_username
            and payload.password == settings.viewer_password
        ):
            role = "user"
        else:
            raise HTTPException(status_code=401, detail='Incorrect username or password')

        access_token = create_access_token(
            data={'sub': payload.username, 'role': role},
            secret_key=settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
            exp_hours=settings.jwt_exp_hours,
        )
        return {'access_token': access_token, 'token_type': 'bearer'}

    @app.get('/api/admin/health')
    def admin_health(current_user: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
        del current_user
        client = create_qdrant_client(settings.qdrant_url)
        active_name = alias_target(client)
        points_count = 0
        if active_name and client.collection_exists(active_name):
            info = client.get_collection(active_name)
            points_count = info.points_count or 0
        return {
            'status': 'ok',
            'pipeline': settings.default_pipeline,
            'document_count': points_count,
            'storage_used': 'n/a',
            'uptime': '24h',
        }

    @app.get('/api/admin/metrics')
    def admin_metrics(current_user: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
        del current_user
        import httpx

        latency = 0
        total = 0
        integration = 'failed'

        try:
            query = '''
            query {
              project(name: "default") {
                traceCount
                latencyMs: traceLatencyNs(aggregation: AVERAGE)
              }
            }
            '''
            resp = httpx.post('http://phoenix:6006/graphql', json={'query': query}, timeout=2.0)

            if resp.status_code == 200:
                data = resp.json().get('data', {}).get('project', {})
                if data:
                    total = data.get('traceCount', 0)
                    latency_ns = data.get('latencyMs') or 0
                    latency = int(latency_ns / 1_000_000)
                integration = 'active'
        except Exception as exc:
            logging.getLogger(__name__).warning('Phoenix metrics fetch failed: %s', exc)

        return {
            'query_latency_ms': latency,
            'retrieval_score': 0.0,
            'total_queries': total,
            'phoenix_integration': integration,
        }

    @app.get('/api/admin/config')
    def get_config(current_user: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
        del current_user
        return {
            'pipeline': settings.default_pipeline,
            'top_k': settings.top_k,
            'hybrid_enabled': settings.hybrid_enabled,
        }

    @app.post('/api/admin/config')
    def update_config(payload: dict[str, Any], current_user: AuthenticatedUser = Depends(require_admin)) -> dict[str, str]:
        del payload, current_user
        return {'status': 'accepted', 'message': 'Configuration saved temporarily.'}

    @app.get('/api/admin/qdrant/collections')
    def list_qdrant_collections(current_user: AuthenticatedUser = Depends(require_admin)) -> dict[str, Any]:
        del current_user
        client = create_qdrant_client(settings.qdrant_url)
        active_name = alias_target(client)
        collections = client.get_collections().collections
        items: list[dict[str, Any]] = []
        for item in collections:
            collection_info = client.get_collection(item.name)
            vectors_count = _collection_count(collection_info, "vectors_count", "indexed_vectors_count")
            points_count = _collection_count(collection_info, "points_count")
            items.append(
                {
                    "name": item.name,
                    "vectors_count": vectors_count,
                    "points_count": points_count,
                    "is_active": item.name == active_name,
                }
            )
        return {"alias": settings.qdrant_active_alias, "active_collection": active_name, "collections": items}

    @app.post('/api/admin/qdrant/collections')
    def create_qdrant_collection(
        payload: CreateCollectionRequest,
        current_user: AuthenticatedUser = Depends(require_admin),
    ) -> dict[str, str]:
        client = create_qdrant_client(settings.qdrant_url)
        name = payload.name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="Collection name cannot be empty")
        if client.collection_exists(name):
            raise HTTPException(status_code=409, detail="Collection already exists")

        distance_map = {
            "cosine": qdrant_models.Distance.COSINE,
            "dot": qdrant_models.Distance.DOT,
            "euclid": qdrant_models.Distance.EUCLID,
        }
        distance_key = payload.distance.lower()
        if distance_key not in distance_map:
            raise HTTPException(status_code=400, detail="Unsupported distance metric")

        client.create_collection(
            collection_name=name,
            vectors_config=qdrant_models.VectorParams(
                size=payload.vector_size,
                distance=distance_map[distance_key],
            ),
            on_disk_payload=True,
        )
        ops_log.record(action="collection:create", target=name, actor=current_user.username, status="completed")
        return {"status": "ok", "message": f"Collection {name} created."}

    @app.post('/api/admin/qdrant/collections/{collection_name}/activate')
    def activate_qdrant_collection(
        collection_name: str,
        current_user: AuthenticatedUser = Depends(require_admin),
    ) -> dict[str, str]:
        client = create_qdrant_client(settings.qdrant_url)
        if not client.collection_exists(collection_name):
            raise HTTPException(status_code=404, detail="Collection not found")
        collection_info = client.get_collection(collection_name)
        points_count = _collection_count(collection_info, "points_count")
        try:
            expected_vector_size = len(build_embedding_provider(settings).embed_query("dimension probe"))
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Unable to validate embedding compatibility: {exc}",
            ) from exc
        target_vector_sizes = collection_vector_sizes(collection_info)
        if target_vector_sizes and expected_vector_size not in target_vector_sizes:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Incompatible vector size for collection {collection_name}. "
                    f"Expected {expected_vector_size}, got {sorted(target_vector_sizes)}."
                ),
            )

        expected_fingerprint = settings.embedding_fingerprint()
        target_fingerprint = detect_collection_embedding_fingerprint(client, collection_name)
        if target_fingerprint and target_fingerprint != expected_fingerprint:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Embedding fingerprint mismatch. "
                    f"Expected {expected_fingerprint}, got {target_fingerprint}."
                ),
            )
        if points_count > 0 and not target_fingerprint:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Collection does not include embedding fingerprint metadata. "
                    "Run metadata backfill before activation."
                ),
            )

        previous_target = alias_target(client)
        operations: list[qdrant_models.ChangeAliasesOperation] = []
        if previous_target:
            operations.append(
                qdrant_models.DeleteAliasOperation(
                    delete_alias=qdrant_models.DeleteAlias(alias_name=settings.qdrant_active_alias),
                )
            )
        operations.append(
            qdrant_models.CreateAliasOperation(
                create_alias=qdrant_models.CreateAlias(
                    collection_name=collection_name,
                    alias_name=settings.qdrant_active_alias,
                )
            )
        )
        client.update_collection_aliases(change_aliases_operations=operations)
        ops_log.record(action="collection:activate", target=collection_name, actor=current_user.username, status="completed")
        return {"status": "ok", "message": f"Active alias now points to {collection_name}."}

    @app.delete('/api/admin/qdrant/collections/{collection_name}')
    def delete_qdrant_collection(
        collection_name: str,
        current_user: AuthenticatedUser = Depends(require_admin),
    ) -> dict[str, str]:
        client = create_qdrant_client(settings.qdrant_url)
        if not client.collection_exists(collection_name):
            raise HTTPException(status_code=404, detail="Collection not found")
        active_name = alias_target(client)
        if active_name == collection_name:
            raise HTTPException(status_code=400, detail="Cannot delete active collection. Activate another first.")

        client.delete_collection(collection_name=collection_name)
        ops_log.record(action="collection:delete", target=collection_name, actor=current_user.username, status="completed")
        return {"status": "ok", "message": f"Collection {collection_name} deleted."}

    @app.post('/api/admin/qdrant/collections/{collection_name}/ingest')
    async def ingest_collection_file(
        collection_name: str,
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        current_user: AuthenticatedUser = Depends(require_admin),
    ) -> dict[str, str]:
        client = create_qdrant_client(settings.qdrant_url)
        if not client.collection_exists(collection_name):
            raise HTTPException(status_code=404, detail="Collection not found")
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename is required")

        original_name = Path(file.filename).name
        extension = Path(original_name).suffix.lower()
        allowed_extensions = {".md", ".markdown", ".pdf", ".txt", ".docx"}
        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Allowed: .md, .markdown, .pdf, .txt, .docx",
            )

        upload_root = Path(tempfile.mkdtemp(prefix="rag-admin-ingest-"))
        target_file = upload_root / original_name
        try:
            content = await file.read()
            target_file.write_bytes(content)
        finally:
            await file.close()

        job_id = OpsLogStore.new_job_id()
        ops_log.record(
            action="collection:ingest",
            target=collection_name,
            actor=current_user.username,
            status="queued",
            job_id=job_id,
            detail=original_name,
        )
        background_tasks.add_task(
            _ingest_uploaded_file,
            upload_dir=upload_root,
            collection_name=collection_name,
            actor=current_user.username,
            original_name=original_name,
            job_id=job_id,
        )
        return {
            "status": "accepted",
            "job_id": job_id,
            "message": f"Ingest queued for {original_name}.",
        }

    @app.post('/api/admin/qdrant/collections/{collection_name}/backfill')
    def backfill_collection(
        collection_name: str,
        apply: bool = False,
        current_user: AuthenticatedUser = Depends(require_admin),
    ) -> dict[str, Any]:
        client = create_qdrant_client(settings.qdrant_url)
        if not client.collection_exists(collection_name):
            raise HTTPException(status_code=404, detail="Collection not found")

        dry_run = not apply
        job_id = OpsLogStore.new_job_id()
        ops_log.record(
            action="collection:backfill",
            target=collection_name,
            actor=current_user.username,
            status="queued",
            job_id=job_id,
            detail=f"dry_run={dry_run}",
        )
        ops_log.record(
            action="collection:backfill",
            target=collection_name,
            actor=current_user.username,
            status="running",
            job_id=job_id,
            detail=f"dry_run={dry_run}",
        )
        try:
            result = backfill_collection_metadata(
                client,
                collection_name,
                default_tenant_id=settings.default_tenant_id,
                default_access_tags=[tag.strip() for tag in settings.default_access_tags.split(",") if tag.strip()],
                embedding_fingerprint=settings.embedding_fingerprint(),
                dry_run=dry_run,
            )
            ops_log.record(
                action="collection:backfill",
                target=collection_name,
                actor=current_user.username,
                status="completed",
                job_id=job_id,
                detail=(
                    f"dry_run={dry_run} total_points={result['total_points']} "
                    f"missing_points={result['missing_points']} updated_points={result['updated_points']}"
                ),
            )
        except Exception as exc:
            ops_log.record(
                action="collection:backfill",
                target=collection_name,
                actor=current_user.username,
                status="failed",
                job_id=job_id,
                detail=str(exc),
            )
            raise HTTPException(status_code=500, detail=f"Backfill failed: {exc}") from exc

        return {
            "status": "ok",
            "job_id": job_id,
            "result": {
                "collection_name": collection_name,
                **result,
            },
        }

    @app.get('/api/admin/qdrant/operations')
    def list_admin_operations(current_user: AuthenticatedUser = Depends(require_admin)) -> list[dict[str, Any]]:
        del current_user
        return ops_log.recent(limit=80)

    @app.post('/api/query', response_model=QueryResponse, responses={500: {'model': ApiError}})
    def query(payload: QueryRequest) -> QueryResponse | JSONResponse:
        question = payload.question.strip()
        if not question:
            raise HTTPException(status_code=400, detail='Question must not be empty.')

        try:
            result = pipeline.ask(question)
        except HTTPException:
            raise
        except Exception as exc:  # pragma: no cover
            logger.exception('Query failed')
            return JSONResponse(
                status_code=500,
                content={
                    'error': 'PIPELINE_ERROR',
                    'message': str(exc),
                },
            )

        return QueryResponse(schema_version=settings.api_schema_version, **result.to_dict())

    if static_dir.exists():
        assets_dir = static_dir / 'assets'
        if assets_dir.exists():
            app.mount('/assets', StaticFiles(directory=assets_dir), name='assets')

        @app.get('/')
        def index() -> FileResponse:
            return FileResponse(static_dir / 'index.html')

        @app.get('/{path:path}')
        def spa(path: str) -> FileResponse:
            if path.startswith('api/'):
                raise HTTPException(status_code=404, detail='Not found')

            target = (static_dir / path).resolve()
            static_root = static_dir.resolve()
            if target.exists() and static_root in target.parents:
                return FileResponse(target)
            return FileResponse(static_dir / 'index.html')

    return app


from ragstack.bootstrap import ensure_telemetry

ensure_telemetry()
app = create_app()
