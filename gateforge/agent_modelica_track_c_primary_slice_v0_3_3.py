from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_track_c_primary_slice_v0_3_3"
DEFAULT_CANDIDATE_TASKSET = "artifacts/agent_modelica_planner_sensitive_expansion_v0_3_2/taskset_candidates.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_primary_slice_v0_3_3"
DEFAULT_MIN_PRIMARY_SLICE_CASES = 20
DEFAULT_MIN_PLANNER_SENSITIVE_PCT = 70.0
DEFAULT_MAX_DETERMINISTIC_ONLY_PCT = 30.0
DEFAULT_FROZEN_REFERENCES = (
    {
        "ref_id": "track_a_valid32",
        "path": "assets_private/agent_modelica_track_a_valid32_fixture_v1/hardpack_frozen.json",
    },
    {
        "ref_id": "track_b_aixlib",
        "path": "benchmarks/agent_modelica_hardpack_aix_v1.json",
    },
    {
        "ref_id": "v0_3_0_hard_lane",
        "path": "artifacts/agent_modelica_layer4_hard_lane_v0_3_0/taskset_frozen.json",
    },
    {
        "ref_id": "v0_3_1_harder_holdout",
        "path": "artifacts/agent_modelica_layer4_holdout_v0_3_1/taskset_frozen.json",
    },
    {
        "ref_id": "v0_3_2_seed_slice",
        "path": "artifacts/agent_modelica_planner_sensitive_taskset_builder_v1/taskset_frozen.json",
    },
)
ALLOWED_FAMILY_IDS = {
    "hard_multiround_simulate_failure",
    "runtime_numerical_instability",
    "initialization_singularity",
}
PLANNER_RESOLUTION_PATHS = {"llm_planner_assisted", "rule_then_llm"}


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


