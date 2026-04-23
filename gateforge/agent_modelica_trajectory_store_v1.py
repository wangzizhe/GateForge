"""Trajectory indexing and retrieval utilities for GateForge.

This module builds a local, deterministic retrieval index from historical
trajectory JSON files. It intentionally does not call an embedding service and
does not generate repair hints. The searchable key is abstracted to avoid
leaking task-specific variable names into later retrieval prompts.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "gateforge_trajectory_store_v1"
DEFAULT_VECTOR_DIM = 512

_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?")
_VARISH_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_SUMMARY_NAMES = {
    "summary.json",
    "experiment_summary.json",
    "aggregate_summary.json",
}


@dataclass(frozen=True)
class RetrievalHit:
    entry_id: str
    score: float
    candidate_id: str
    mode: str
    final_status: str
    mutation_family: str
    failure_type: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "score": round(self.score, 6),
            "candidate_id": self.candidate_id,
            "mode": self.mode,
            "final_status": self.final_status,
            "mutation_family": self.mutation_family,
            "failure_type": self.failure_type,
            "summary": self.summary,
        }


def load_json_file(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def iter_trajectory_json_paths(paths: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for root in paths:
        if root.is_file() and root.suffix == ".json":
            if root.name not in _SUMMARY_NAMES and not root.name.startswith("summary_"):
                out.append(root)
            continue
        if not root.exists():
            continue
        for path in root.rglob("*.json"):
            if path.name in _SUMMARY_NAMES or path.name.startswith("summary_"):
                continue
            out.append(path)
    return sorted(set(out))


def infer_mutation_family(payload: dict[str, Any]) -> str:
    explicit = str(payload.get("mutation_family") or payload.get("family") or "").strip()
    if explicit:
        return _normalize_label(explicit)

    candidate_id = str(payload.get("candidate_id") or "")
    lower = candidate_id.lower()
    has_pp = "_pp_" in lower or lower.endswith("_pp") or "parameter_promotion" in lower
    has_pv = "_pv_" in lower or "_phantom" in lower or "phantom_variable" in lower
    if has_pp and has_pv:
        return "compound_underdetermined"
    if has_pp:
        return "parameter_promotion"
    if has_pv:
        return "phantom_variable"
    if "overdet" in lower or "overdetermined" in lower:
        return "overdetermined"
    if "underdet" in lower or "underdetermined" in lower:
        return "underdetermined"
    if "semantic" in lower:
        return "semantic"
    return "unknown"


def infer_failure_type(payload: dict[str, Any], round_payload: dict[str, Any] | None = None) -> str:
    for source in (round_payload or {}, payload):
        for key in ("observed_failure_type", "failure_type", "expected_failure_type"):
            value = str(source.get(key) or "").strip()
            if value:
                return _normalize_label(value)

    text = _collect_omc_text(round_payload or payload).lower()
    if "under-determined" in text or "underdetermined" in text or "too few equations" in text or "not determined" in text:
        return "underdetermined_structural"
    if "overdetermined" in text or "too many equations" in text:
        return "overdetermined_structural"
    if "class" in text and "not found" in text:
        return "missing_symbol"
    if "simulate" in text or "simulation" in text:
        return "simulate_error"
    return "unknown"


def abstract_root_cause_signature(payload: dict[str, Any], round_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    text = _collect_omc_text(round_payload or payload)
    candidate_id = str(payload.get("candidate_id") or "")
    lower_id = candidate_id.lower()

    return {
        "mutation_family": infer_mutation_family(payload),
        "failure_type": infer_failure_type(payload, round_payload),
        "has_parameter_promotion_marker": "_pp_" in lower_id or "parameter_promotion" in lower_id,
        "has_phantom_marker": "_pv_" in lower_id or "_phantom" in lower_id or "phantom" in text.lower(),
        "phantom_token_count": len(re.findall(r"\b[A-Za-z][A-Za-z0-9_]*_phantom\b", text)),
        "underdetermined_signal_count": len(re.findall(r"underdetermined|too few equations|not determined", text, re.I)),
        "overdetermined_signal_count": len(re.findall(r"overdetermined|too many equations", text, re.I)),
        "missing_symbol_signal_count": len(re.findall(r"class .*? not found|variable .*? not found", text, re.I)),
        "deficit_bucket": _deficit_bucket(round_payload or payload),
        "round_count_bucket": _round_count_bucket(payload),
    }


def extract_trajectory_entries_from_result(
    payload: dict[str, Any],
    *,
    source_path: str = "",
    vector_dim: int = DEFAULT_VECTOR_DIM,
) -> list[dict[str, Any]]:
    condition_entries = _extract_condition_entries(payload, source_path=source_path, vector_dim=vector_dim)
    if condition_entries:
        return condition_entries

    rounds = payload.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        rounds = payload.get("attempts")
    if not isinstance(rounds, list) or not rounds:
        return []

    candidate_id = str(payload.get("candidate_id") or Path(source_path).stem)
    mode = str(payload.get("mode") or payload.get("arm") or "")
    final_status = _normalize_status(str(payload.get("final_status") or payload.get("status") or "unknown"))
    trajectory_success = final_status in {"pass", "passed", "success"}
    mutation_family = infer_mutation_family(payload)

    entries: list[dict[str, Any]] = []
    for idx, round_payload in enumerate(rounds, start=1):
        if not isinstance(round_payload, dict):
            continue
        round_no = int(round_payload.get("round") or idx)
        failure_type = infer_failure_type(payload, round_payload)
        signature = abstract_root_cause_signature(payload, round_payload)
        search_text = build_search_text(
            mutation_family=mutation_family,
            failure_type=failure_type,
            mode=mode,
            final_status=final_status,
            round_payload=round_payload,
            signature=signature,
        )
        vector = vectorize_text(search_text, dim=vector_dim)
        entry_id = stable_entry_id(source_path, candidate_id, mode, round_no)
        entries.append(
            {
                "entry_id": entry_id,
                "candidate_id": candidate_id,
                "source_path": source_path,
                "mode": mode,
                "round": round_no,
                "final_status": final_status,
                "trajectory_success": trajectory_success,
                "round_advance": _normalize_label(str(round_payload.get("advance") or "")),
                "mutation_family": mutation_family,
                "failure_type": failure_type,
                "abstract_signature": signature,
                "search_text": search_text,
                "summary": summarize_round(round_payload, mutation_family, failure_type, final_status),
                "vector": vector,
            }
        )
    return entries


def build_trajectory_store(paths: Iterable[Path], *, vector_dim: int = DEFAULT_VECTOR_DIM) -> dict[str, Any]:
    json_paths = iter_trajectory_json_paths(paths)
    entries: list[dict[str, Any]] = []
    skipped = 0
    for path in json_paths:
        payload = load_json_file(path)
        if not isinstance(payload, dict):
            skipped += 1
            continue
        extracted = extract_trajectory_entries_from_result(
            payload,
            source_path=str(path),
            vector_dim=vector_dim,
        )
        if not extracted:
            skipped += 1
            continue
        entries.extend(extracted)

    success_count = sum(1 for row in entries if row.get("trajectory_success") is True)
    failure_count = sum(1 for row in entries if row.get("trajectory_success") is False)
    return {
        "schema_version": SCHEMA_VERSION,
        "vector_dim": vector_dim,
        "entry_count": len(entries),
        "success_count": success_count,
        "failure_count": failure_count,
        "source_file_count": len(json_paths),
        "skipped_file_count": skipped,
        "created_from": [str(p) for p in json_paths],
        "entries": entries,
    }


def save_trajectory_store(store: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, sort_keys=True), encoding="utf-8")


def load_trajectory_store(path: Path) -> dict[str, Any]:
    payload = load_json_file(path)
    if not isinstance(payload, dict):
        raise ValueError(f"not a trajectory store: {path}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported trajectory store schema: {payload.get('schema_version')}")
    return payload


def retrieve_similar_trajectories(
    store: dict[str, Any],
    query: dict[str, Any] | str,
    *,
    top_k: int = 3,
    prefer_success: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    dim = int(store.get("vector_dim") or DEFAULT_VECTOR_DIM)
    query_text = query if isinstance(query, str) else query_to_search_text(query)
    query_family = ""
    query_failure = ""
    if isinstance(query, dict):
        query_signature = query.get("abstract_signature") if isinstance(query.get("abstract_signature"), dict) else {}
        query_family = _normalize_label(str(query.get("mutation_family") or query_signature.get("mutation_family") or ""))
        query_failure = _normalize_label(str(query.get("failure_type") or query_signature.get("failure_type") or ""))
    query_vector = vectorize_text(query_text, dim=dim)

    hits: list[RetrievalHit] = []
    for entry in store.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        score = cosine_similarity(query_vector, entry.get("vector") if isinstance(entry.get("vector"), dict) else {})
        if query_family and query_family == str(entry.get("mutation_family") or ""):
            score += 0.08
        if query_failure and query_failure == str(entry.get("failure_type") or ""):
            score += 0.10
        if prefer_success and entry.get("trajectory_success") is True:
            score += 0.03
        if score <= 0.0:
            continue
        hits.append(
            RetrievalHit(
                entry_id=str(entry.get("entry_id") or ""),
                score=score,
                candidate_id=str(entry.get("candidate_id") or ""),
                mode=str(entry.get("mode") or ""),
                final_status=str(entry.get("final_status") or ""),
                mutation_family=str(entry.get("mutation_family") or ""),
                failure_type=str(entry.get("failure_type") or ""),
                summary=str(entry.get("summary") or ""),
            )
        )

    hits.sort(key=lambda item: item.score, reverse=True)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return {
        "query_text": query_text,
        "top_k": top_k,
        "latency_ms": round(elapsed_ms, 3),
        "hits": [hit.to_dict() for hit in hits[: max(0, int(top_k))]],
    }


def query_to_search_text(query: dict[str, Any]) -> str:
    signature = query.get("abstract_signature") if isinstance(query.get("abstract_signature"), dict) else {}
    parts = [
        f"family:{_normalize_label(str(query.get('mutation_family') or signature.get('mutation_family') or 'unknown'))}",
        f"failure:{_normalize_label(str(query.get('failure_type') or signature.get('failure_type') or 'unknown'))}",
        f"mode:{_normalize_label(str(query.get('mode') or 'unknown'))}",
    ]
    for key in sorted(signature):
        value = signature.get(key)
        if isinstance(value, bool):
            parts.append(f"{_normalize_label(key)}:{'yes' if value else 'no'}")
        elif isinstance(value, (int, float, str)):
            parts.append(f"{_normalize_label(key)}:{_abstract_token(str(value))}")
    return " ".join(parts)


def build_search_text(
    *,
    mutation_family: str,
    failure_type: str,
    mode: str,
    final_status: str,
    round_payload: dict[str, Any],
    signature: dict[str, Any],
) -> str:
    parts = [
        f"family:{_normalize_label(mutation_family)}",
        f"failure:{_normalize_label(failure_type)}",
        f"mode:{_normalize_label(mode)}",
        f"status:{_normalize_label(final_status)}",
        f"advance:{_normalize_label(str(round_payload.get('advance') or 'unknown'))}",
        f"ranked_count:{_count_bucket(_count_ranked(round_payload))}",
        f"check_pass_count:{_count_bucket(_count_ranked_pass(round_payload, 'check_pass'))}",
        f"simulate_pass_count:{_count_bucket(_count_ranked_pass(round_payload, 'simulate_pass'))}",
    ]
    for key in sorted(signature):
        value = signature[key]
        if isinstance(value, bool):
            parts.append(f"{_normalize_label(key)}:{'yes' if value else 'no'}")
        else:
            parts.append(f"{_normalize_label(key)}:{_abstract_token(str(value))}")
    return " ".join(parts)


def summarize_round(round_payload: dict[str, Any], mutation_family: str, failure_type: str, final_status: str) -> str:
    return (
        f"family={_normalize_label(mutation_family)} "
        f"failure={_normalize_label(failure_type)} "
        f"status={_normalize_label(final_status)} "
        f"advance={_normalize_label(str(round_payload.get('advance') or 'unknown'))} "
        f"ranked={_count_ranked(round_payload)} "
        f"check_pass={_count_ranked_pass(round_payload, 'check_pass')} "
        f"simulate_pass={_count_ranked_pass(round_payload, 'simulate_pass')}"
    )


def vectorize_text(text: str, *, dim: int = DEFAULT_VECTOR_DIM) -> dict[str, float]:
    counts: dict[int, float] = {}
    for token in _tokenize_abstract(text):
        bucket = int(hashlib.sha256(token.encode("utf-8")).hexdigest()[:8], 16) % dim
        counts[bucket] = counts.get(bucket, 0.0) + 1.0
    norm = math.sqrt(sum(value * value for value in counts.values()))
    if norm == 0.0:
        return {}
    return {str(key): value / norm for key, value in sorted(counts.items())}


def cosine_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    total = 0.0
    for key, value in left.items():
        total += float(value) * float(right.get(key, 0.0))
    return total


def stable_entry_id(source_path: str, candidate_id: str, mode: str, round_no: int) -> str:
    raw = f"{source_path}|{candidate_id}|{mode}|{round_no}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _tokenize_abstract(text: str) -> list[str]:
    tokens: list[str] = []
    for token in _TOKEN_RE.findall(text):
        tokens.append(_abstract_token(token))
    return [token for token in tokens if token]


def _abstract_token(token: str) -> str:
    lower = token.lower()
    if re.fullmatch(r"\d+(?:\.\d+)?", lower):
        return "num"
    if lower.endswith("_phantom") or lower == "phantom":
        return "var_phantom"
    if lower in {
        "family",
        "failure",
        "mode",
        "status",
        "advance",
        "pass",
        "fail",
        "unknown",
        "compound_underdetermined",
        "parameter_promotion",
        "phantom_variable",
        "underdetermined_structural",
        "overdetermined_structural",
        "missing_symbol",
        "simulate_error",
        "baseline",
        "tool",
        "causal",
        "blt",
        "multi",
        "check",
        "simulate",
        "ranked",
        "count",
        "bucket",
        "yes",
        "no",
        "low",
        "mid",
        "high",
    }:
        return lower
    if "_" in lower and _VARISH_RE.match(lower):
        return "var_compound"
    if re.search(r"[A-Z]", token[1:]) or (len(token) <= 4 and token.isupper()):
        return "var_symbol"
    return lower


def _normalize_label(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown"


def _normalize_status(value: str) -> str:
    label = _normalize_label(value)
    if label in {"pass", "passed", "success", "ok"}:
        return "pass"
    if label in {"fail", "failed", "failure", "unresolved"}:
        return "fail"
    return label


def _collect_omc_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for key in (
        "omc_output",
        "omc_output_before_patch",
        "omc_output_after_patch",
        "omc_output_snippet",
        "check_output",
        "simulate_output",
        "error",
        "stderr",
        "stdout",
        "message",
    ):
        value = payload.get(key)
        if isinstance(value, str):
            chunks.append(value)
    for key in ("ranked", "candidates", "simulate_attempts"):
        value = payload.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    chunks.append(_collect_omc_text(item))
    return "\n".join(chunk for chunk in chunks if chunk)


def _extract_condition_entries(
    payload: dict[str, Any],
    *,
    source_path: str,
    vector_dim: int,
) -> list[dict[str, Any]]:
    condition_keys = [key for key in ("condition_a", "condition_b", "condition_c") if isinstance(payload.get(key), dict)]
    if not condition_keys:
        return []

    candidate_id = str(payload.get("candidate_id") or Path(source_path).stem)
    mutation_family = infer_mutation_family(payload)
    entries: list[dict[str, Any]] = []
    for idx, key in enumerate(condition_keys, start=1):
        round_payload = dict(payload[key])
        condition = _normalize_label(str(round_payload.get("condition") or key))
        final_status = "pass" if round_payload.get("fix_pass") is True else "fail"
        round_payload["round"] = idx
        round_payload["advance"] = "condition_pass" if final_status == "pass" else "condition_fail"
        failure_type = infer_failure_type(payload, round_payload)
        signature = abstract_root_cause_signature(payload, round_payload)
        search_text = build_search_text(
            mutation_family=mutation_family,
            failure_type=failure_type,
            mode=condition,
            final_status=final_status,
            round_payload=round_payload,
            signature=signature,
        )
        entries.append(
            {
                "entry_id": stable_entry_id(source_path, candidate_id, condition, idx),
                "candidate_id": candidate_id,
                "source_path": source_path,
                "mode": condition,
                "round": idx,
                "final_status": final_status,
                "trajectory_success": final_status == "pass",
                "round_advance": round_payload["advance"],
                "mutation_family": mutation_family,
                "failure_type": failure_type,
                "abstract_signature": signature,
                "search_text": search_text,
                "summary": summarize_round(round_payload, mutation_family, failure_type, final_status),
                "vector": vectorize_text(search_text, dim=vector_dim),
            }
        )
    return entries


def _count_ranked(round_payload: dict[str, Any]) -> int:
    ranked = round_payload.get("ranked")
    return len(ranked) if isinstance(ranked, list) else 0


def _count_ranked_pass(round_payload: dict[str, Any], key: str) -> int:
    ranked = round_payload.get("ranked")
    if not isinstance(ranked, list):
        return 0
    return sum(1 for item in ranked if isinstance(item, dict) and item.get(key) is True)


def _count_bucket(value: int) -> str:
    if value <= 0:
        return "zero"
    if value == 1:
        return "one"
    if value <= 3:
        return "low"
    if value <= 5:
        return "mid"
    return "high"


def _deficit_bucket(payload: dict[str, Any]) -> str:
    values: list[int] = []
    for key in ("deficit", "equation_deficit", "variable_deficit"):
        value = payload.get(key)
        if isinstance(value, int):
            values.append(abs(value))
    ranked = payload.get("ranked")
    if isinstance(ranked, list):
        for item in ranked:
            if isinstance(item, dict) and isinstance(item.get("deficit"), int):
                values.append(abs(int(item["deficit"])))
    if not values:
        return "unknown"
    return _count_bucket(max(values))


def _round_count_bucket(payload: dict[str, Any]) -> str:
    value = payload.get("round_count")
    if not isinstance(value, int):
        rounds = payload.get("rounds")
        value = len(rounds) if isinstance(rounds, list) else 0
    return _count_bucket(value)


__all__ = [
    "SCHEMA_VERSION",
    "abstract_root_cause_signature",
    "build_trajectory_store",
    "cosine_similarity",
    "extract_trajectory_entries_from_result",
    "infer_failure_type",
    "infer_mutation_family",
    "iter_trajectory_json_paths",
    "load_trajectory_store",
    "query_to_search_text",
    "retrieve_similar_trajectories",
    "save_trajectory_store",
    "vectorize_text",
]
