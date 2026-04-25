#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_diversity_live_probe_v0_21_12 import (
    DEFAULT_BENCHMARK,
    DEFAULT_OUT_DIR,
    build_ab_summary,
    load_cases,
    run_first_turn_probe,
    run_diversity_live_probe,
    write_outputs,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.21.12 first-turn diversity live probe.")
    parser.add_argument("--benchmark", default=str(DEFAULT_BENCHMARK))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--mode", action="append", choices=["standard-c5", "diversity-c5"], default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    selected_modes = args.mode or ["standard-c5", "diversity-c5"]
    cases = load_cases(Path(args.benchmark))
    if args.limit is not None:
        cases = cases[: max(0, int(args.limit))]
    out_dir = Path(args.out_dir)
    rows = []
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(selected_modes) * len(cases)
    index = 0
    for mode in selected_modes:
        for case in cases:
            index += 1
            candidate_id = str(case.get("candidate_id") or case.get("task_id") or "")
            print(f"[{index}/{total}] mode={mode} case={candidate_id}", flush=True)
            row = run_first_turn_probe(case, mode=mode)
            rows.append(row)
            partial = build_ab_summary(rows)
            write_outputs(out_dir=out_dir, rows=rows, summary=partial)
            diversity = row.get("diversity") or {}
            print(
                "  check={check} sim={sim} structural={struct:.3f} text={text:.3f}".format(
                    check=row.get("first_turn_any_check_pass"),
                    sim=row.get("first_turn_any_simulate_pass"),
                    struct=float(diversity.get("structural_uniqueness_rate") or 0.0),
                    text=float(diversity.get("text_uniqueness_rate") or 0.0),
                ),
                flush=True,
            )
    summary = build_ab_summary(rows)
    write_outputs(out_dir=out_dir, rows=rows, summary=summary)
    deltas = summary["deltas"]
    standard = summary["mode_summaries"]["standard-c5"]
    diversity = summary["mode_summaries"]["diversity-c5"]
    print(
        "status={status} standard_check={s_chk}/{s_n} diversity_check={d_chk}/{d_n} "
        "structural_delta={struct_delta:.3f} check_delta={check_delta:.3f} conclusion={conclusion}".format(
            status=summary["status"],
            s_chk=standard["first_turn_any_check_pass_count"],
            s_n=standard["case_count"],
            d_chk=diversity["first_turn_any_check_pass_count"],
            d_n=diversity["case_count"],
            struct_delta=float(deltas["structural_uniqueness_delta"]),
            check_delta=float(deltas["first_turn_any_check_pass_rate_delta"]),
            conclusion=summary["conclusion"],
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
