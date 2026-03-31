from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_planner_bottleneck_analysis_v0_3_4"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_planner_bottleneck_analysis_v0_3_4"
LEVER_ORDER = (
    "l2_replan",
    "l4_guided_search",
    "repair_rule_ordering",
    "experience_replay_retrieval",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _rows(payload: dict) -> list[dict]:
    rows = payload.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("item_id") or row.get("task_id") or row.get("mutation_id"))


def _bool(value: object) -> bool:
    return bool(value)


def recommend_bottleneck_levers(row: dict) -> dict:
    bucket = _norm(row.get("failure_bucket"))
    planner_invoked = _bool(row.get("planner_invoked"))
    planner_decisive = _bool(row.get("planner_decisive"))
    replay_used = _bool(row.get("replay_used"))
    rounds_used = int(row.get("rounds_used") or row.get("agent_rounds") or 0)
    check_model_pass = row.get("check_model_pass")
    simulate_pass = row.get("simulate_pass")
    attribution_missing = _bool(row.get("attribution_missing"))
    library_context = any(
        (
            _norm(row.get("source_library")),
            _norm(row.get("source_model_path")),
            isinstance(row.get("component_hints"), list) and bool(row.get("component_hints")),
            isinstance(row.get("library_hints"), list) and bool(row.get("library_hints")),
        )
    )

    primary = ""
    reasons: list[str] = []
    secondary: list[str] = []

    if bucket == "unresolved_search" and planner_invoked and rounds_used <= 1:
        primary = "l2_replan"
        reasons.extend(["planner_invoked_true", "rounds_used_le_1", "unresolved_search"])
    elif bucket == "unresolved_search" and planner_invoked and rounds_used >= 2:
        primary = "l4_guided_search"
        reasons.extend(["planner_invoked_true", "rounds_used_ge_2", "unresolved_search"])
    elif bucket in {"patch_invalid", "verifier_reject"}:
        primary = "repair_rule_ordering"
        reasons.append(f"failure_bucket:{bucket}")
        if check_model_pass is False:
            reasons.append("check_model_pass_false")
        if simulate_pass is False:
            reasons.append("simulate_pass_false")
    elif planner_invoked and not planner_decisive:
        primary = "l2_replan" if rounds_used <= 1 else "l4_guided_search"
        reasons.extend(["planner_invoked_true", "planner_decisive_false"])
    else:
        primary = "l4_guided_search"
        reasons.append("fallback_guided_search_default")

    if library_context and not replay_used and bucket in {"unresolved_search", "patch_invalid", "verifier_reject"}:
        secondary.append("experience_replay_retrieval")
        reasons.append("replay_candidate_context_present")

    if attribution_missing:
        reasons.append("attribution_missing")

    return {
        "primary_lever": primary,
        "secondary_levers": secondary,
        "lever_reasons": reasons,
    }


def build_planner_bottleneck_analysis(
    *,
    failure_classifier_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = _load_json(failure_classifier_summary_path)
    rows = _rows(payload)
    focus_rows: list[dict] = []
    lever_counts = {lever: 0 for lever in LEVER_ORDER}

    for row in rows:
        bucket = _norm(row.get("failure_bucket"))
        planner_invoked = _bool(row.get("planner_invoked"))
        if bucket == "success":
            continue
        if not planner_invoked and bucket not in {"patch_invalid", "verifier_reject"}:
            continue
        recommendation = recommend_bottleneck_levers(row)
        primary = _norm(recommendation.get("primary_lever"))
        if primary:
            lever_counts[primary] = int(lever_counts.get(primary) or 0) + 1
        focus_rows.append(
            {
                **row,
                "item_id": _item_id(row),
                "primary_bottleneck_lever": primary,
                "secondary_bottleneck_levers": list(recommendation.get("secondary_levers") or []),
                "bottleneck_reasons": list(recommendation.get("lever_reasons") or []),
            }
        )

    ordered_focus_rows = sorted(
        focus_rows,
        key=lambda row: (
            LEVER_ORDER.index(_norm(row.get("primary_bottleneck_lever"))) if _norm(row.get("primary_bottleneck_lever")) in LEVER_ORDER else len(LEVER_ORDER),
            _item_id(row),
        ),
    )
    ranked_levers = [
        {"lever": lever, "case_count": int(lever_counts.get(lever) or 0)}
        for lever in sorted(LEVER_ORDER, key=lambda item: (-int(lever_counts.get(item) or 0), LEVER_ORDER.index(item)))
        if int(lever_counts.get(lever) or 0) > 0
    ]
    payload_out = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if rows else "FAIL",
        "failure_classifier_summary_path": str(Path(failure_classifier_summary_path).resolve()) if Path(failure_classifier_summary_path).exists() else str(failure_classifier_summary_path),
        "metrics": {
            "focus_case_count": len(ordered_focus_rows),
            "lever_case_counts": lever_counts,
            "top_primary_lever": ranked_levers[0]["lever"] if ranked_levers else "",
        },
        "ranked_levers": ranked_levers,
        "focus_rows": ordered_focus_rows,
        "notes": [
            "Bottleneck-first analysis for planner-sensitive failures; use this to choose the first engineering lever before broad capability changes.",
            "experience_replay_retrieval is treated as a secondary lever unless replay/context evidence is the clearest gap.",
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload_out)
    _write_text(out_root / "summary.md", render_markdown(payload_out))
    return payload_out


def render_markdown(payload: dict) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    lines = [
        "# Agent Modelica Planner Bottleneck Analysis v0.3.4",
        "",
        f"- status: `{payload.get('status')}`",
        f"- focus_case_count: `{metrics.get('focus_case_count')}`",
        f"- top_primary_lever: `{metrics.get('top_primary_lever')}`",
        f"- lever_case_counts: `{json.dumps(metrics.get('lever_case_counts') or {}, sort_keys=True)}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Recommend the first engineering lever for planner-sensitive failures in v0.3.4.")
    parser.add_argument("--failure-classifier-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_planner_bottleneck_analysis(
        failure_classifier_summary_path=str(args.failure_classifier_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "top_primary_lever": payload.get("metrics", {}).get("top_primary_lever")}))


if __name__ == "__main__":
    main()
