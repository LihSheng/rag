# Plan: Industry-Standard RAG System Functions

**Generated**: 2026-03-27
**Estimated Complexity**: High

## Overview
This plan upgrades the current RAGStack (manual + LangChain pipelines, FastAPI, Qdrant, React UI) into an industry-standard production RAG system with strong retrieval quality, governance, security, observability, and operator workflow.

Approach:
1. Harden existing foundations first (security, config, contracts).
2. Add production-grade ingestion/index lifecycle and retrieval quality controls.
3. Add governance, observability, evaluation, and release safeguards.
4. Finish with operator UX and rollout safety.

## Assumptions
- Existing stack remains: FastAPI + Qdrant + React + Docker Compose.
- Primary target is multi-tenant internal knowledge retrieval.
- Backward compatibility for `/api/query` remains unless explicitly versioned.

## Prerequisites
- Docker and Docker Compose available.
- Access to Qdrant and model endpoints used in `.env`.
- Test runner available (`pytest`, frontend tests).
- Baseline corpus and deployment paths are from this repo (`data/corpus`, `data/eval`, `frontend/`, `src/ragstack/`), with environment-specific paths documented per target runtime.

## Sprint 1: Foundation Hardening (Security + Contracts)
**Goal**: Remove critical security and contract risks before scaling features.
**Demo/Validation**:
- `pytest tests/test_api.py`
- `docker compose exec app ragstack manual ask "health check"`
- Manual auth test for admin routes.

### Task 1.1: Externalize auth secrets and token policy
- **Location**: `src/ragstack/api.py`, `src/ragstack/config.py`, `.env.example`
- **Description**: Replace hardcoded JWT secret and static expiry assumptions with env-configurable settings (`JWT_SECRET`, `JWT_ALGORITHM`, `JWT_EXP_HOURS`).
- **Dependencies**: None
- **Acceptance Criteria**:
  - No hardcoded secret remains in source.
  - Token expiration is configurable and enforced.
- **Validation**:
  - Auth login succeeds with valid credentials and fails with tampered token.

### Task 1.2: Introduce API versioned response contract
- **Location**: `src/ragstack/api.py`, `src/ragstack/models.py`, `tests/test_api.py`
- **Description**: Add contract version field and stable citation schema across manual/LangChain outputs.
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - `/api/query` responses include explicit schema version.
  - Tests lock contract shape.
- **Validation**:
  - Snapshot/contract tests pass.

### Task 1.3: Add role-safe admin guardrails
- **Location**: `src/ragstack/api.py`
- **Description**: Split authentication and authorization concerns, reserving admin endpoints for admin role claims.
- **Dependencies**: Task 1.1
- **Acceptance Criteria**:
  - Non-admin tokens are blocked from `/api/admin/*`.
- **Validation**:
  - API tests for 401/403 paths.

## Sprint 2: Ingestion and Index Lifecycle
**Goal**: Make ingestion reliable, repeatable, and production-safe.
**Demo/Validation**:
- Upload multiple files to admin ingest endpoint.
- Verify alias-switch workflow with zero query downtime.

### Task 2.1: Build ingestion job states and idempotency ledger
- **Location**: `src/ragstack/ops_log.py`, `src/ragstack/manual/pipeline.py`, `src/ragstack/langchain_pipeline/pipeline.py`
- **Description**: Persist ingestion job lifecycle (`queued`, `running`, `completed`, `failed`) with stable job IDs and source checksums.
- **Dependencies**: Sprint 1 complete
- **Acceptance Criteria**:
  - Re-upload of unchanged source is skipped deterministically.
  - Failures are visible via operations API with job ID.
- **Validation**:
  - Integration test with repeated ingest runs.

### Task 2.2: Add staging collection + atomic alias cutover
- **Location**: `src/ragstack/api.py`, `src/ragstack/qdrant_store.py`
- **Description**: Ingest into staging collection, run smoke checks, then atomically switch active alias.
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - Active alias only changes after successful ingest verification.
  - Alias activation validates embedding compatibility (vector dimension + embedding model fingerprint) between query path and target collection.
  - Rollback endpoint can restore previous alias target.
- **Validation**:
  - E2E script verifies old->new->rollback.
  - Activation test fails fast on incompatible vector schema/model fingerprint.

### Task 2.3: Enrich document metadata schema
- **Location**: `src/ragstack/models.py`, loaders in `src/ragstack/manual/loaders.py`
- **Description**: Normalize metadata (`tenant_id`, `doc_type`, `created_at`, `access_tags`) for downstream filtering.
- **Dependencies**: Task 2.1
- **Acceptance Criteria**:
  - Metadata present in Qdrant payload for all new chunks.
- **Validation**:
  - Qdrant payload inspection test.

### Task 2.4: Backfill strategy for existing indexed chunks
- **Location**: `src/ragstack/manual/pipeline.py`, `src/ragstack/langchain_pipeline/pipeline.py`, `src/ragstack/cli.py`
- **Description**: Add migration path for pre-existing chunks (reindex or metadata backfill mode) before mandatory tenant filtering is enforced.
- **Dependencies**: Task 2.3
- **Acceptance Criteria**:
  - No active collection serves mixed-schema data once tenant filters are enabled.
  - Rollout doc defines migration sequencing: backfill -> verify -> enforce filter.
