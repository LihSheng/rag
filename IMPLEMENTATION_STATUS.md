# Dockerized RAG Learning Stack Status

## Plan

1. Build the project scaffold and Docker runtime.
2. Add shared config, schemas, providers, Qdrant helpers, and the CLI entrypoint.
3. Implement the manual RAG pipeline.
4. Implement the LangChain RAG pipeline.
5. Add comparison tooling and validation.

## Todo Status

- [x] Create the project scaffold.
- [x] Add `docker-compose.yml`, `Dockerfile`, and container entrypoint bootstrap logic.
- [x] Add shared dependency and packaging files.
- [x] Add sample corpus data and evaluation input data.
- [x] Implement shared config loading and environment-variable-based provider switching.
- [x] Define shared document, chunk, retrieval, answer, and ingestion data models.
- [x] Implement shared text normalization and chunking helpers.
- [x] Implement OpenAI-compatible chat and embedding provider abstractions.
- [x] Implement Qdrant collection, delete, scroll, upsert, and query helpers.
- [x] Implement Docker bootstrap logic for waiting on services and pulling Ollama models.
- [x] Implement Markdown and PDF document loading.
- [x] Implement the manual ingest pipeline.
- [x] Implement the manual ask/query pipeline.
- [x] Implement LangChain runtime wrappers for chat and embeddings.
- [x] Implement the LangChain ingest pipeline.
- [x] Implement the LangChain ask/query pipeline.
- [x] Implement the CLI commands:
  - [x] `manual ingest`
  - [x] `manual ask`
  - [x] `langchain ingest`
  - [x] `langchain ask`
  - [x] `compare eval`
- [x] Generate a mixed sample corpus with Markdown and PDF documents.
- [x] Run a compile check across `src`.
- [x] Verify that the generated sample PDF can be read by `pypdf`.
- [ ] Run the full automated test suite.
- [ ] Run end-to-end Docker validation with live Ollama and Qdrant containers.
- [ ] Confirm first-run model pull and second-run reuse behavior in Docker volumes.
- [ ] Document any fixes needed after live runtime validation.

## Current State

- Implementation is paused.
- The codebase already contains work beyond step 1 because the pause instruction arrived after additional implementation had been completed.
- The remaining work is validation and any fixes discovered during validation.
