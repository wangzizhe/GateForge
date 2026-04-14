from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from .agent_modelica_v0_19_2_common import (
    DEFAULT_PROFILE_OUT_DIR,
    DEFAULT_TRAJECTORY_OUT_DIR,
    PROFILE_MIN_CASES,
    PROFILE_MIXED_THRESHOLD,
    PROFILE_STRONG_THRESHOLD,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)

VALID_PROFILE_CLASSES = {
    "strong_handled_pattern",
    "mixed_but_recoverable_pattern",
    "weak_residual_pattern",
    "insufficient_data",
}


def _assign_profile_class(case_count: int, turn_n_success_rate: float, progressive_solve_rate: float) -> str:
    if case_count < PROFILE_MIN_CASES:
        return "insufficient_data"
    if turn_n_success_rate >= PROFILE_STRONG_THRESHOLD:
        return "strong_handled_pattern"
    if turn_n_success_rate >= PROFILE_MIXED_THRESHOLD and progressive_solve_rate > 0:
        return "mixed_but_recoverable_pattern"
    return "weak_residual_pattern"


def build_v192_capability_profile(
    *,
    trajectory_summary_path: str = str(DEFAULT_TRAJECTORY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PROFILE_OUT_DIR),
) -> dict:
    dataset = load_json(trajectory_summary_path)
    trajectories = dataset.get("trajectories") or []

    category_cases: dict[str, list[dict]] = defaultdict(list)
    for trajectory in trajectories:
        for category in trajectory.get("taxonomy_chain") or []:
            category_cases[str(category)].append(trajectory)

    rows = []
    for category in sorted(category_cases):
        cases = category_cases[category]
        case_count = len(cases)
        success_count = sum(1 for case in cases if case.get("final_outcome") == "success")
        progressive_count = sum(1 for case in cases if bool(case.get("progressive_solve")))
        reason_counts = Counter(str(case.get("termination_reason") or "") for case in cases)
        dominant_reason = sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[0][0] if reason_counts else ""
        turn_n_success_rate = round(success_count / case_count, 4) if case_count else 0.0
        progressive_solve_rate = round(progressive_count / case_count, 4) if case_count else 0.0
        profile_class = _assign_profile_class(case_count, turn_n_success_rate, progressive_solve_rate)
        rows.append(
            {
                "taxonomy_category_id": category,
                "case_count": case_count,
                "turn_n_success_rate": turn_n_success_rate,
                "progressive_solve_rate": progressive_solve_rate,
                "dominant_termination_reason": dominant_reason,
                "profile_class": profile_class,
            }
        )

    eligible_rows = [row for row in rows if int(row["case_count"]) >= PROFILE_MIN_CASES]
    if eligible_rows:
        strongest_row = sorted(eligible_rows, key=lambda row: (-float(row["turn_n_success_rate"]), row["taxonomy_category_id"]))[0]
        weakest_row = sorted(eligible_rows, key=lambda row: (float(row["turn_n_success_rate"]), row["taxonomy_category_id"]))[0]
        strongest_category = strongest_row["taxonomy_category_id"]
        strongest_rate = strongest_row["turn_n_success_rate"]
        weakest_category = weakest_row["taxonomy_category_id"]
        weakest_rate = weakest_row["turn_n_success_rate"]
        sufficient_data = True
    else:
        strongest_category = None
        strongest_rate = None
        weakest_category = None
        weakest_rate = None
        sufficient_data = False

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_capability_profile",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "capability_profile_status": "PASS",
        "profile_rows": rows,
        "strongest_handled_taxonomy_category_id": strongest_category,
        "strongest_handled_turn_n_success_rate": strongest_rate,
        "weakest_residual_taxonomy_category_id": weakest_category,
        "weakest_residual_turn_n_success_rate": weakest_rate,
        "cross_case_readout_sufficient_data": sufficient_data,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.19.2 Capability Profile",
                "",
                f"- strongest_handled_taxonomy_category_id: `{strongest_category}`",
                f"- weakest_residual_taxonomy_category_id: `{weakest_category}`",
                f"- cross_case_readout_sufficient_data: `{sufficient_data}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.19.2 capability profile artifact.")
    parser.add_argument("--trajectory-summary", default=str(DEFAULT_TRAJECTORY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PROFILE_OUT_DIR))
    args = parser.parse_args()
    payload = build_v192_capability_profile(trajectory_summary_path=str(args.trajectory_summary), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload["status"], "capability_profile_status": payload["capability_profile_status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