- **Validation**:
  - Migration dry-run report + integration test on legacy fixture corpus.

## Sprint 3: Retrieval and Generation Quality
**Goal**: Improve answer quality, groundedness, and controllability.
**Demo/Validation**:
- Offline eval run with baseline vs improved configuration.
- Manual query checks with citation relevance.

### Task 3.1: Add query preprocessing and intent routing
- **Location**: `src/ragstack/prompting.py`, `src/ragstack/manual/pipeline.py`, `src/ragstack/langchain_pipeline/pipeline.py`
- **Description**: Add optional query rewrite/classification for question type (fact lookup, summarization, comparison).
- **Dependencies**: Sprint 2 complete
- **Acceptance Criteria**:
  - Pipeline chooses retrieval params by intent class.
- **Validation**:
  - Unit tests for intent mapping and fallback behavior.

### Task 3.2: Introduce retrieval policy profiles
- **Location**: `src/ragstack/config.py`, `src/ragstack/retrieval.py`
- **Description**: Define profile-based settings (semantic-heavy, hybrid-balanced, precision-first), selected per request or default.
- **Dependencies**: Task 3.1
- **Acceptance Criteria**:
  - Profiles change candidate pool, fusion, and rerank behavior without code edits.
- **Validation**:
  - Config tests + regression eval.

### Task 3.3: Grounded answer enforcement
- **Location**: `src/ragstack/prompting.py`, `src/ragstack/models.py`
- **Description**: Enforce answer format with explicit abstain policy when evidence is weak; require citation linkage.
- **Dependencies**: Task 3.2
- **Acceptance Criteria**:
  - Answers with low support return insufficiency consistently.
- **Validation**:
  - Eval set includes no-context queries and verifies abstain behavior.

### Task 3.4: Scale-safe hybrid retrieval
- **Location**: `src/ragstack/manual/pipeline.py`, `src/ragstack/qdrant_store.py`, `src/ragstack/retrieval.py`
- **Description**: Replace full-collection lexical scan with bounded candidate generation strategy (windowed lexical pool and capped fusion input).
- **Dependencies**: Task 3.2
- **Acceptance Criteria**:
  - Hybrid query latency does not grow linearly with total collection size for large corpora.
  - Candidate counts are explicitly capped and configurable.
- **Validation**:
  - Performance benchmark across small/medium/large corpora with latency budget checks.

## Sprint 4: Governance, Security, and Multi-Tenancy
**Goal**: Add access control and compliance-safe data handling.
**Demo/Validation**:
- Tenant A cannot retrieve Tenant B chunks.
- Admin audit trail available for operations.

### Task 4.1: Tenant-aware filtering at retrieval time
- **Location**: `src/ragstack/qdrant_store.py`, `src/ragstack/manual/pipeline.py`, `src/ragstack/langchain_pipeline/pipeline.py`, `src/ragstack/api.py`
- **Description**: Apply mandatory metadata filters (`tenant_id`, `access_tags`) on all query calls.
- **Dependencies**: Sprint 3 complete
- **Acceptance Criteria**:
  - Every query includes enforced filter clauses.
- **Validation**:
  - Security tests with cross-tenant data fixtures.

### Task 4.2: Ingestion-time redaction hooks
- **Location**: `src/ragstack/text_utils.py`, `src/ragstack/manual/loaders.py`
- **Description**: Add optional PII/secrets redaction pipeline before embedding/upsert.
- **Dependencies**: Task 4.1
- **Acceptance Criteria**:
  - Configurable redaction rules run before chunk storage.
- **Validation**:
  - Unit tests with synthetic secret patterns.

### Task 4.3: Structured audit logs
- **Location**: `src/ragstack/ops_log.py`, `src/ragstack/api.py`
- **Description**: Log query actor, collection alias, retrieval profile, and cited chunk IDs.
- **Dependencies**: Task 4.1
- **Acceptance Criteria**:
  - Query audit event exists for every `/api/query` request.
- **Validation**:
  - API integration test checks log emission.

## Sprint 5: Evaluation, Observability, and SLOs
**Goal**: Make quality and reliability measurable.
**Demo/Validation**:
- Dashboard/API returns latency and quality metrics.
- CI fails if regression threshold exceeded.

### Task 5.1: Expand evaluation harness with retrieval metrics
- **Location**: `src/ragstack/cli.py`, `data/eval/questions.json`, `tests/test_ragstack.py`
- **Description**: Extend `compare eval` to report precision@k, recall@k proxy, groundedness, and insufficiency precision.
- **Dependencies**: Sprint 4 complete
- **Acceptance Criteria**:
  - CLI outputs machine-readable metrics JSON and human summary.
  - Metric definitions and scoring rubric are versioned (`eval_spec_version`) and checked into repo.
  - Eval set contains labeled relevance judgments for citation-level scoring.