def _task_rows(payload: dict) -> list[dict]:
    for key in ("tasks", "cases"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _item_id(row: dict) -> str:
    return _norm(row.get("task_id") or row.get("mutation_id") or row.get("item_id"))


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _frozen_case_ids(path: str | Path) -> set[str]:
    payload = _load_json(path)
    out: set[str] = set()
    for row in _task_rows(payload):
        item_id = _item_id(row)
        if item_id:
            out.add(item_id)
    return out


def _selection_reasons(row: dict) -> list[str]:
    return [str(x).strip() for x in (row.get("selection_reasons") or []) if str(x).strip()]


def _resolution_path(row: dict) -> str:
    direct = _norm(row.get("resolution_path"))
    if direct:
        return direct
    for reason in _selection_reasons(row):
        if reason.startswith("observed_resolution_path:"):
            return _norm(reason.split(":", 1)[1])
    return ""


def _family_gate(row: dict) -> tuple[bool, list[str]]:
    family_id = _norm(row.get("v0_3_family_id"))
    expected_layer_hint = _norm(row.get("expected_layer_hint"))
    reasons: list[str] = []
    if family_id not in ALLOWED_FAMILY_IDS:
        reasons.append("family_not_in_v0_3_3_allowed_set")
        return False, reasons
    if family_id == "initialization_singularity" and expected_layer_hint != "layer_4":
        reasons.append("initialization_singularity_not_layer4_observed")
        return False, reasons
    reasons.append(f"family_ok:{family_id}")
    return True, reasons


def _planner_sensitivity_gate(row: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    resolution_path = _resolution_path(row)
    if resolution_path in PLANNER_RESOLUTION_PATHS:
        reasons.append(f"resolution_path:{resolution_path}")
        return True, reasons
    if bool(row.get("planner_invoked")):
        reasons.append("planner_invoked_true")
        return True, reasons
    rounds_used = int(row.get("rounds_used") or row.get("candidate_metrics", {}).get("rounds_used") or 0) if isinstance(row.get("candidate_metrics"), dict) else int(row.get("rounds_used") or 0)
    llm_request_count = int(row.get("llm_request_count") or row.get("candidate_metrics", {}).get("llm_request_count") or 0) if isinstance(row.get("candidate_metrics"), dict) else int(row.get("llm_request_count") or 0)
    if rounds_used > 1 and llm_request_count > 0:
        reasons.append("multi_round_with_llm_requests")
        return True, reasons
    if "planner_invoked_observed" in _selection_reasons(row):
        reasons.append("planner_invoked_observed")
        return True, reasons
    reasons.append("planner_sensitivity_not_evidenced")
    return False, reasons


def _attribution_gate(row: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    classification = _norm(row.get("classification"))
    resolution_path = _resolution_path(row)
    if classification == "freeze_ready_observed":
        if resolution_path or "planner_invoked_observed" in _selection_reasons(row):
            reasons.append("observed_attribution_present")
            return True, reasons
        reasons.append("observed_seed_missing_resolution_attribution")
        return False, reasons
    if resolution_path:
        reasons.append("direct_resolution_path_present")
        return True, reasons
    reasons.append("attribution_missing_for_candidate")
    return False, reasons


def _deterministic_only(row: dict) -> bool:
    return _resolution_path(row) == "deterministic_rule_only"


def build_primary_slice(
    *,
    candidate_taskset_path: str = DEFAULT_CANDIDATE_TASKSET,
    frozen_references: list[dict] | None = None,
    min_primary_slice_cases: int = DEFAULT_MIN_PRIMARY_SLICE_CASES,
    min_planner_sensitive_pct: float = DEFAULT_MIN_PLANNER_SENSITIVE_PCT,
    max_deterministic_only_pct: float = DEFAULT_MAX_DETERMINISTIC_ONLY_PCT,
) -> dict:
    payload = _load_json(candidate_taskset_path)
    candidate_rows = _task_rows(payload)
    frozen_refs = [dict(row) for row in (frozen_references or list(DEFAULT_FROZEN_REFERENCES))]
    frozen_ids_by_ref: dict[str, set[str]] = {}
    for row in frozen_refs:
        frozen_ids_by_ref[_norm(row.get("ref_id")) or "unknown_ref"] = _frozen_case_ids(_norm(row.get("path")))

    admitted: list[dict] = []
    excluded: list[dict] = []
    for row in candidate_rows:
        item_id = _item_id(row)
        if not item_id:
            continue
        frozen_hits = sorted([ref_id for ref_id, ids in frozen_ids_by_ref.items() if item_id in ids])
        family_ok, family_reasons = _family_gate(row)
        attribution_ok, attribution_reasons = _attribution_gate(row)
        planner_ok, planner_reasons = _planner_sensitivity_gate(row)
        holdout_ok = not frozen_hits

        eval_row = {
            **row,
            "item_id": item_id,
            "gates": {
                "holdout_clean": holdout_ok,
                "family_spec": family_ok,
                "attribution": attribution_ok,
                "planner_sensitivity": planner_ok,
            },
            "gate_reasons": {
                "holdout_clean": [] if holdout_ok else [f"frozen_hit:{x}" for x in frozen_hits],
                "family_spec": family_reasons,
                "attribution": attribution_reasons,
                "planner_sensitivity": planner_reasons,
            },
            "frozen_hits": frozen_hits,
            "admission_status": "admitted" if holdout_ok and family_ok and attribution_ok and planner_ok else "excluded",
        }
        if eval_row["admission_status"] == "admitted":
            admitted.append(eval_row)
        else:
            excluded.append(eval_row)

    planner_sensitive_count = len(admitted)
    deterministic_only_count = len([row for row in admitted if _deterministic_only(row)])
    planner_sensitive_pct = _ratio(planner_sensitive_count, len(admitted)) if admitted else 0.0
    deterministic_only_pct = _ratio(deterministic_only_count, len(admitted)) if admitted else 0.0
    paper_ready = (
        len(admitted) >= int(min_primary_slice_cases)
        and planner_sensitive_pct >= float(min_planner_sensitive_pct)
        and deterministic_only_pct <= float(max_deterministic_only_pct)
    )
    status = "PRIMARY_READY" if paper_ready else "NEEDS_MORE_GENERATION"
    holdout_blocked_count = len([row for row in excluded if not bool(row.get("gates", {}).get("holdout_clean"))])
    family_blocked_count = len([row for row in excluded if not bool(row.get("gates", {}).get("family_spec"))])
    attribution_blocked_count = len([row for row in excluded if not bool(row.get("gates", {}).get("attribution"))])
    planner_blocked_count = len([row for row in excluded if not bool(row.get("gates", {}).get("planner_sensitivity"))])

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": status,
        "candidate_taskset_path": str(Path(candidate_taskset_path).resolve()) if Path(candidate_taskset_path).exists() else str(candidate_taskset_path),
        "targets": {
            "min_primary_slice_cases": int(min_primary_slice_cases),
            "min_planner_sensitive_pct": float(min_planner_sensitive_pct),
            "max_deterministic_only_pct": float(max_deterministic_only_pct),
        },
        "metrics": {
            "candidate_count": len(candidate_rows),
            "admitted_count": len(admitted),
            "excluded_count": len(excluded),
            "planner_sensitive_count": planner_sensitive_count,
            "planner_sensitive_pct": planner_sensitive_pct,
            "deterministic_only_count": deterministic_only_count,
            "deterministic_only_pct": deterministic_only_pct,
            "freeze_ready_gap": max(0, int(min_primary_slice_cases) - len(admitted)),
            "holdout_blocked_count": holdout_blocked_count,
            "family_blocked_count": family_blocked_count,
            "attribution_blocked_count": attribution_blocked_count,
            "planner_blocked_count": planner_blocked_count,
        },
        "frozen_references": [
            {
                "ref_id": _norm(row.get("ref_id")),
                "path": _norm(row.get("path")),
                "case_count": len(frozen_ids_by_ref.get(_norm(row.get("ref_id")), set())),
            }
            for row in frozen_refs
        ],
        "admitted_rows": admitted,
        "excluded_rows": excluded,
        "next_actions": [
            "Generate new harder Layer 4 mutation candidates rather than reusing previously frozen packs.",
            "Rerun attribution-bearing evidence on newly generated candidates before attempting primary-slice freeze.",
            "Do not treat previously frozen seed cases as holdout-clean members of the v0.3.3 primary slice.",
        ],
    }


def _render_markdown(payload: dict) -> str:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    lines = [
        "# Track C Primary Slice v0.3.3",
        "",
        f"- status: `{payload.get('status')}`",
        f"- candidate_count: `{metrics.get('candidate_count')}`",
        f"- admitted_count: `{metrics.get('admitted_count')}`",
        f"- freeze_ready_gap: `{metrics.get('freeze_ready_gap')}`",
        f"- planner_sensitive_pct: `{metrics.get('planner_sensitive_pct')}`",
        f"- deterministic_only_pct: `{metrics.get('deterministic_only_pct')}`",
        f"- holdout_blocked_count: `{metrics.get('holdout_blocked_count')}`",
        "",
        "## Frozen References",
        "",
    ]
    for row in payload.get("frozen_references") or []:
        if not isinstance(row, dict):
            continue
        lines.append(f"- `{row.get('ref_id')}`: `{row.get('case_count')}` cases")
    admitted_rows = payload.get("admitted_rows") if isinstance(payload.get("admitted_rows"), list) else []
    if admitted_rows:
        lines.extend(["", "## Admitted Rows", ""])
        for row in admitted_rows:
            lines.append(f"- `{row.get('item_id')}`")
    excluded_rows = payload.get("excluded_rows") if isinstance(payload.get("excluded_rows"), list) else []
    if excluded_rows:
        lines.extend(["", "## Exclusion Highlights", ""])
        for row in excluded_rows[:10]:
            frozen_hits = row.get("frozen_hits") if isinstance(row.get("frozen_hits"), list) else []
            gate_reasons = row.get("gate_reasons") if isinstance(row.get("gate_reasons"), dict) else {}
            reasons: list[str] = []
            for gate_name in ("holdout_clean", "family_spec", "attribution", "planner_sensitivity"):
                values = gate_reasons.get(gate_name) if isinstance(gate_reasons.get(gate_name), list) else []
                reasons.extend([str(x) for x in values if str(x).strip()])
            hit_text = f" frozen_hits={','.join(frozen_hits)}" if frozen_hits else ""
            lines.append(f"- `{row.get('item_id')}`:{hit_text} reasons=`{'; '.join(reasons[:4])}`")
    lines.extend(["", "## Next Actions", ""])
    for idx, item in enumerate(payload.get("next_actions") or [], start=1):
        lines.append(f"{idx}. {item}")
    lines.append("")
    return "\n".join(lines)


def run_primary_slice(
    *,
    candidate_taskset_path: str = DEFAULT_CANDIDATE_TASKSET,
    out_dir: str = DEFAULT_OUT_DIR,
    frozen_references: list[dict] | None = None,
    min_primary_slice_cases: int = DEFAULT_MIN_PRIMARY_SLICE_CASES,
    min_planner_sensitive_pct: float = DEFAULT_MIN_PLANNER_SENSITIVE_PCT,
    max_deterministic_only_pct: float = DEFAULT_MAX_DETERMINISTIC_ONLY_PCT,
) -> dict:
    payload = build_primary_slice(
        candidate_taskset_path=candidate_taskset_path,
        frozen_references=frozen_references,
        min_primary_slice_cases=min_primary_slice_cases,
        min_planner_sensitive_pct=min_planner_sensitive_pct,
        max_deterministic_only_pct=max_deterministic_only_pct,
    )
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    admitted_rows = payload.get("admitted_rows") if isinstance(payload.get("admitted_rows"), list) else []
    _write_json(
        out_root / "taskset_frozen_candidate.json",
        {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": _now_utc(),
            "tasks": admitted_rows,
        },
    )
    _write_text(out_root / "summary.md", _render_markdown(payload))
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.3 Track C primary-slice candidate with holdout-clean gates.")
    parser.add_argument("--candidate-taskset", default=DEFAULT_CANDIDATE_TASKSET)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-primary-slice-cases", type=int, default=DEFAULT_MIN_PRIMARY_SLICE_CASES)
    parser.add_argument("--min-planner-sensitive-pct", type=float, default=DEFAULT_MIN_PLANNER_SENSITIVE_PCT)
    parser.add_argument("--max-deterministic-only-pct", type=float, default=DEFAULT_MAX_DETERMINISTIC_ONLY_PCT)
    args = parser.parse_args()
    payload = run_primary_slice(
        candidate_taskset_path=str(args.candidate_taskset),
        out_dir=str(args.out_dir),
        min_primary_slice_cases=int(args.min_primary_slice_cases),
        min_planner_sensitive_pct=float(args.min_planner_sensitive_pct),
        max_deterministic_only_pct=float(args.max_deterministic_only_pct),
    )
    print(json.dumps({"status": payload.get("status"), "admitted_count": payload.get("metrics", {}).get("admitted_count")}))


if __name__ == "__main__":
    main()
