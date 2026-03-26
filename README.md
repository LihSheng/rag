# Dockerized RAG Learning Stack

This repository is a learning-oriented Retrieval-Augmented Generation stack built in Python and packaged to run through Docker Compose.

It contains two implementations over the same corpus and vector database:

- `manual`: a plain Python pipeline so you can see each RAG step directly
- `langchain`: the same workflow rebuilt with LangChain components

The goal is to let you understand the internals first, then compare that against a framework-based version without changing the surrounding architecture.

## Architecture Overview

The system is split into three Docker services:

- `app`: the Python CLI container that runs ingestion, querying, and evaluation commands
- `ollama`: the local LLM and embedding runtime
- `qdrant`: the vector database that stores chunk embeddings and metadata

Named Docker volumes are used for persistence:

- `ollama_models`: keeps downloaded local model files so they do not need to be re-pulled every run
- `qdrant_storage`: keeps indexed vectors and payload data

This means the stack is portable as a Compose project instead of depending on one large prebuilt image.

## RAG Data Flow

Both pipelines follow the same high-level flow:

1. Read local source files from `data/corpus`
2. Normalize text
3. Split documents into chunks
4. Generate embeddings for each chunk
5. Store chunk vectors and metadata in Qdrant
6. Embed the user question
7. Retrieve the top matching chunks from Qdrant
8. Build a grounded prompt from those chunks
9. Generate an answer with citations

The main difference is where the orchestration lives:

- `manual` does the flow with your own code and thin libraries
- `langchain` uses LangChain wrappers for embeddings, chat models, text splitting, and vector store integration

## Repository Layout

```text
.
├── docker-compose.yml
├── Dockerfile
├── data
│   ├── corpus
│   └── eval
├── docker
│   └── entrypoint.sh
├── src
│   └── ragstack
│       ├── bootstrap.py
│       ├── cli.py
│       ├── config.py
│       ├── models.py
│       ├── prompting.py
│       ├── providers.py
│       ├── qdrant_store.py
│       ├── text_utils.py
│       ├── manual
│       └── langchain_pipeline
└── tests
```

## Shared Contracts

Both pipelines use the same Qdrant payload structure:

- `document_id`
- `chunk_id`
- `source_path`
- `source_type`
- `page`
- `section`
- `text`
- `checksum`
- `pipeline`

Separate collections are used for comparison:

- `rag_manual`
- `rag_langchain`

The collection prefix is configurable with `QDRANT_COLLECTION_PREFIX`.

## Provider Abstraction

The app separates chat generation and embeddings into two independent provider layers:

- `ChatProvider`
- `EmbeddingProvider`

This lets you:

- run locally with Ollama now
- switch later to a hosted OpenAI-compatible endpoint through environment variables

No CLI changes are required when switching providers.

## Configuration

Copy `.env.example` to `.env` if you want a local env file for Docker Compose.

Important variables:

```env
CHAT_PROVIDER=ollama
CHAT_BASE_URL=http://ollama:11434/v1
CHAT_API_KEY=ollama
CHAT_MODEL=qwen2.5:3b

EMBED_PROVIDER=ollama
EMBED_BASE_URL=http://ollama:11434/v1
EMBED_API_KEY=ollama
EMBED_MODEL=nomic-embed-text

QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION_PREFIX=rag

SOURCE_DIR=/workspace/data/corpus
EVAL_PATH=/workspace/data/eval/questions.json
```

If you later want to use an external OpenAI-compatible provider, change values like:

```env
CHAT_PROVIDER=openai_compatible
CHAT_BASE_URL=https://your-provider.example.com/v1
CHAT_API_KEY=your-key
CHAT_MODEL=your-chat-model

EMBED_PROVIDER=openai_compatible
EMBED_BASE_URL=https://your-provider.example.com/v1
EMBED_API_KEY=your-key
EMBED_MODEL=your-embedding-model
```

## How To Run

### 1. Start the stack

```bash
docker compose up --build -d
```

What happens:

- the `app` image is built
- `ollama` starts
- `qdrant` starts
- the app bootstrap waits for services
- the app can pull the configured chat and embedding models on first startup

### 2. Ingest documents with the manual pipeline

```bash
docker compose exec app ragstack manual ingest
```

Optional custom source directory:

```bash
docker compose exec app ragstack manual ingest --source-dir /workspace/data/corpus
```

### 3. Ask a question with the manual pipeline

```bash
docker compose exec app ragstack manual ask "How does this stack stay portable?"
```

### 4. Ingest documents with the LangChain pipeline

```bash
docker compose exec app ragstack langchain ingest
```

### 5. Ask a question with the LangChain pipeline

```bash
docker compose exec app ragstack langchain ask "What is the manual pipeline trying to teach?"
```

### 6. Compare both pipelines on the evaluation set

```bash
docker compose exec app ragstack compare eval
```

Optional custom evaluation file:

```bash
docker compose exec app ragstack compare eval --eval-path /workspace/data/eval/questions.json
```

## CLI Reference

```bash
ragstack manual ingest [--source-dir PATH]
ragstack manual ask "question"
ragstack langchain ingest [--source-dir PATH]
ragstack langchain ask "question"
ragstack compare eval [--eval-path PATH]
```

## How Ingestion Works

During ingestion the system:

- scans `SOURCE_DIR` recursively
- loads supported files:
  - Markdown
  - PDF
- computes a checksum per document
- skips unchanged documents
- deletes old chunks for changed documents
- creates new chunks
- embeds those chunks
- upserts them into the pipeline-specific Qdrant collection

This makes re-ingestion idempotent for unchanged files.

## How Querying Works

When you ask a question:

1. the question is embedded
2. the top `k` similar chunks are fetched from Qdrant
3. those chunks are formatted into a grounded prompt
4. the chat model answers only from retrieved context
5. the output includes citations and can return an insufficient-context response

Default behavior:

- chunk size: about 1000 characters
- chunk overlap: about 150 characters
- top results: 5

## Corpus And Evaluation Files

Sample files are included:

- corpus: [data/corpus](/Users/Lih Sheng/RAG/data/corpus)
- evaluation set: [data/eval/questions.json](/Users/Lih Sheng/RAG/data/eval/questions.json)

You can replace or expand the corpus with your own Markdown and PDF files.

## Running Outside Docker

If you want to run locally without Compose:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Then point the provider URLs to local endpoints such as:

- `http://localhost:11434/v1`
- `http://localhost:6333`

Example:

```bash
ragstack manual ingest
ragstack manual ask "What does Qdrant store?"
```

## Current Status

The implementation exists, but full end-to-end validation is still pending.

What is already in place:

- Docker stack
- manual pipeline
- LangChain pipeline
- provider abstraction
- comparison command
- sample corpus and eval inputs

What still needs to be confirmed:

- live Docker validation with Ollama and Qdrant
- automated test execution
- model bootstrap and volume reuse behavior

## Next Learning Steps

After you are comfortable with this version, useful follow-ups are:

- add reranking
- add hybrid keyword + vector retrieval
- compare chunking strategies
- add a simple HTTP API
- add source highlighting in answers
- swap the local LLM for a hosted provider using only env changes
