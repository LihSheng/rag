from __future__ import annotations

import time

import httpx
import os

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

from ragstack.config import Settings


def _wait_for_endpoint(url: str, label: str, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error = ""

    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code < 500:
                return
            last_error = f"{label} returned status {response.status_code}"
        except Exception as exc:  # pragma: no cover - exercised in Docker
            last_error = str(exc)

        time.sleep(2)

    raise RuntimeError(f"Timed out waiting for {label}: {last_error}")


def _pull_model(ollama_url: str, model: str) -> None:
    response = httpx.post(
        f"{ollama_url.rstrip('/')}/api/pull",
        json={"model": model, "stream": False},
        timeout=None,
    )
    response.raise_for_status()


def ensure_telemetry() -> None:
    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
    if not endpoint:
        return
        
    try:
        from opentelemetry import trace
        # Only configure once
        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            resource = Resource(attributes={"service.name": "ragstack"})
            provider = TracerProvider(resource=resource)
            exporter = OTLPSpanExporter(endpoint=endpoint)
            # Use SimpleSpanProcessor for immediate visibility or BatchSpanProcessor for production
            provider.add_span_processor(BatchSpanProcessor(exporter))
            trace.set_tracer_provider(provider)
    except Exception as e:
        print(f"Failed to initialize OpenTelemetry: {e}")


def main() -> int:
    settings = Settings.from_env()

    if settings.bootstrap_qdrant_url and settings.bootstrap_qdrant_url.startswith("http"):
        _wait_for_endpoint(
            settings.bootstrap_qdrant_url,
            "qdrant",
            settings.bootstrap_wait_timeout,
        )

    use_ollama = settings.chat_provider == "ollama" or settings.embed_provider == "ollama"
    if use_ollama and settings.bootstrap_ollama_url:
        _wait_for_endpoint(
            f"{settings.bootstrap_ollama_url.rstrip('/')}/api/tags",
            "ollama",
            settings.bootstrap_wait_timeout,
        )

        if settings.bootstrap_pull_models:
            for model in {settings.chat_model, settings.embed_model}:
                _pull_model(settings.bootstrap_ollama_url, model)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
