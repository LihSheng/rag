from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ragstack.config import Settings
from ragstack.langchain_pipeline.pipeline import LangChainRagPipeline
from ragstack.manual.pipeline import ManualRagPipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dockerized RAG learning CLI")
    subparsers = parser.add_subparsers(dest="command_group", required=True)

    manual = subparsers.add_parser("manual", help="Manual RAG pipeline")
    manual_subparsers = manual.add_subparsers(dest="manual_command", required=True)
    manual_ingest = manual_subparsers.add_parser("ingest", help="Index the source corpus with the manual pipeline")
    manual_ingest.add_argument("--source-dir", type=Path, default=None)
    manual_backfill = manual_subparsers.add_parser("backfill-metadata", help="Backfill metadata in manual collection")
    manual_backfill.add_argument("--collection-name", type=str, default=None)
    manual_backfill.add_argument("--apply", action="store_true")
    manual_ask = manual_subparsers.add_parser("ask", help="Ask the manual pipeline a question")
    manual_ask.add_argument("question")

    langchain = subparsers.add_parser("langchain", help="LangChain RAG pipeline")
    langchain_subparsers = langchain.add_subparsers(dest="langchain_command", required=True)
    langchain_ingest = langchain_subparsers.add_parser("ingest", help="Index the source corpus with LangChain")
    langchain_ingest.add_argument("--source-dir", type=Path, default=None)
    langchain_backfill = langchain_subparsers.add_parser("backfill-metadata", help="Backfill metadata in LangChain collection")
    langchain_backfill.add_argument("--collection-name", type=str, default=None)
    langchain_backfill.add_argument("--apply", action="store_true")
    langchain_ask = langchain_subparsers.add_parser("ask", help="Ask the LangChain pipeline a question")
    langchain_ask.add_argument("question")

    compare = subparsers.add_parser("compare", help="Compare both pipelines")
    compare_subparsers = compare.add_subparsers(dest="compare_command", required=True)
    compare_eval = compare_subparsers.add_parser("eval", help="Run the evaluation set across both pipelines")
    compare_eval.add_argument("--eval-path", type=Path, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = Settings.from_env()

    if args.command_group == "manual":
        pipeline = ManualRagPipeline(settings)
        if args.manual_command == "ingest":
            result = pipeline.ingest(args.source_dir)
            _print_ingestion_result(result.to_dict())
            return 0
        if args.manual_command == "backfill-metadata":
            result = pipeline.backfill_metadata(dry_run=not args.apply, collection_name=args.collection_name)
            _print_backfill_result(result.to_dict())
            return 0

        answer = pipeline.ask(args.question)
        _print_answer(answer.to_dict())
        return 0

    if args.command_group == "langchain":
        pipeline = LangChainRagPipeline(settings)
        if args.langchain_command == "ingest":
            result = pipeline.ingest(args.source_dir)
            _print_ingestion_result(result.to_dict())
            return 0
        if args.langchain_command == "backfill-metadata":
            result = pipeline.backfill_metadata(dry_run=not args.apply, collection_name=args.collection_name)
            _print_backfill_result(result.to_dict())
            return 0

        answer = pipeline.ask(args.question)
        _print_answer(answer.to_dict())
        return 0

    if args.command_group == "compare" and args.compare_command == "eval":
        eval_path = args.eval_path or settings.eval_path
        manual = ManualRagPipeline(settings)
        langchain = LangChainRagPipeline(settings)
        _print_eval_results(_load_eval_set(eval_path), manual, langchain)
        return 0

    parser.error("Unsupported command")
    return 2


def _load_eval_set(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Evaluation file must contain a JSON array")

    normalized: list[dict[str, Any]] = []
    for item in payload:
        if isinstance(item, str):
            normalized.append({"question": item, "expected_source": None})
            continue

        if not isinstance(item, dict) or "question" not in item:
            raise ValueError("Each evaluation item must be a string or an object with a 'question' field")
        normalized.append(item)

    return normalized


def _print_ingestion_result(result: dict[str, Any]) -> None:
    print(f"Pipeline: {result['pipeline']}")
    print(f"Discovered files: {result['discovered_files']}")
    print(f"Indexed files: {result['indexed_files']}")
    print(f"Skipped files: {result['skipped_files']}")
    print(f"Indexed chunks: {result['indexed_chunks']}")
    print(f"Deleted documents: {result['deleted_documents']}")


def _print_answer(answer: dict[str, Any]) -> None:
    print(f"Pipeline: {answer['pipeline']}")
    print(f"Question: {answer['question']}")
    print(f"Insufficient context: {answer['insufficient_context']}")
    print("Answer:")
    print(answer["answer"])
    print("Citations:")
    for citation in answer["citations"]:
        location = citation["source_path"]
        if citation.get("page") is not None:
            location = f"{location} page {citation['page']}"
        if citation.get("section"):
            location = f"{location} section {citation['section']}"
        print(f"- {citation['chunk_id']} | score={citation['score']:.4f} | {location}")


def _print_backfill_result(result: dict[str, Any]) -> None:
    print(f"Pipeline: {result['pipeline']}")
    print(f"Collection: {result['collection_name']}")
    print(f"Dry run: {result['dry_run']}")
    print(f"Total points: {result['total_points']}")
    print(f"Points missing metadata: {result['missing_points']}")
    print(f"Points updated: {result['updated_points']}")
    print("Missing field counts:")
    for key, value in result["missing_field_counts"].items():
        print(f"- {key}: {value}")


def _print_eval_results(
    eval_rows: list[dict[str, Any]],
    manual: ManualRagPipeline,
    langchain: LangChainRagPipeline,
) -> None:
    for index, row in enumerate(eval_rows, start=1):
        question = str(row["question"])
        expected_source = row.get("expected_source")

        manual_result = manual.ask(question)
        langchain_result = langchain.ask(question)

        print(f"=== Evaluation {index} ===")
        print(f"Question: {question}")
        if expected_source:
            print(f"Expected source: {expected_source}")
        print()
        _print_pipeline_eval("manual", manual_result.to_dict())
        print()
        _print_pipeline_eval("langchain", langchain_result.to_dict())
        print()


def _print_pipeline_eval(label: str, result: dict[str, Any]) -> None:
    print(label.upper())
    print(f"Insufficient context: {result['insufficient_context']}")
    print("Answer:")
    print(result["answer"])
    print("Retrieved chunks:")
    for citation in result["citations"]:
        location = citation["source_path"]
        if citation.get("page") is not None:
            location = f"{location} page {citation['page']}"
        if citation.get("section"):
            location = f"{location} section {citation['section']}"
        print(f"- {citation['chunk_id']} | score={citation['score']:.4f} | {location}")