- **Validation**:
  - Golden eval run checked in for baseline.
  - Scorer unit tests validate metric computation against fixed fixtures.

### Task 5.2: Add request tracing and latency buckets
- **Location**: `src/ragstack/api.py`, `src/ragstack/ops_log.py`
- **Description**: Instrument pipeline stages (embed, retrieve, rerank, generate) with per-stage timing and trace IDs.
- **Dependencies**: Task 5.1
- **Acceptance Criteria**:
  - Each query exposes stage latency breakdown.
- **Validation**:
  - Observability endpoint and integration tests.

### Task 5.3: CI quality gates
- **Location**: project CI config (new), `tests/`
- **Description**: Add gates for unit tests, API contract tests, and minimum eval thresholds.
- **Dependencies**: Task 5.1
- **Acceptance Criteria**:
  - PR fails on metric regressions beyond configured budget.
  - Threshold policy is documented (absolute minimums + allowed regression delta) with baseline version pinning.
  - CI emits clear failure reason (which metric, expected vs observed, baseline version).
- **Validation**:
  - Simulated failing threshold run in CI.
  - Simulated baseline update flow with approval step.

## Sprint 6: Operator UX and Release Readiness
**Goal**: Make system usable and trustworthy for daily operations.
**Demo/Validation**:
- Query UI clearly shows groundedness, citations, and query trace summary.
- Admin can run ingest, activate collection, and monitor status end-to-end.

### Task 6.1: Enhance query UX trust panel
- **Location**: `frontend/src/pages/Search.tsx`, `frontend/src/types.ts`
- **Description**: Add retrieval profile label, stage latency summary, and stronger insufficient-context guidance in existing UI pattern.
- **Dependencies**: Sprint 5 complete
- **Acceptance Criteria**:
  - Query result displays trust state + diagnostics without clutter.
  - UI uses `DESIGN.md` typography, color, spacing, radius, and motion tokens without introducing off-system values.
  - Evidence drawer remains collapsed by default and user preference persists locally across reloads.
  - Trust state is always visible (`Grounded answer` vs `Insufficient context`).
  - Query input is preserved on API failure and a clear retry action is available.
- **Validation**:
  - Frontend tests + manual UX review against `DESIGN.md`.
  - Responsive visual checks at `<=768`, `769-1024`, and `>=1025` widths with screenshot artifacts.

### Task 6.2: Complete admin operations dashboard
- **Location**: `frontend/src/pages/AdminDashboard.tsx`, `src/ragstack/api.py`
- **Description**: Add ingestion job timeline, alias history, and safe rollback action.
- **Dependencies**: Tasks 2.2, 5.2
- **Acceptance Criteria**:
  - Operator can perform full index lifecycle from UI.
  - Admin screens follow `DESIGN.md` token system (type scale, spacing scale, palette, and component radius hierarchy).
  - No overloaded top navigation or decorative UI anti-patterns are introduced.
- **Validation**:
  - End-to-end admin workflow test.
  - Responsive visual checks at `<=768`, `769-1024`, and `>=1025` widths with screenshot artifacts.

### Task 6.3: Production runbook and incident playbook
- **Location**: `README.md` or new `docs/OPERATIONS.md`
- **Description**: Document SLOs, on-call checks, rollback steps, and failure triage commands.
- **Dependencies**: Task 6.2
- **Acceptance Criteria**:
  - Runbook covers ingest failure, model outage, and retrieval degradation.
- **Validation**:
  - Tabletop walkthrough with checklist.

## Testing Strategy
- Unit tests for parsing, retrieval ranking, reranking, filters, and auth.
- API contract tests for `/api/query` and `/api/admin/*`.
- Integration tests with Qdrant test collection fixtures.
- Offline eval benchmark tracked per sprint.
- Frontend tests for trust state and evidence interactions.
- Deterministic provider-fixture mode for CI (stubbed embeddings/generation + fixed seeds) to prevent flaky model-driven failures.

## Potential Risks and Gotchas
- **Hardcoded auth defaults** currently create immediate security risk if deployed.
  - Mitigation: Sprint 1 first, block release until complete.
- **Collection alias misuse** can cause query downtime or wrong index reads.
  - Mitigation: enforce staged ingest + validated cutover.
- **Over-aggressive redaction** may reduce retrieval quality.
  - Mitigation: start with dry-run redaction metrics before strict enforcement.
- **Rerank/profile drift** can silently change quality.
  - Mitigation: CI eval thresholds and baseline snapshots.
- **Multi-tenant filters missed in one path** can leak data.
  - Mitigation: centralize filter construction and test every pipeline path.

## Rollback Plan
1. Keep previous active Qdrant collection and alias metadata.
2. On regression, switch alias back to prior collection.
3. Disable new retrieval profile flags via env toggles.
4. Revert API contract additions behind version flag if clients break.
5. Restore prior frontend bundle while backend remains backward-compatible.

## Suggested Execution Order
1. Sprint 1 and Sprint 2 first (blockers for safe scale).
2. Sprint 3 and Sprint 4 next (quality + governance).
3. Sprint 5 and Sprint 6 to lock operations and release readiness.
