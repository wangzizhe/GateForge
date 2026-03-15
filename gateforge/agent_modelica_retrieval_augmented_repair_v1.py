from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


LIST_HINT_KEYS = {
    "libraries": ("library_hints", "libraries", "library_ids", "package_names"),
    "components": ("component_hints", "components", "component_types"),
    "connectors": ("connector_hints", "connectors", "connector_types"),
    "domains": ("domains", "domain_hints"),
}
SCALAR_HINT_KEYS = {
    "libraries": ("library_name", "library_id", "source_library", "package_name"),
    "components": ("component_name", "component_type"),
    "connectors": ("connector_name", "connector_type"),
    "domains": ("domain",),
}
TEXT_HINT_KEYS = (
    "model_hint",
    "model_id",
    "task_id",
    "source_model_path",
    "mutated_model_path",
    "error_excerpt",
    "patch_diff_summary",
    "error_message",
    "compile_error",
    "simulate_error_message",
    "stderr_snippet",
    "reason",
)
ENDPOINT_HINT_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\b")
PACKAGE_REF_RE = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:\.[A-Z][A-Za-z0-9_]*){1,})\b")
FILE_SUFFIX_BLACKLIST = {"mo", "mat", "json", "jsonl", "md", "txt", "log", "csv", "yaml", "yml"}


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _norm_text(value: object) -> str:
    return str(value or "").strip().lower()


def _token_overlap(a: str, b: str) -> int:
    sa = {x for x in a.replace("/", " ").replace("_", " ").split() if x}
    sb = {x for x in b.replace("/", " ").replace("_", " ").split() if x}
    return len(sa & sb)


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _append_unique(out: list[str], seen: set[str], value: object) -> None:
    text = _norm_text(value)
    if text and text not in seen:
        out.append(text)
        seen.add(text)


def _append_many(out: list[str], seen: set[str], values: object) -> None:
    if isinstance(values, (list, tuple, set)):
        for value in values:
            _append_unique(out, seen, value)
        return
    _append_unique(out, seen, values)


def _infer_model_reference_hints(value: object) -> tuple[list[str], list[str]]:
    text = str(value or "").strip()
    if not text:
        return [], []
    trimmed = text[:-3] if text.lower().endswith(".mo") else text
    libraries: list[str] = []
    components: list[str] = []
    if "/" not in trimmed and "\\" not in trimmed and "." in trimmed and " " not in trimmed:
        parts = [part.strip() for part in trimmed.split(".") if part.strip()]
        if len(parts) >= 2:
            libraries.append(parts[0])
            components.append(parts[-1])
            return libraries, components
    stem = Path(trimmed).stem
    if stem and stem.lower() not in {"model", "package"}:
        components.append(stem)
    return libraries, components


def _extract_text_hints(value: object) -> tuple[list[str], list[str], list[str]]:
    text = str(value or "").strip()
    if not text:
        return [], [], []
    libraries: list[str] = []
    components: list[str] = []
    connectors: list[str] = []
    for match in ENDPOINT_HINT_RE.findall(text):
        if "." in match:
            _, port = match.split(".", 1)
            if _norm_text(port) in FILE_SUFFIX_BLACKLIST:
                continue
            connectors.append(_norm_text(match))
            connectors.append(_norm_text(port))
    for match in PACKAGE_REF_RE.findall(text):
        inferred_libraries, inferred_components = _infer_model_reference_hints(match)
        libraries.extend(inferred_libraries)
        components.extend(inferred_components)
    return libraries, components, connectors


