# High-Volume Readiness Implementation Checklist

## Scope and Constraints
- [ ] Keep scope to foundation only: runtime hardening, external model endpoint support, Redis cache, load testing.
- [ ] Do not implement multi-region, queue orchestration, sharding, or full async rewrite in this cycle.
- [ ] Keep Ollama for local/dev profile; treat external provider as production profile.

## Success Criteria (Definition of Done)
- [ ] `/api/query` has defined SLO targets (p95 latency, error rate, throughput).
- [ ] Runtime supports configurable concurrency and timeout budgets.
- [ ] Cache layer is in place with versioned keys and TTL.
- [ ] Load test is repeatable and produces pass/fail output.
- [ ] Rollout/rollback can be controlled with environment flags.

## Phase 1 - Runtime Hardening
- [ ] Add configurable API worker count for Uvicorn startup.
- [ ] Add request timeout settings for query execution path.
- [ ] Add provider timeout and bounded retry settings for embedding/chat requests.
- [ ] Add request-level logging fields (`request_id`, latency, pipeline, provider).
- [ ] Add endpoint-level metrics for `/api/query` (count, latency, errors).
- [ ] Add environment variable documentation for all new runtime knobs.

## Phase 2 - Redis Cache Layer
- [ ] Add Redis service and connection settings.
- [ ] Add cache abstraction for query response caching.
- [ ] Implement deterministic cache key schema including:
- [ ] tenant_id
- [ ] pipeline
- [ ] normalized question hash
- [ ] embedding fingerprint
- [ ] retrieval knobs (`top_k`, hybrid/rerank flags)
- [ ] Add configurable TTL values.
- [ ] Add cache kill-switch env flags.
- [ ] Ensure cache failures fall back to normal query flow.
- [ ] Add cache observability metrics (hit, miss, set error, latency).

## Phase 3 - External Model Endpoint Readiness
- [ ] Keep current provider abstraction and add production profile defaults.
- [ ] Validate endpoint reachability and model configuration at startup.
- [ ] Add explicit failure messages for invalid model/endpoint config.
- [ ] Document profile switch strategy (dev local vs prod external).

## Phase 4 - Load Testing and SLO Gates
- [ ] Add load test script (k6 or Locust) with baseline and stress scenarios.
- [ ] Define target workload profile (concurrency, ramp, duration, question mix).
- [ ] Capture SLO thresholds in config/docs.
- [ ] Add automated pass/fail checks for p95 latency, error rate, minimum throughput.
- [ ] Add regression gate in CI to detect performance drift.

## Phase 5 - Rollout and Operational Safety
- [ ] Deploy with cache disabled first.
- [ ] Enable cache gradually using feature flags.
- [ ] Track rollout metrics: p50/p95/p99 latency, error rate, cache hit rate, provider latency.
- [ ] Define rollback triggers and rollback commands.
- [ ] Document incident response playbook for timeout spikes and cache outages.

## Test Checklist
- [ ] Unit tests for timeout/retry policy behavior.
- [ ] Unit tests for cache key stability and namespace versioning.
- [ ] Unit tests for cache hit/miss/stale behavior.
- [ ] Integration tests for Redis unavailable -> graceful fallback.
- [ ] Integration tests for provider timeout/error propagation.
- [ ] Load test execution as part of pre-release validation.

## Failure Mode Coverage Checklist
- [ ] Redis outage covered by tests and graceful fallback.
- [ ] External provider timeout covered by tests and clear user error path.
- [ ] Cache-key drift risk mitigated via versioned keys.
- [ ] Hybrid retrieval candidate explosion constrained and tested.

## Not In Scope (Explicit)
- [ ] Multi-region architecture.
- [ ] Qdrant cluster/sharding migration.
- [ ] Event-driven async orchestration rewrite.

## Parallelization Plan (Worktrees)
- [ ] Lane A: Runtime hardening -> Cache implementation (sequential, shared backend modules).
- [ ] Lane B: Load-test scaffolding (parallel after runtime knobs exist).
- [ ] Lane C: CI gate wiring (after load-test artifacts exist).
- [ ] Merge order defined and conflict hotspots reviewed before execution.

## Documentation Deliverables
- [ ] Create `docs/runbooks/high-volume-readiness.md`.
- [ ] Add rollout checklist and rollback steps.
- [ ] Add SLO and alert policy section.
- [ ] Add operating model for local/dev vs production provider profiles.