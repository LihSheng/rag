# Dockerized RAG Basics

## Why Docker Helps

Packaging the app, vector store, and model runtime in Docker Compose makes the
learning environment portable. The same service graph can be moved to another
machine without changing the application code.

## Manual Pipeline

The manual pipeline makes every step visible. It loads files, normalizes text,
creates chunks, generates embeddings, stores vectors, retrieves matches, and
assembles the final prompt without hiding those transitions behind a framework.

## LangChain Pipeline

The LangChain pipeline keeps the same corpus and payload contract, but delegates
chunk splitting, vector store adapters, and model wrappers to LangChain
components. This helps you compare the framework abstraction against the manual
implementation.