def build_retrieval_context_hints(payload: dict | None, diagnostic_payload: dict | None = None) -> dict:
    source = payload if isinstance(payload, dict) else {}
    diagnostic = diagnostic_payload if isinstance(diagnostic_payload, dict) else {}
    libraries: list[str] = []
    components: list[str] = []
    connectors: list[str] = []
    domains: list[str] = []
    text: list[str] = []
    seen = {"libraries": set(), "components": set(), "connectors": set(), "domains": set(), "text": set()}
    buckets = {
        "libraries": libraries,
        "components": components,
        "connectors": connectors,
        "domains": domains,
    }

    for bucket, keys in LIST_HINT_KEYS.items():
        for key in keys:
            _append_many(buckets[bucket], seen[bucket], source.get(key))
    for bucket, keys in SCALAR_HINT_KEYS.items():
        for key in keys:
            _append_many(buckets[bucket], seen[bucket], source.get(key))
    for key in TEXT_HINT_KEYS:
        _append_many(text, seen["text"], source.get(key))
    _append_many(text, seen["text"], source.get("action_trace"))
    _append_many(text, seen["text"], source.get("actions"))
    _append_many(text, seen["text"], source.get("context_text"))
    _append_many(text, seen["text"], source.get("text"))

    for key in ("model_hint", "model_id", "task_id", "source_model_path", "mutated_model_path", "package_name"):
        inferred_libraries, inferred_components = _infer_model_reference_hints(source.get(key))
        _append_many(libraries, seen["libraries"], inferred_libraries)
        _append_many(components, seen["components"], inferred_components)
    for value in text:
        inferred_libraries, inferred_components, inferred_connectors = _extract_text_hints(value)
        _append_many(libraries, seen["libraries"], inferred_libraries)
        _append_many(components, seen["components"], inferred_components)
        _append_many(connectors, seen["connectors"], inferred_connectors)

    mutated_objects = source.get("mutated_objects") if isinstance(source.get("mutated_objects"), list) else []
    for row in mutated_objects:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("kind") or "").strip().lower()
        name = str(row.get("name") or row.get("component") or row.get("component_id") or "").strip()
        if "component" in kind or name:
            _append_unique(components, seen["components"], name)
        if "connector" in kind or "connect" in kind:
            for key in ("name", "paired_with", "from", "to", "removed_from", "removed_to", "from_before", "from_after", "to_before", "to_after"):
                _append_unique(connectors, seen["connectors"], row.get(key))
        for key in ("kind", "effect", "name", "paired_with", "from", "to", "removed_from", "removed_to", "from_before", "from_after", "to_before", "to_after"):
            _append_unique(text, seen["text"], row.get(key))

    _append_many(connectors, seen["connectors"], diagnostic.get("connector_hints"))
    for key in ("reason", "error_subtype", "error_type", "stage"):
        _append_unique(text, seen["text"], diagnostic.get(key))

    return {
        "libraries": libraries,
        "components": components,
        "connectors": connectors,
        "domains": domains,
        "text": text,
    }


def _success_state(row: dict) -> str:
    for key in ("passed", "pass", "success", "is_success", "success_flag"):
        if key in row:
            value = row.get(key)
            if isinstance(value, bool):
                return "success" if value else "fail"
            if isinstance(value, (int, float)):
                return "success" if float(value) > 0 else "fail"
            text = str(value or "").strip().lower()
            if text in {"pass", "passed", "success", "ok", "true", "1"}:
                return "success"
            if text in {"fail", "failed", "error", "timeout", "false", "0"}:
                return "fail"
    for key in ("decision", "result", "outcome", "gate", "status"):
        if key not in row:
            continue
        text = str(row.get(key) or "").strip().lower()
        if text in {"pass", "passed", "success", "ok"}:
            return "success"
        if text in {"fail", "failed", "error", "timeout"}:
            return "fail"
    return "unknown"


