"""Audit routing-signal feasibility for v0.19.56.

This script compares three things:
  1. The desired representation from v0.19.56 offline stratification.
  2. The first live route selected in v0.19.56.
  3. The route that would be selected from admission/simulate failure output.

It does not call an LLM or OMC and does not make repair decisions.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_representation_routing_trajectory_v0_19_56 import (  # noqa: E402
    select_signal_route,
)

DEFAULT_STRATIFICATION_CSV = (
    REPO_ROOT
    / "artifacts"
    / "representation_effect_stratification_v0_19_56"
    / "case_stratification.csv"
)
DEFAULT_ROUTING_DIR = REPO_ROOT / "artifacts" / "representation_routing_trajectory_v0_19_56"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "routing_signal_feasibility_v0_19_56"
ADMITTED_CASE_FILES = [
    REPO_ROOT
    / "artifacts"
    / "triple_underdetermined_experiment_v0_19_45_pp_pv_pv"
    / "admitted_cases.jsonl",
    REPO_ROOT
    / "artifacts"
    / "triple_underdetermined_experiment_v0_19_45"
    / "admitted_cases.jsonl",
]

WARNING_RE = re.compile(r"Warning:\s+Variable\s+([A-Za-z_][A-Za-z0-9_]*)\s+")


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def load_admitted_cases(paths: list[Path] | None = None) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in paths or ADMITTED_CASE_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            rows.setdefault(row["candidate_id"], row)
    return rows


def extract_warning_variables(text: str) -> list[str]:
    seen: set[str] = set()
    variables: list[str] = []
    for match in WARNING_RE.finditer(text or ""):
        var = match.group(1)
        if var not in seen:
            seen.add(var)
            variables.append(var)
    return variables


def load_first_live_route(routing_dir: Path, candidate_id: str) -> tuple[str, str, bool]:
    path = routing_dir / f"{candidate_id}_signal-routed-c5.json"
    if not path.exists():
        return "", "", False
    result = json.loads(path.read_text(encoding="utf-8"))
    rounds = result.get("rounds", [])
    if not rounds:
        return "", str(result.get("final_status") or ""), False
    first = rounds[0]
    return (
        str(first.get("selected_representation_mode") or ""),
        str(result.get("final_status") or ""),
        bool(result.get("final_status") == "pass"),
    )


def classify_feasibility(row: dict[str, Any]) -> str:
    desired = row["desired_route"]
    if desired == "none":
        return "no_known_good_representation"
    if row["first_live_route"] != desired and row["admission_route"] == desired:
        return "signal_available_but_not_at_live_entry"
    if row["first_live_route"] != desired:
        return "no_stable_route_signal"
    if row["live_passed"]:
        return "route_match_and_pass"
    return "route_match_but_candidate_generation_failed"


def build_analysis(
    *,
    stratification_csv: Path = DEFAULT_STRATIFICATION_CSV,
    routing_dir: Path = DEFAULT_ROUTING_DIR,
    admitted_cases: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    strat_rows = load_csv_rows(stratification_csv)
    admitted = admitted_cases or load_admitted_cases()
    case_rows: list[dict[str, Any]] = []

    for item in strat_rows:
        candidate_id = item["candidate_id"]
        admitted_row = admitted.get(candidate_id, {})
        excerpt = str(admitted_row.get("mutated_failure_excerpt") or "")
        warning_vars = extract_warning_variables(excerpt)
        admission_route = select_signal_route(
            candidate_id=candidate_id,
            omc_output=excerpt,
        )
        first_live_route, live_status, live_passed = load_first_live_route(
            routing_dir, candidate_id
        )
        row = {
            "candidate_id": candidate_id,
            "model_family": item["model_family"],
            "desired_route": item["route_label"],
            "admission_route": admission_route,
            "first_live_route": first_live_route,
            "live_status": live_status,
            "live_passed": live_passed,
            "admission_warning_variables": warning_vars,
            "admission_warning_count": len(warning_vars),
            "admission_route_matches_desired": admission_route == item["route_label"],
            "live_route_matches_desired": first_live_route == item["route_label"],
        }
        row["feasibility_class"] = classify_feasibility(row)
        case_rows.append(row)

    desired_rows = [row for row in case_rows if row["desired_route"] != "none"]
    summary_counts: dict[str, int] = {}
    for row in case_rows:
        key = row["feasibility_class"]
        summary_counts[key] = summary_counts.get(key, 0) + 1

    admission_match_count = sum(
        1 for row in desired_rows if row["admission_route_matches_desired"]
    )
    live_match_count = sum(1 for row in desired_rows if row["live_route_matches_desired"])

    return {
        "version": "v0.19.56",
        "case_count": len(case_rows),
        "desired_route_case_count": len(desired_rows),
        "admission_route_match_count": admission_match_count,
        "admission_route_match_rate": (
            admission_match_count / len(desired_rows) if desired_rows else 0.0
        ),
        "live_route_match_count": live_match_count,
        "live_route_match_rate": live_match_count / len(desired_rows) if desired_rows else 0.0,
        "feasibility_counts": summary_counts,
        "case_rows": case_rows,
        "main_finding": (
            "Admission/simulate failure output carries stronger routing signal than "
            "the v0.19.56 live route entry."
        ),
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["admission_warning_variables"] = ",".join(
                out.get("admission_warning_variables", [])
            )
            writer.writerow(out)


def render_report(analysis: dict[str, Any]) -> str:
    lines = [
        "# v0.19.56 Routing Signal Feasibility Report",
        "",
        "## 核心结论",
        "",
        (
            f"- 有已知最佳表示的 case：{analysis['desired_route_case_count']} / "
            f"{analysis['case_count']}"
        ),
        (
            f"- admission/simulate 输出可复现最佳 route："
            f"{analysis['admission_route_match_count']} / "
            f"{analysis['desired_route_case_count']} "
            f"({analysis['admission_route_match_rate'] * 100:.1f}%)"
        ),
        (
            f"- v0.19.56 live 入口 route 命中最佳 route："
            f"{analysis['live_route_match_count']} / "
            f"{analysis['desired_route_case_count']} "
            f"({analysis['live_route_match_rate'] * 100:.1f}%)"
        ),
        f"- feasibility class：{analysis['feasibility_counts']}",
        "",
        "## Case 明细",
        "",
        "| case | desired | admission route | live route | class | warning vars |",
        "|---|---|---|---|---|---|",
    ]
    for row in analysis["case_rows"]:
        lines.append(
            "| {candidate_id} | {desired_route} | {admission_route} | "
            "{first_live_route} | {feasibility_class} | {vars} |".format(
                vars=",".join(row["admission_warning_variables"]),
                **row,
            )
        )
    lines.extend(
        [
            "",
            "## 解释",
            "",
            (
                "v0.19.56 的 live route 入口没有稳定拿到 admission/simulate 阶段的 "
                "underdetermined warning。很多 case 的关键变量信号存在于 admission "
                "failure excerpt 中，但 live route 仍然回落到 baseline 或错误表示。"
            ),
            "",
            (
                "因此当前问题不是继续写更多关键词 routing 规则，而是先修正 runner "
                "feedback wiring：当 checkModel 通过但 simulate/build 失败时，LLM "
                "和 representation router 应该看到 simulate/build 的失败输出。"
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
        out_dir / "case_signal_audit.csv",
        analysis["case_rows"],
        [
            "candidate_id",
            "model_family",
            "desired_route",
            "admission_route",
            "first_live_route",
            "live_status",
            "live_passed",
            "admission_warning_variables",
            "admission_warning_count",
            "admission_route_matches_desired",
            "live_route_matches_desired",
            "feasibility_class",
        ],
    )
    (out_dir / "REPORT.md").write_text(render_report(analysis), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit v0.19.56 routing signal feasibility")
    parser.add_argument("--stratification-csv", type=Path, default=DEFAULT_STRATIFICATION_CSV)
    parser.add_argument("--routing-dir", type=Path, default=DEFAULT_ROUTING_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    analysis = build_analysis(
        stratification_csv=args.stratification_csv,
        routing_dir=args.routing_dir,
    )
    write_outputs(analysis, args.out_dir)

    print("=== ROUTING SIGNAL FEASIBILITY v0.19.56 ===")
    print(f"Cases: {analysis['case_count']}")
    print(
        "Admission route match: "
        f"{analysis['admission_route_match_count']}/"
        f"{analysis['desired_route_case_count']} "
        f"({analysis['admission_route_match_rate'] * 100:.1f}%)"
    )
    print(
        "Live route match: "
        f"{analysis['live_route_match_count']}/"
        f"{analysis['desired_route_case_count']} "
        f"({analysis['live_route_match_rate'] * 100:.1f}%)"
    )
    print(f"Feasibility counts: {analysis['feasibility_counts']}")
    print(f"Wrote {args.out_dir}")


if __name__ == "__main__":
    main()
