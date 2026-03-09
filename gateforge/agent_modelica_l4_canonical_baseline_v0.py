from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "agent_modelica_l4_canonical_baseline_v0"
PRIMARY_REASON_PRIORITY = [
    "inconsistent_provenance",
    "infra",
    "missing_artifacts",
    "repeat_required",
    "candidate_unstable",
    "baseline_too_weak",
    "baseline_too_strong",
    "no_in_range_candidate",
]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str, payload: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict[str, Any]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    canonical = payload.get("canonical_budget") if isinstance(payload.get("canonical_budget"), dict) else {}
    lines = [
        "# Agent Modelica L4 Canonical Baseline v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- primary_reason: `{payload.get('primary_reason')}`",
        f"- canonical_budget_token: `{canonical.get('budget_token')}`",
        f"- canonical_success_at_k_pct: `{canonical.get('baseline_off_success_at_k_pct')}`",
        f"- stability_ok: `{payload.get('stability_ok')}`",
        f"- stability_in_range_run_count: `{payload.get('stability_in_range_run_count')}`",
        f"- stability_total_run_count: `{payload.get('stability_total_run_count')}`",
        f"- reasons: `{payload.get('reasons')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except Exception:
        return default


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(str(value).strip())
    except Exception:
        return default


def _suffix_rank(path: Path) -> tuple[int, int, str]:
    name = path.name
    match = re.search(r"_r(\d+)$", name)
    if match:
        return (1, int(match.group(1)), name)
    return (0, 0, name)


def _budget_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
    return (
        _to_int(row.get("max_rounds"), 0),
        _to_int(row.get("max_time_sec"), 0),
        str(row.get("budget_token") or ""),
    )


def _candidate_row(candidate_dir: str) -> dict[str, Any]:
    root = Path(candidate_dir)
    frozen_summary = _load_json(root / "frozen_summary.json")
    manifest = _load_json(root / "manifest.json")
    baseline_summary = _load_json(root / "baseline_off_run_summary.json")
    baseline_results_path = root / "baseline_off_run_results.json"
    baseline_results_present = baseline_results_path.exists()
    summary_provenance = frozen_summary.get("baseline_provenance") if isinstance(frozen_summary.get("baseline_provenance"), dict) else {}
    manifest_provenance = manifest.get("baseline_provenance") if isinstance(manifest.get("baseline_provenance"), dict) else {}
    provenance = summary_provenance if summary_provenance else manifest_provenance

    success_pct = frozen_summary.get("baseline_off_success_at_k_pct")
    if success_pct is None:
        success_pct = baseline_summary.get("success_at_k_pct")

    max_rounds = provenance.get("max_rounds")
    if max_rounds is None:
        max_rounds = baseline_summary.get("max_rounds")
    max_time_sec = provenance.get("max_time_sec")
    if max_time_sec is None:
        max_time_sec = baseline_summary.get("max_time_sec")

    complete_artifacts = bool(frozen_summary and manifest and baseline_summary and baseline_results_present)
    baseline_exit_code = _to_int(frozen_summary.get("baseline_off_run_exit_code"), 1 if not baseline_summary else 0)
    infra_failure_count = 1 if baseline_exit_code != 0 else 0

    budget_token = f"{_to_int(max_rounds, 0)}x{_to_int(max_time_sec, 0)}"
    return {
        "candidate_dir": str(root),
        "candidate_name": root.name,
        "budget_token": budget_token,
        "max_rounds": _to_int(max_rounds, 0),
        "max_time_sec": _to_int(max_time_sec, 0),
        "baseline_off_success_at_k_pct": _to_float(success_pct, 0.0),
        "baseline_in_target_range": frozen_summary.get("baseline_in_target_range") is True,
        "status": str(frozen_summary.get("status") or ""),
        "total_selected_tasks": _to_int(frozen_summary.get("total_selected_tasks"), 0),
        "success_count": _to_int(baseline_summary.get("success_count"), 0),
        "total_tasks": _to_int(baseline_summary.get("total_tasks"), 0),
        "planner_backend": str(provenance.get("planner_backend") or ""),
        "llm_model": str(provenance.get("llm_model") or ""),
        "taskset_in": str(provenance.get("taskset_in") or manifest.get("taskset_in") or ""),
        "git_commit": str(provenance.get("git_commit") or ""),
        "summary_has_provenance": bool(summary_provenance),
        "manifest_has_provenance": bool(manifest_provenance),
        "complete_artifacts": complete_artifacts,
        "baseline_off_run_exit_code": baseline_exit_code,
        "baseline_summary_refresh_exit_code": _to_int(frozen_summary.get("baseline_summary_refresh_exit_code"), 0),
        "infra_failure_count": infra_failure_count,
        "reasons": [str(x) for x in (frozen_summary.get("reasons") or []) if str(x)],
    }


def _stability_payload(
    rows: list[dict[str, Any]],
    *,
    min_pct: float,
    max_pct: float,
    min_in_range_runs: int,
    max_spread_pp: float,
) -> dict[str, Any]:
    usable = [row for row in rows if row.get("complete_artifacts") and _to_int(row.get("infra_failure_count"), 0) == 0]
    values = [_to_float(row.get("baseline_off_success_at_k_pct"), 0.0) for row in usable]
    in_range_runs = [value for value in values if float(min_pct) <= value <= float(max_pct)]
    spread = (max(values) - min(values)) if values else 0.0
    ok = bool(
        usable
        and len(in_range_runs) >= int(min_in_range_runs)
        and spread <= float(max_spread_pp)
        and len(usable) == len(rows)
    )
    return {
        "ok": ok,
        "usable_run_count": len(usable),
        "total_run_count": len(rows),
        "in_range_run_count": len(in_range_runs),
        "spread_pp": round(spread, 4),
        "values": values,
    }


def evaluate_l4_canonical_baseline_v0(
    *,
    candidate_dirs: list[str],
    target_min_off_success_pct: float = 60.0,
    target_max_off_success_pct: float = 90.0,
    required_total_runs: int = 3,
    min_in_range_runs: int = 2,
    max_repeat_spread_pp: float = 20.0,
) -> dict[str, Any]:
    rows = [_candidate_row(x) for x in candidate_dirs if str(x).strip()]
    rows = [row for row in rows if str(row.get("candidate_dir") or "").strip()]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("budget_token") or "0x0"), []).append(row)
    for budget_token, items in grouped.items():
        grouped[budget_token] = sorted(items, key=lambda row: _suffix_rank(Path(str(row.get("candidate_dir") or ""))))

    initial_rows = [items[0] for _budget, items in grouped.items() if items]
    initial_rows = sorted(initial_rows, key=_budget_sort_key)

    reasons: list[str] = []
    status = "PASS"
    decision = "hold"

    complete_rows = [row for row in initial_rows if row.get("complete_artifacts")]
    if len(complete_rows) != len(initial_rows):
        reasons.append("missing_artifacts")

    infra_total = sum(_to_int(row.get("infra_failure_count"), 0) for row in initial_rows)
    if infra_total > 0:
        reasons.append("infra")

    provenance_keys = ("planner_backend", "llm_model", "taskset_in")
    provenance_values = {
        key: sorted(set(str(row.get(key) or "") for row in complete_rows if str(row.get(key) or "")))
        for key in provenance_keys
    }
    if any(len(values) > 1 for values in provenance_values.values()):
        reasons.append("inconsistent_provenance")
        status = "NEEDS_REVIEW"

    stability = {
        "ok": False,
        "usable_run_count": 0,
        "total_run_count": 0,
        "in_range_run_count": 0,
        "spread_pp": 0.0,
        "values": [],
    }
    canonical_budget: dict[str, Any] | None = None
    selected_runs: list[dict[str, Any]] = []
    pending_repeat = False
    unstable_candidate = False
    for row in initial_rows:
        if not row.get("complete_artifacts"):
            continue
        if _to_int(row.get("infra_failure_count"), 0) > 0:
            continue
        if row.get("baseline_in_target_range") is not True:
            continue
        runs = grouped.get(str(row.get("budget_token") or ""), [])
        if len(runs) < int(required_total_runs):
            pending_repeat = True
            continue
        candidate_stability = _stability_payload(
            runs,
            min_pct=float(target_min_off_success_pct),
            max_pct=float(target_max_off_success_pct),
            min_in_range_runs=int(min_in_range_runs),
            max_spread_pp=float(max_repeat_spread_pp),
        )
        if candidate_stability.get("ok"):
            selected_runs = runs
            stability = candidate_stability
            canonical_budget = {
                "budget_token": str(row.get("budget_token") or ""),
                "candidate_dir": str(row.get("candidate_dir") or ""),
                "max_rounds": _to_int(row.get("max_rounds"), 0),
                "max_time_sec": _to_int(row.get("max_time_sec"), 0),
                "baseline_off_success_at_k_pct": _to_float(row.get("baseline_off_success_at_k_pct"), 0.0),
                "planner_backend": str(row.get("planner_backend") or ""),
                "llm_model": str(row.get("llm_model") or ""),
                "taskset_in": str(row.get("taskset_in") or ""),
                "git_commit": str(row.get("git_commit") or ""),
            }
            break
        unstable_candidate = True

    if canonical_budget is not None:
        pass
    elif pending_repeat:
        reasons.append("repeat_required")
        status = "NEEDS_REVIEW"
    elif unstable_candidate:
        reasons.append("candidate_unstable")
    else:
        strength_rows = [row for row in initial_rows if row.get("complete_artifacts") and _to_int(row.get("infra_failure_count"), 0) == 0 and _to_int(row.get("max_rounds"), 0) >= 2]
        if not strength_rows:
            strength_rows = [row for row in initial_rows if row.get("complete_artifacts") and _to_int(row.get("infra_failure_count"), 0) == 0]
        if strength_rows:
            values = [_to_float(row.get("baseline_off_success_at_k_pct"), 0.0) for row in strength_rows]
            if values and all(value < float(target_min_off_success_pct) for value in values):
                reasons.append("baseline_too_weak")
            elif values and all(value > float(target_max_off_success_pct) for value in values):
                reasons.append("baseline_too_strong")
            else:
                reasons.append("no_in_range_candidate")
        else:
            reasons.append("no_in_range_candidate")

    primary_reason = "none"
    for reason in PRIMARY_REASON_PRIORITY:
        if reason in reasons:
            primary_reason = reason
            break

    if not reasons:
        decision = "ready"
    else:
        decision = "hold"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "decision": decision,
        "primary_reason": primary_reason,
        "reason_priority": PRIMARY_REASON_PRIORITY,
        "reasons": sorted(set(reasons)),
        "canonical_budget": canonical_budget,
        "stability_ok": bool(stability.get("ok")),
        "stability_total_run_count": _to_int(stability.get("total_run_count"), 0),
        "stability_usable_run_count": _to_int(stability.get("usable_run_count"), 0),
        "stability_in_range_run_count": _to_int(stability.get("in_range_run_count"), 0),
        "stability_spread_pp": _to_float(stability.get("spread_pp"), 0.0),
        "baseline_planner_backend": provenance_values.get("planner_backend", [None])[0] if len(provenance_values.get("planner_backend", [])) == 1 else None,
        "baseline_llm_model": provenance_values.get("llm_model", [None])[0] if len(provenance_values.get("llm_model", [])) == 1 else None,
        "base_taskset": provenance_values.get("taskset_in", [None])[0] if len(provenance_values.get("taskset_in", [])) == 1 else None,
        "thresholds": {
            "target_min_off_success_pct": float(target_min_off_success_pct),
            "target_max_off_success_pct": float(target_max_off_success_pct),
            "required_total_runs": int(required_total_runs),
            "min_in_range_runs": int(min_in_range_runs),
            "max_repeat_spread_pp": float(max_repeat_spread_pp),
        },
        "candidate_runs": rows,
        "selected_budget_runs": selected_runs,
        "infra_failure_count_total": infra_total,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Select canonical L4 baseline budget from challenge runs")
    parser.add_argument("--candidate-dir", action="append", default=[])
    parser.add_argument("--target-min-off-success-pct", type=float, default=60.0)
    parser.add_argument("--target-max-off-success-pct", type=float, default=90.0)
    parser.add_argument("--required-total-runs", type=int, default=3)
    parser.add_argument("--min-in-range-runs", type=int, default=2)
    parser.add_argument("--max-repeat-spread-pp", type=float, default=20.0)
    parser.add_argument("--out", default="artifacts/agent_modelica_l4_canonical_baseline_v0/summary.json")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    summary = evaluate_l4_canonical_baseline_v0(
        candidate_dirs=[str(x) for x in args.candidate_dir],
        target_min_off_success_pct=float(args.target_min_off_success_pct),
        target_max_off_success_pct=float(args.target_max_off_success_pct),
        required_total_runs=int(args.required_total_runs),
        min_in_range_runs=int(args.min_in_range_runs),
        max_repeat_spread_pp=float(args.max_repeat_spread_pp),
    )
    summary["inputs"] = {"candidate_dirs": [str(x) for x in args.candidate_dir]}

    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "decision": summary.get("decision"),
                "primary_reason": summary.get("primary_reason"),
                "canonical_budget_token": ((summary.get("canonical_budget") or {}).get("budget_token")),
                "stability_ok": summary.get("stability_ok"),
            }
        )
    )


if __name__ == "__main__":
    main()