def retrieve_repair_examples(
    history_payload: dict,
    failure_type: str,
    model_hint: str = "",
    top_k: int = 2,
    policy_payload: dict | None = None,
    context_hints: dict | None = None,
) -> dict:
    rows = history_payload.get("rows") if isinstance(history_payload.get("rows"), list) else []
    if not rows:
        rows = history_payload.get("records") if isinstance(history_payload.get("records"), list) else []
    rows = [x for x in rows if isinstance(x, dict)]

    ftype = _norm_text(failure_type)
    hint = _norm_text(model_hint)
    policy = policy_payload if isinstance(policy_payload, dict) else {}
    top_k_map = policy.get("top_k_by_failure_type") if isinstance(policy.get("top_k_by_failure_type"), dict) else {}
    strategy_bonus_map_root = (
        policy.get("strategy_id_bonus_by_failure_type")
        if isinstance(policy.get("strategy_id_bonus_by_failure_type"), dict)
        else {}
    )
    strategy_bonus_map = (
        strategy_bonus_map_root.get(ftype)
        if isinstance(strategy_bonus_map_root.get(ftype), dict)
        else {}
    )
    failure_match_bonus = _safe_float(policy.get("failure_match_bonus"), 2.0)
    model_overlap_weight = _safe_float(policy.get("model_overlap_weight"), 1.0)
    library_overlap_weight = _safe_float(policy.get("library_overlap_weight"), 1.3)
    component_overlap_weight = _safe_float(policy.get("component_overlap_weight"), 1.1)
    connector_overlap_weight = _safe_float(policy.get("connector_overlap_weight"), 1.2)
    exact_library_match_weight = _safe_float(policy.get("exact_library_match_weight"), 1.6)
    domain_overlap_weight = _safe_float(policy.get("domain_overlap_weight"), 0.8)
    text_context_weight = _safe_float(policy.get("text_context_weight"), 0.35)
    effective_top_k = max(0, int(top_k_map.get(ftype, top_k)))
    context_payload = dict(context_hints) if isinstance(context_hints, dict) else {}
    if model_hint and not str(context_payload.get("model_hint") or "").strip():
        context_payload["model_hint"] = model_hint
    query_profile = build_retrieval_context_hints(context_payload)
    query_libraries = set(query_profile.get("libraries") or [])
    query_components = set(query_profile.get("components") or [])
    query_connectors = set(query_profile.get("connectors") or [])
    query_domains = set(query_profile.get("domains") or [])
    query_text = " ".join(str(x) for x in (query_profile.get("text") or []) if isinstance(x, str))

    prepared_rows: list[dict] = []
    for row in rows:
        row_ftype = _norm_text(row.get("failure_type"))
        row_model = _norm_text(
            row.get("model_id") or row.get("source_model_path") or row.get("target_model_id") or row.get("task_id")
        )
        strategy_id = str(
            row.get("used_strategy")
            or row.get("strategy_id")
            or (row.get("repair_strategy") or {}).get("strategy_id")
            or (row.get("repair_audit") or {}).get("strategy_id")
            or ""
        )
        actions = row.get("action_trace") if isinstance(row.get("action_trace"), list) else row.get("actions")
        if not isinstance(actions, list):
            nested_strategy = row.get("repair_strategy") if isinstance(row.get("repair_strategy"), dict) else {}
            nested_audit = row.get("repair_audit") if isinstance(row.get("repair_audit"), dict) else {}
            if isinstance(nested_strategy.get("actions"), list):
                actions = nested_strategy.get("actions")
            elif isinstance(nested_audit.get("actions_planned"), list):
                actions = nested_audit.get("actions_planned")
            else:
                actions = []
        actions = [str(x) for x in (actions or []) if isinstance(x, str)]
        row_profile = build_retrieval_context_hints(row)
        row_profile_text = [row_model, row.get("error_excerpt"), row.get("patch_diff_summary"), *actions, *(row_profile.get("text") or [])]
        prepared_rows.append(
            {
                "failure_type": row_ftype,
                "model": row_model,
                "strategy_id": strategy_id,
                "actions": actions,
                "success_state": _success_state(row),
                "libraries": [str(x) for x in (row_profile.get("libraries") or []) if isinstance(x, str)],
                "components": [str(x) for x in (row_profile.get("components") or []) if isinstance(x, str)],
                "connectors": [str(x) for x in (row_profile.get("connectors") or []) if isinstance(x, str)],
                "domains": [str(x) for x in (row_profile.get("domains") or []) if isinstance(x, str)],
                "context_text": " ".join(str(x) for x in row_profile_text if isinstance(x, str) and str(x).strip()),
            }
        )

    # If we have same failure type history, only retrieve from that slice.
    candidates = prepared_rows
    if ftype and any(x.get("failure_type") == ftype for x in prepared_rows):
        candidates = [x for x in prepared_rows if x.get("failure_type") == ftype]

    # If success labels exist in candidate set, prefer successful repairs only.
    has_success_signal = any(x.get("success_state") in {"success", "fail"} for x in candidates)
    if has_success_signal:
        candidates = [x for x in candidates if x.get("success_state") == "success"]

    ranked: list[dict] = []
    for row in candidates:
        row_ftype = str(row.get("failure_type") or "")
        row_model = str(row.get("model") or "")
        strategy_id = str(row.get("strategy_id") or "")
        actions = [str(x) for x in (row.get("actions") or []) if isinstance(x, str)]
        row_libraries = {str(x) for x in (row.get("libraries") or []) if isinstance(x, str)}
        row_components = {str(x) for x in (row.get("components") or []) if isinstance(x, str)}
        row_connectors = {str(x) for x in (row.get("connectors") or []) if isinstance(x, str)}
        row_domains = {str(x) for x in (row.get("domains") or []) if isinstance(x, str)}
        matched_libraries = sorted(query_libraries & row_libraries)
        matched_components = sorted(query_components & row_components)
        matched_connectors = sorted(query_connectors & row_connectors)
        matched_domains = sorted(query_domains & row_domains)
        exact_library_matches = sorted({item for item in matched_libraries if item in query_libraries and item in row_libraries})
        score = 0
        if row_ftype and row_ftype == ftype:
            score += failure_match_bonus
        score += min(2, _token_overlap(hint, row_model)) * model_overlap_weight
        score += min(2, len(exact_library_matches)) * exact_library_match_weight
        score += min(2, len(matched_libraries)) * library_overlap_weight
        score += min(3, len(matched_components)) * component_overlap_weight
        score += min(3, len(matched_connectors)) * connector_overlap_weight
        score += min(2, len(matched_domains)) * domain_overlap_weight
        if query_text:
            score += min(2, _token_overlap(query_text, str(row.get("context_text") or ""))) * text_context_weight
        if strategy_id:
            score += 1
            score += _safe_float(strategy_bonus_map.get(strategy_id), 0.0)
        if score <= 0:
            continue
        ranked.append(
            {
                "score": score,
                "failure_type": row_ftype,
                "model": row_model,
                "strategy_id": strategy_id,
                "actions": actions,
                "success_state": str(row.get("success_state") or "unknown"),
                "matched_library_hints": matched_libraries,
                "matched_component_hints": matched_components,
                "matched_connector_hints": matched_connectors,
                "matched_domain_hints": matched_domains,
                "exact_library_match_count": len(exact_library_matches),
                "library_match_count": len(matched_libraries),
                "component_match_count": len(matched_components),
                "connector_match_count": len(matched_connectors),
                "domain_match_count": len(matched_domains),
            }
        )

    ranked = sorted(
        ranked,
        key=lambda x: (-_safe_float(x.get("score"), 0.0), x.get("strategy_id", ""), x.get("model", "")),
    )
    selected = ranked[: effective_top_k]
    suggested_actions: list[str] = []
    seen: set[str] = set()
    for row in selected:
        for action in row.get("actions", []):
            item = str(action).strip()
            if item and item not in seen:
                suggested_actions.append(item)
                seen.add(item)

    matched_library_hints: set[str] = set()
    matched_component_hints: set[str] = set()
    matched_connector_hints: set[str] = set()
    matched_domain_hints: set[str] = set()
    exact_library_match_total = 0
    library_match_total = 0
    component_match_total = 0
    connector_match_total = 0
    domain_match_total = 0
    for row in selected:
        matched_library_hints.update(str(x) for x in (row.get("matched_library_hints") or []) if isinstance(x, str))
        matched_component_hints.update(str(x) for x in (row.get("matched_component_hints") or []) if isinstance(x, str))
        matched_connector_hints.update(str(x) for x in (row.get("matched_connector_hints") or []) if isinstance(x, str))
        matched_domain_hints.update(str(x) for x in (row.get("matched_domain_hints") or []) if isinstance(x, str))
        exact_library_match_total += int(row.get("exact_library_match_count", 0) or 0)
        library_match_total += int(row.get("library_match_count", 0) or 0)
        component_match_total += int(row.get("component_match_count", 0) or 0)
        connector_match_total += int(row.get("connector_match_count", 0) or 0)
        domain_match_total += int(row.get("domain_match_count", 0) or 0)

    return {
        "retrieved_count": len(selected),
        "effective_top_k": effective_top_k,
        "examples": selected,
        "suggested_actions": suggested_actions,
        "audit": {
            "matched_library_hints": sorted(matched_library_hints),
            "matched_component_hints": sorted(matched_component_hints),
            "matched_connector_hints": sorted(matched_connector_hints),
            "matched_domain_hints": sorted(matched_domain_hints),
            "exact_library_match_count": exact_library_match_total,
            "library_match_count": library_match_total,
            "component_match_count": component_match_total,
            "connector_match_count": connector_match_total,
            "domain_match_count": domain_match_total,
            "fallback_used": len(selected) > 0 and library_match_total <= 0,
        },
    }


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Retrieval Augmented Repair v1",
        "",
        f"- retrieved_count: `{payload.get('retrieved_count')}`",
        "",
        "## Suggested Actions",
        "",
    ]
    actions = payload.get("suggested_actions") if isinstance(payload.get("suggested_actions"), list) else []
    if actions:
        lines.extend([f"- {x}" for x in actions])
    else:
        lines.append("- none")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve similar successful repair traces for current task")
    parser.add_argument("--history", required=True)
    parser.add_argument("--failure-type", required=True)
    parser.add_argument("--model-hint", default="")
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--policy", default="")
    parser.add_argument("--context", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_retrieval_augmented_repair_v1/retrieval.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    history = _load_json(args.history)
    policy = _load_json(args.policy) if str(args.policy).strip() else {}
    context = _load_json(args.context) if str(args.context).strip() else {}
    payload = retrieve_repair_examples(
        history_payload=history,
        failure_type=args.failure_type,
        model_hint=args.model_hint,
        top_k=max(0, int(args.top_k)),
        policy_payload=policy,
        context_hints=context,
    )
    payload["schema_version"] = "agent_modelica_retrieval_augmented_repair_v1"
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["sources"] = {
        "history": args.history,
        "policy": args.policy if str(args.policy).strip() else None,
        "context": args.context if str(args.context).strip() else None,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"retrieved_count": payload.get("retrieved_count")}))


if __name__ == "__main__":
    main()
