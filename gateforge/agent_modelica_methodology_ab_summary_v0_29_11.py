from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "methodology_ab_summary_v0_29_11"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _case_group(case_id: str) -> str:
    if "_" not in case_id:
        return "ungrouped"
    return case_id.split("_", 1)[0]


def _tool_counts(row: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for step in row.get("steps", []):
        for call in step.get("tool_calls", []):
            if not isinstance(call, dict):
                continue
            name = str(call.get("name") or "")
            if name:
                counts[name] = counts.get(name, 0) + 1
    return dict(sorted(counts.items()))


def _arm_rows(arm_dirs: dict[str, Path]) -> dict[str, dict[str, dict[str, Any]]]:
    by_arm: dict[str, dict[str, dict[str, Any]]] = {}
    for arm_name, arm_dir in arm_dirs.items():
        rows = load_jsonl(arm_dir / "results.jsonl")
        by_arm[arm_name] = {str(row.get("case_id") or ""): row for row in rows if row.get("case_id")}
    return by_arm


def build_methodology_ab_summary(*, arm_dirs: dict[str, Path], out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Any]:
    by_arm = _arm_rows(arm_dirs)
    all_case_ids = sorted({case_id for rows in by_arm.values() for case_id in rows})
    case_rows: list[dict[str, Any]] = []
    group_totals: dict[str, dict[str, Any]] = {}
    overall = {
        "case_count": 0,
        "pass_counts": {arm_name: 0 for arm_name in arm_dirs},
        "fail_to_pass": {arm_name: 0 for arm_name in arm_dirs if arm_name != "base"},
        "pass_to_fail": {arm_name: 0 for arm_name in arm_dirs if arm_name != "base"},
        "net_delta": {arm_name: 0 for arm_name in arm_dirs if arm_name != "base"},
    }

    for case_id in all_case_ids:
        group = _case_group(case_id)
        arm_verdicts: dict[str, str] = {}
        arm_tool_counts: dict[str, dict[str, int]] = {}
        for arm_name, rows in by_arm.items():
            row = rows.get(case_id) or {}
            verdict = str(row.get("final_verdict") or "MISSING")
            arm_verdicts[arm_name] = verdict
            arm_tool_counts[arm_name] = _tool_counts(row)
        baseline = arm_verdicts.get("base", "MISSING")
        transitions = {
            arm_name: f"{baseline}->{verdict}"
            for arm_name, verdict in arm_verdicts.items()
            if arm_name != "base" and verdict != baseline
        }
        case_rows.append(
            {
                "case_id": case_id,
                "group": group,
                "arm_verdicts": arm_verdicts,
                "tool_counts": arm_tool_counts,
                "transitions": transitions,
            }
        )
        totals = group_totals.setdefault(
            group,
            {
                "case_count": 0,
                "pass_counts": {arm_name: 0 for arm_name in arm_dirs},
                "fail_to_pass": {arm_name: 0 for arm_name in arm_dirs if arm_name != "base"},
                "pass_to_fail": {arm_name: 0 for arm_name in arm_dirs if arm_name != "base"},
                "net_delta": {arm_name: 0 for arm_name in arm_dirs if arm_name != "base"},
            },
        )
        totals["case_count"] += 1
        overall["case_count"] += 1
        for arm_name, verdict in arm_verdicts.items():
            if verdict == "PASS":
                totals["pass_counts"][arm_name] = totals["pass_counts"].get(arm_name, 0) + 1
                overall["pass_counts"][arm_name] = overall["pass_counts"].get(arm_name, 0) + 1
            if arm_name == "base":
                continue
            if baseline != "PASS" and verdict == "PASS":
                totals["fail_to_pass"][arm_name] = totals["fail_to_pass"].get(arm_name, 0) + 1
                overall["fail_to_pass"][arm_name] = overall["fail_to_pass"].get(arm_name, 0) + 1
            if baseline == "PASS" and verdict != "PASS":
                totals["pass_to_fail"][arm_name] = totals["pass_to_fail"].get(arm_name, 0) + 1
                overall["pass_to_fail"][arm_name] = overall["pass_to_fail"].get(arm_name, 0) + 1
        for arm_name in totals["net_delta"]:
            totals["net_delta"][arm_name] = (
                totals["fail_to_pass"].get(arm_name, 0) - totals["pass_to_fail"].get(arm_name, 0)
            )

    for arm_name in overall["net_delta"]:
        overall["net_delta"][arm_name] = (
            overall["fail_to_pass"].get(arm_name, 0) - overall["pass_to_fail"].get(arm_name, 0)
        )

    positive_arms = [
        arm_name
        for arm_name, net_delta in overall["net_delta"].items()
        if int(net_delta) > 0
    ]
    mixed_arms = [
        arm_name
        for arm_name, fail_to_pass in overall["fail_to_pass"].items()
        if int(fail_to_pass) > 0 and int(overall["net_delta"].get(arm_name, 0)) <= 0
    ]

    summary = {
        "version": "v0.29.11",
        "status": "PASS" if all_case_ids else "REVIEW",
        "analysis_scope": "methodology_ab_summary",
        "arm_names": sorted(arm_dirs),
        "case_count": len(all_case_ids),
        "overall": overall,
        "group_totals": dict(sorted(group_totals.items())),
        "cases": case_rows,
        "decision": (
            "methodology_ab_has_net_positive_delta"
            if positive_arms
            else "methodology_ab_has_mixed_delta_no_net_gain"
            if mixed_arms
            else "methodology_ab_no_positive_delta_observed"
        ),
        "discipline": {
            "deterministic_repair_added": False,
            "hidden_routing_added": False,
            "candidate_selection_added": False,
            "llm_capability_gain_claimed": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
