"""Stratify representation effects for v0.19.56.

Offline analysis over v0.19.56 representation trajectories. This script does
not call an LLM or OMC and does not make repair decisions.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_TRAJECTORY_DIR = REPO_ROOT / "artifacts" / "representation_trajectory_v0_19_56"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "representation_effect_stratification_v0_19_56"
MODES = ("baseline-c5", "causal-c5", "blt-c5")
TREATMENT_MODES = ("causal-c5", "blt-c5")


def load_result(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def infer_model_family(candidate_id: str) -> str:
    if "ExciterAVR" in candidate_id:
        return "ExciterAVR"
    if "HydroTurbineGov" in candidate_id:
        return "HydroTurbineGov"
    if "SyncMachineSimplified" in candidate_id:
        return "SyncMachineSimplified"
    if "ThermalZone" in candidate_id:
        return "ThermalZone"
    return "unknown"


def summarize_case_result(result: dict[str, Any]) -> dict[str, Any]:
    rounds = result.get("rounds", [])
    sim_total = 0
    check_total = 0
    rounds_with_sim = 0
    rounds_with_check = 0
    advances: list[str] = []
    rep_chars: list[int] = []
    selected_counts: list[int] = []
    block_counts: list[int] = []

    for round_record in rounds:
        sim_count = int(round_record.get("coverage_simulate_pass") or 0)
        check_count = int(round_record.get("coverage_check_pass") or 0)
        sim_total += sim_count
        check_total += check_count
        if sim_count:
            rounds_with_sim += 1
        if check_count:
            rounds_with_check += 1
        advances.append(str(round_record.get("advance") or ""))
        if round_record.get("representation_enabled"):
            rep_chars.append(int(round_record.get("representation_char_count") or 0))
            selected_counts.append(
                int(round_record.get("representation_selected_variable_count") or 0)
            )
            block_counts.append(int(round_record.get("representation_block_count") or 0))

    return {
        "candidate_id": result["candidate_id"],
        "mode": result["mode"],
        "model_family": infer_model_family(result["candidate_id"]),
        "final_status": result.get("final_status", "fail"),
        "passed": result.get("final_status") == "pass",
        "final_round": int(result.get("final_round") or 0),
        "round_count": int(result.get("round_count") or len(rounds)),
        "simulate_pass_candidate_total": sim_total,
        "check_pass_candidate_total": check_total,
        "rounds_with_simulate_pass": rounds_with_sim,
        "rounds_with_check_pass": rounds_with_check,
        "advance_sequence": " -> ".join(item for item in advances if item),
        "avg_representation_chars": (
            sum(rep_chars) / len(rep_chars) if rep_chars else 0.0
        ),
        "avg_selected_variables": (
            sum(selected_counts) / len(selected_counts) if selected_counts else 0.0
        ),
        "avg_block_count": sum(block_counts) / len(block_counts) if block_counts else 0.0,
    }


def treatment_effect(baseline: dict[str, Any], treatment: dict[str, Any]) -> str:
    if not baseline["passed"] and treatment["passed"]:
        return "rescued"
    if baseline["passed"] and not treatment["passed"]:
        return "regressed"
    if baseline["passed"] and treatment["passed"]:
        if treatment["final_round"] < baseline["final_round"]:
            return "preserved_pass_faster"
        if treatment["final_round"] > baseline["final_round"]:
            return "preserved_pass_slower"
        return "preserved_pass_same_round"
    return "preserved_fail"


def route_label(case_modes: dict[str, dict[str, Any]]) -> str:
    passing = [mode for mode in MODES if case_modes[mode]["passed"]]
    if not passing:
        return "none"
    if len(passing) == 1:
        return passing[0]
    # Prefer the simplest passing prompt if it already works.
    if "baseline-c5" in passing:
        return "baseline-c5"
    # Otherwise choose the treatment with more simulate-pass candidates.
    return max(
        passing,
        key=lambda mode: case_modes[mode]["simulate_pass_candidate_total"],
    )


def build_analysis(trajectory_dir: Path) -> dict[str, Any]:
    by_case: dict[str, dict[str, dict[str, Any]]] = {}
    for mode in MODES:
        for path in sorted(trajectory_dir.glob(f"*_{mode}.json")):
            if path.name.startswith("summary_"):
                continue
            result = load_result(path)
            if result.get("error"):
                continue
            summary = summarize_case_result(result)
            by_case.setdefault(summary["candidate_id"], {})[mode] = summary

    complete_ids = sorted(
        cid for cid, mode_map in by_case.items() if all(mode in mode_map for mode in MODES)
    )
    case_rows: list[dict[str, Any]] = []
    effect_rows: list[dict[str, Any]] = []

    for cid in complete_ids:
        mode_map = by_case[cid]
        route = route_label(mode_map)
        case_row = {
            "candidate_id": cid,
            "model_family": mode_map["baseline-c5"]["model_family"],
            "baseline_status": mode_map["baseline-c5"]["final_status"],
            "causal_status": mode_map["causal-c5"]["final_status"],
            "blt_status": mode_map["blt-c5"]["final_status"],
            "baseline_sim_candidates": mode_map["baseline-c5"][
                "simulate_pass_candidate_total"
            ],
            "causal_sim_candidates": mode_map["causal-c5"][
                "simulate_pass_candidate_total"
            ],
            "blt_sim_candidates": mode_map["blt-c5"]["simulate_pass_candidate_total"],
            "baseline_round_count": mode_map["baseline-c5"]["round_count"],
            "causal_round_count": mode_map["causal-c5"]["round_count"],
            "blt_round_count": mode_map["blt-c5"]["round_count"],
            "route_label": route,
            "any_mode_passed": route != "none",
        }
        case_rows.append(case_row)
        for treatment in TREATMENT_MODES:
            effect_rows.append(
                {
                    "candidate_id": cid,
                    "model_family": case_row["model_family"],
                    "mode": treatment,
                    "effect_vs_baseline": treatment_effect(
                        mode_map["baseline-c5"], mode_map[treatment]
                    ),
                    "sim_candidate_delta": (
                        mode_map[treatment]["simulate_pass_candidate_total"]
                        - mode_map["baseline-c5"]["simulate_pass_candidate_total"]
                    ),
                }
            )

    mode_pass_counts = {
        mode: sum(1 for cid in complete_ids if by_case[cid][mode]["passed"])
        for mode in MODES
    }
    union_pass_count = sum(1 for row in case_rows if row["any_mode_passed"])
    route_counts: dict[str, int] = {}
    for row in case_rows:
        route = row["route_label"]
        route_counts[route] = route_counts.get(route, 0) + 1

    effect_counts: dict[str, dict[str, int]] = {}
    for row in effect_rows:
        mode = row["mode"]
        effect = row["effect_vs_baseline"]
        effect_counts.setdefault(mode, {})
        effect_counts[mode][effect] = effect_counts[mode].get(effect, 0) + 1

    family_rows: list[dict[str, Any]] = []
    families = sorted({row["model_family"] for row in case_rows})
    for family in families:
        family_cases = [row for row in case_rows if row["model_family"] == family]
        family_rows.append(
            {
                "model_family": family,
                "case_count": len(family_cases),
                "baseline_pass": sum(1 for row in family_cases if row["baseline_status"] == "pass"),
                "causal_pass": sum(1 for row in family_cases if row["causal_status"] == "pass"),
                "blt_pass": sum(1 for row in family_cases if row["blt_status"] == "pass"),
                "union_pass": sum(1 for row in family_cases if row["any_mode_passed"]),
            }
        )

    return {
        "version": "v0.19.56",
        "source_artifact": str(trajectory_dir),
        "case_count": len(complete_ids),
        "mode_pass_counts": mode_pass_counts,
        "union_pass_count": union_pass_count,
        "union_pass_rate": union_pass_count / len(complete_ids) if complete_ids else 0.0,
        "route_counts": route_counts,
        "effect_counts": effect_counts,
        "case_rows": case_rows,
        "effect_rows": effect_rows,
        "family_rows": family_rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def render_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# v0.19.56 Representation Effect Stratification Report",
        "",
        "## 核心结论",
        "",
        (
            f"- 单一模式通过数：baseline={analysis['mode_pass_counts']['baseline-c5']}，"
            f"causal={analysis['mode_pass_counts']['causal-c5']}，"
            f"blt={analysis['mode_pass_counts']['blt-c5']}"
        ),
        (
            f"- 三种表示的 union 上界：{analysis['union_pass_count']} / "
            f"{analysis['case_count']} ({analysis['union_pass_rate'] * 100:.1f}%)"
        ),
        f"- route label 分布：{analysis['route_counts']}",
        "",
        "## Family 汇总",
        "",
        "| family | cases | baseline | causal | blt | union |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in analysis["family_rows"]:
        lines.append(
            "| {model_family} | {case_count} | {baseline_pass} | {causal_pass} | "
            "{blt_pass} | {union_pass} |".format(**row)
        )
    lines.extend(["", "## Case 汇总", ""])
    lines.append(
        "| case | family | baseline | causal | blt | sim baseline/causal/blt | route |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---|")
    for row in analysis["case_rows"]:
        lines.append(
            "| {candidate_id} | {model_family} | {baseline_status} | {causal_status} | "
            "{blt_status} | {baseline_sim_candidates}/{causal_sim_candidates}/"
            "{blt_sim_candidates} | {route_label} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## 解释",
            "",
            (
                "这不是新的 runner 结果，而是对同一批 v0.19.56 轨迹做离线分层。"
                "它只说明不同表示在当前 8 个 hard case 上的经验适配性，不能直接当成"
                "稳定 routing 规则。"
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(analysis: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(
        json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    write_csv(
        out_dir / "case_stratification.csv",
        analysis["case_rows"],
        [
            "candidate_id",
            "model_family",
            "baseline_status",
            "causal_status",
            "blt_status",
            "baseline_sim_candidates",
            "causal_sim_candidates",
            "blt_sim_candidates",
            "baseline_round_count",
            "causal_round_count",
            "blt_round_count",
            "route_label",
            "any_mode_passed",
        ],
    )
    write_csv(
        out_dir / "effect_vs_baseline.csv",
        analysis["effect_rows"],
        [
            "candidate_id",
            "model_family",
            "mode",
            "effect_vs_baseline",
            "sim_candidate_delta",
        ],
    )
    write_csv(
        out_dir / "family_stratification.csv",
        analysis["family_rows"],
        ["model_family", "case_count", "baseline_pass", "causal_pass", "blt_pass", "union_pass"],
    )
    (out_dir / "REPORT.md").write_text(render_report(analysis), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze representation effects across v0.19.56 arms."
    )
    parser.add_argument("--trajectory-dir", type=Path, default=DEFAULT_TRAJECTORY_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    analysis = build_analysis(args.trajectory_dir)
    write_outputs(analysis, args.out_dir)

    print("=== REPRESENTATION EFFECT STRATIFICATION v0.19.56 ===")
    print(f"Cases: {analysis['case_count']}")
    print(f"Mode pass counts: {analysis['mode_pass_counts']}")
    print(
        f"Union pass: {analysis['union_pass_count']}/{analysis['case_count']} "
        f"({analysis['union_pass_rate'] * 100:.1f}%)"
    )
    print(f"Route labels: {analysis['route_counts']}")
    print(f"Wrote {args.out_dir}")


if __name__ == "__main__":
    main()
