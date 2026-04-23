"""Analyze BLT-like candidate density conversion for v0.19.56.

This is an offline analyzer over v0.19.56 trajectory artifacts. It does not
call an LLM, does not run OMC, and does not change repair behavior.
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
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "blt_density_conversion_v0_19_56"
BASELINE_MODE = "baseline-c5"
BLT_MODE = "blt-c5"


def load_result(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sim_pass_candidate_ids(round_record: dict[str, Any]) -> list[int]:
    ids: list[int] = []
    for attempt in round_record.get("simulate_attempts", []):
        if attempt.get("simulate_pass"):
            ids.append(int(attempt["candidate_id"]))
    return ids


def round_conversion_record(
    *,
    candidate_id: str,
    mode: str,
    round_record: dict[str, Any],
) -> dict[str, Any]:
    sim_ids = sim_pass_candidate_ids(round_record)
    chosen = round_record.get("chosen_candidate_id")
    chosen_id = int(chosen) if chosen is not None else None
    return {
        "candidate_id": candidate_id,
        "mode": mode,
        "round": int(round_record.get("round") or 0),
        "num_candidates": int(round_record.get("num_candidates") or 0),
        "check_pass_count": int(round_record.get("coverage_check_pass") or 0),
        "simulate_pass_count": len(sim_ids),
        "simulate_pass_candidate_ids": sim_ids,
        "chosen_candidate_id": chosen_id,
        "chosen_is_simulate_pass": chosen_id in sim_ids if chosen_id is not None else False,
        "advance": round_record.get("advance", ""),
    }


def summarize_case(result: dict[str, Any]) -> dict[str, Any]:
    rounds = [
        round_conversion_record(
            candidate_id=result["candidate_id"],
            mode=result["mode"],
            round_record=round_record,
        )
        for round_record in result.get("rounds", [])
    ]
    return {
        "candidate_id": result["candidate_id"],
        "mode": result["mode"],
        "final_status": result.get("final_status"),
        "round_count": int(result.get("round_count") or len(rounds)),
        "simulate_pass_candidate_total": sum(
            record["simulate_pass_count"] for record in rounds
        ),
        "rounds_with_simulate_pass": sum(
            1 for record in rounds if record["simulate_pass_count"] > 0
        ),
        "rounds": rounds,
    }


def classify_blt_conversion(blt_case: dict[str, Any]) -> str:
    if blt_case["final_status"] == "pass":
        return "converted_to_pass"
    has_sim_candidate = any(
        record["simulate_pass_count"] > 0 for record in blt_case["rounds"]
    )
    if not has_sim_candidate:
        return "no_good_candidate_emerged"
    selected_sim_candidate = any(
        record["chosen_is_simulate_pass"] for record in blt_case["rounds"]
    )
    if not selected_sim_candidate:
        return "selection_miss"
    return "selected_but_incomplete"


def compare_cases(
    baseline_case: dict[str, Any],
    blt_case: dict[str, Any],
) -> dict[str, Any]:
    baseline_total = baseline_case["simulate_pass_candidate_total"]
    blt_total = blt_case["simulate_pass_candidate_total"]
    return {
        "candidate_id": blt_case["candidate_id"],
        "baseline_final_status": baseline_case["final_status"],
        "blt_final_status": blt_case["final_status"],
        "baseline_simulate_pass_candidate_total": baseline_total,
        "blt_simulate_pass_candidate_total": blt_total,
        "simulate_pass_candidate_delta": blt_total - baseline_total,
        "baseline_rounds_with_simulate_pass": baseline_case["rounds_with_simulate_pass"],
        "blt_rounds_with_simulate_pass": blt_case["rounds_with_simulate_pass"],
        "conversion_class": classify_blt_conversion(blt_case),
    }


def build_analysis(trajectory_dir: Path) -> dict[str, Any]:
    baseline_results: dict[str, dict[str, Any]] = {}
    blt_results: dict[str, dict[str, Any]] = {}

    for path in sorted(trajectory_dir.glob(f"*_{BASELINE_MODE}.json")):
        if path.name.startswith("summary_"):
            continue
        result = load_result(path)
        if not result.get("error"):
            baseline_results[result["candidate_id"]] = summarize_case(result)
    for path in sorted(trajectory_dir.glob(f"*_{BLT_MODE}.json")):
        if path.name.startswith("summary_"):
            continue
        result = load_result(path)
        if not result.get("error"):
            blt_results[result["candidate_id"]] = summarize_case(result)

    shared_ids = sorted(set(baseline_results) & set(blt_results))
    case_comparisons = [
        compare_cases(baseline_results[cid], blt_results[cid]) for cid in shared_ids
    ]
    round_records: list[dict[str, Any]] = []
    for cid in shared_ids:
        round_records.extend(baseline_results[cid]["rounds"])
        round_records.extend(blt_results[cid]["rounds"])

    positive_delta_cases = [
        item for item in case_comparisons if item["simulate_pass_candidate_delta"] > 0
    ]
    negative_delta_cases = [
        item for item in case_comparisons if item["simulate_pass_candidate_delta"] < 0
    ]
    flat_delta_cases = [
        item for item in case_comparisons if item["simulate_pass_candidate_delta"] == 0
    ]
    conversion_counts: dict[str, int] = {}
    for item in case_comparisons:
        key = item["conversion_class"]
        conversion_counts[key] = conversion_counts.get(key, 0) + 1

    baseline_total = sum(
        item["baseline_simulate_pass_candidate_total"] for item in case_comparisons
    )
    blt_total = sum(item["blt_simulate_pass_candidate_total"] for item in case_comparisons)
    blt_failed = [item for item in case_comparisons if item["blt_final_status"] != "pass"]
    failed_with_good_candidate = [
        item for item in blt_failed if item["blt_simulate_pass_candidate_total"] > 0
    ]

    return {
        "version": "v0.19.56",
        "source_artifact": str(trajectory_dir),
        "modes": [BASELINE_MODE, BLT_MODE],
        "case_count": len(shared_ids),
        "totals": {
            "baseline_simulate_pass_candidates": baseline_total,
            "blt_simulate_pass_candidates": blt_total,
            "delta": blt_total - baseline_total,
            "positive_delta_case_count": len(positive_delta_cases),
            "flat_delta_case_count": len(flat_delta_cases),
            "negative_delta_case_count": len(negative_delta_cases),
            "blt_failed_case_count": len(blt_failed),
            "blt_failed_with_simulate_pass_candidate_count": len(
                failed_with_good_candidate
            ),
        },
        "conversion_counts": conversion_counts,
        "case_comparisons": case_comparisons,
        "round_records": round_records,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            if isinstance(out.get("simulate_pass_candidate_ids"), list):
                out["simulate_pass_candidate_ids"] = ",".join(
                    str(item) for item in out["simulate_pass_candidate_ids"]
                )
            writer.writerow(out)


def render_report(analysis: dict[str, Any]) -> str:
    totals = analysis["totals"]
    conversion_counts = analysis["conversion_counts"]
    lines = [
        "# v0.19.56 BLT-like Density Conversion Report",
        "",
        "## 核心结论",
        "",
        (
            f"- BLT-like 的 simulate-pass candidate 总数："
            f"{totals['baseline_simulate_pass_candidates']} -> "
            f"{totals['blt_simulate_pass_candidates']} "
            f"(delta {totals['delta']:+d})"
        ),
        (
            f"- 正增量 case 数：{totals['positive_delta_case_count']}；"
            f"持平：{totals['flat_delta_case_count']}；"
            f"负增量：{totals['negative_delta_case_count']}"
        ),
        (
            f"- BLT 失败 case 中仍出现 simulate-pass candidate 的数量："
            f"{totals['blt_failed_with_simulate_pass_candidate_count']} / "
            f"{totals['blt_failed_case_count']}"
        ),
        "",
        "## 归因计数",
        "",
    ]
    for key in sorted(conversion_counts):
        lines.append(f"- {key}: {conversion_counts[key]}")
    lines.extend(["", "## Case 对比", ""])
    lines.append(
        "| case | baseline | blt | baseline sim | blt sim | delta | class |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for item in analysis["case_comparisons"]:
        lines.append(
            "| {candidate_id} | {baseline_final_status} | {blt_final_status} | "
            "{baseline_simulate_pass_candidate_total} | "
            "{blt_simulate_pass_candidate_total} | "
            "{simulate_pass_candidate_delta:+d} | {conversion_class} |".format(**item)
        )
    lines.extend(
        [
            "",
            "## 解释",
            "",
            (
                "runner 会对所有 check-pass 候选做 simulate，并在本轮选中第一个 "
                "simulate-pass 候选。因此如果 BLT 失败 case 中没有 simulate-pass "
                "候选，瓶颈不是 ranker 选择，而是正确候选没有出现。"
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
        out_dir / "round_records.csv",
        analysis["round_records"],
        [
            "candidate_id",
            "mode",
            "round",
            "num_candidates",
            "check_pass_count",
            "simulate_pass_count",
            "simulate_pass_candidate_ids",
            "chosen_candidate_id",
            "chosen_is_simulate_pass",
            "advance",
        ],
    )
    write_csv(
        out_dir / "case_comparisons.csv",
        analysis["case_comparisons"],
        [
            "candidate_id",
            "baseline_final_status",
            "blt_final_status",
            "baseline_simulate_pass_candidate_total",
            "blt_simulate_pass_candidate_total",
            "simulate_pass_candidate_delta",
            "baseline_rounds_with_simulate_pass",
            "blt_rounds_with_simulate_pass",
            "conversion_class",
        ],
    )
    (out_dir / "REPORT.md").write_text(render_report(analysis), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze v0.19.56 BLT-like density conversion."
    )
    parser.add_argument("--trajectory-dir", type=Path, default=DEFAULT_TRAJECTORY_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    analysis = build_analysis(args.trajectory_dir)
    write_outputs(analysis, args.out_dir)

    totals = analysis["totals"]
    print("=== BLT DENSITY CONVERSION v0.19.56 ===")
    print(f"Cases: {analysis['case_count']}")
    print(
        "Sim-pass candidates: "
        f"{totals['baseline_simulate_pass_candidates']} -> "
        f"{totals['blt_simulate_pass_candidates']} "
        f"({totals['delta']:+d})"
    )
    print(f"Conversion counts: {analysis['conversion_counts']}")
    print(f"Wrote {args.out_dir}")


if __name__ == "__main__":
    main()
