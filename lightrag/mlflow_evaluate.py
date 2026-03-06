"""MLflow Evaluate helper for comparing LightRAG retrieval modes.

Runs the same queries across multiple retrieval modes (local, global, hybrid,
mix, naive) and logs results to MLflow for side-by-side comparison.

Requires: mlflow (raises ImportError if not installed).

Usage:
    from lightrag.mlflow_evaluate import compare_modes

    results = await compare_modes(
        rag=rag_instance,
        queries=["What is X?", "How does Y work?"],
        modes=["local", "global", "hybrid"],
    )
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any

try:
    import mlflow
except ImportError:
    raise ImportError(
        "mlflow is required for lightrag.mlflow_evaluate. "
        "Install it with: pip install mlflow"
    )

from lightrag.base import QueryParam

if TYPE_CHECKING:
    from lightrag import LightRAG

logger = logging.getLogger("lightrag")

ALL_MODES = ["local", "global", "hybrid", "mix", "naive"]


def _extract_metrics(result: dict[str, Any]) -> dict[str, Any]:
    """Extract numeric metrics from an aquery_llm result dict."""
    metadata = result.get("metadata", {})
    processing = metadata.get("processing_info", {})
    return {
        "entities_found": processing.get("total_entities_found", 0),
        "relations_found": processing.get("total_relations_found", 0),
        "chunks_found": processing.get("final_chunks_count", 0),
    }


async def compare_modes(
    rag: "LightRAG",
    queries: list[str],
    modes: list[str] | None = None,
    param_overrides: dict[str, Any] | None = None,
    experiment_name: str | None = None,
) -> list[dict[str, Any]]:
    """Run queries across retrieval modes and log results to MLflow.

    Each mode-query combination is logged as a child run under a parent run,
    enabling side-by-side comparison in the MLflow UI.

    Args:
        rag: Initialized LightRAG instance.
        queries: List of query strings to evaluate.
        modes: Retrieval modes to compare. Defaults to all 5 modes.
        param_overrides: Optional overrides for QueryParam fields (top_k, etc.).
        experiment_name: MLflow experiment name. Defaults to MLFLOW_EXPERIMENT_NAME
            env var or "lightrag-evaluate".

    Returns:
        List of result dicts, one per query-mode combination, with keys:
            query, mode, answer, latency_ms, entities_found,
            relations_found, chunks_found, metadata
    """
    if modes is None:
        modes = list(ALL_MODES)

    exp_name = experiment_name or os.environ.get(
        "MLFLOW_EXPERIMENT_NAME", "lightrag-evaluate"
    )
    mlflow.set_experiment(exp_name)

    overrides = param_overrides or {}
    all_results: list[dict[str, Any]] = []

    with mlflow.start_run(run_name="compare_modes"):
        mlflow.log_param("num_queries", len(queries))
        mlflow.log_param("modes", ",".join(modes))

        for query in queries:
            for mode in modes:
                param = QueryParam(mode=mode, **overrides)

                with mlflow.start_run(
                    run_name=f"{mode}",
                    nested=True,
                ):
                    mlflow.log_param("mode", mode)
                    mlflow.log_param("query", query[:250])
                    for k, v in overrides.items():
                        mlflow.log_param(k, v)

                    start = time.perf_counter()
                    try:
                        result = await rag.aquery_llm(query, param=param)
                        latency_ms = (time.perf_counter() - start) * 1000

                        metrics = _extract_metrics(result)
                        metrics["latency_ms"] = latency_ms

                        mlflow.log_metrics(metrics)

                        # Extract answer text
                        llm_resp = result.get("llm_response", {})
                        answer = llm_resp.get("content", "") or ""

                        entry = {
                            "query": query,
                            "mode": mode,
                            "answer": answer,
                            "latency_ms": latency_ms,
                            "entities_found": metrics["entities_found"],
                            "relations_found": metrics["relations_found"],
                            "chunks_found": metrics["chunks_found"],
                            "metadata": result.get("metadata", {}),
                        }
                    except Exception as e:
                        latency_ms = (time.perf_counter() - start) * 1000
                        logger.error(
                            f"compare_modes: query failed for mode={mode}: {e}"
                        )
                        mlflow.log_metrics(
                            {"latency_ms": latency_ms, "error": 1}
                        )
                        entry = {
                            "query": query,
                            "mode": mode,
                            "answer": "",
                            "latency_ms": latency_ms,
                            "entities_found": 0,
                            "relations_found": 0,
                            "chunks_found": 0,
                            "metadata": {},
                            "error": str(e),
                        }
                    all_results.append(entry)

    return all_results
