"""Analyze per-turn root-cause attribution on raw-only triple-compound trajectories.

Two-level analysis:
  Structural: checkModel PASS (structural_fixed)
  Behavioral: simulate PASS (behavioral_fixed)

Inputs:
  - admitted triple cases
  - raw trajectory JSON files
  - patched intermediate model files

Outputs:
  - per-case per-turn attribution rows
  - aggregate summaries of structural/behavioral fix patterns

Usage:
  python3 scripts/analyze_triple_turn_attribution_v0_19_45.py
  python3 scripts/analyze_triple_turn_attribution_v0_19_45.py \
    --admitted-cases artifacts/triple_underdetermined_experiment_v0_19_45_pp_pv_pv/admitted_cases.jsonl \
    --trajectory-dir artifacts/raw_only_triple_triple_underdetermined_experiment_v0_19_45_pp_pv_pv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_cases(path: Path) -> dict[str, dict]:
    return {row["candidate_id"]: row for row in _read_jsonl(path)}


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--admitted-cases",
        type=Path,
        default=REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45" / "admitted_cases.jsonl",
    )
    parser.add_argument(
        "--trajectory-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "raw_only_triple_trajectory_v0_19_45",
    )
    args = parser.parse_args()

    raw_dir = args.trajectory_dir / "raw"
    out_name = args.trajectory_dir.name  # e.g. raw_only_triple_triple_underdetermined_experiment_v0_19_45_pp_pv_pv
    out_dir = REPO_ROOT / "artifacts" / f"analyze_{out_name}"

    cases = _load_cases(args.admitted_cases)
    trajectories = sorted(raw_dir.glob("v01945_*.json"))

    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    turn1_structural_counts: dict[str, int] = {}
    turn1_behavioral_counts: dict[str, int] = {}
    turn1_attempt_counts: dict[str, int] = {}
    sequence_structural_counts: dict[str, int] = {}
    sequence_behavioral_counts: dict[str, int] = {}
    partial_structural_seq_counts: dict[str, int] = {}

    # Track PP1 vs PP2 first-structural-fixed order
    pp1_first_struct = 0
    pp2_first_struct = 0
    both_struct_same_turn = 0

    # Track behavioral
    pp1_first_behav = 0
    pp2_first_behav = 0
    pv_first_behav = 0
    all_three_behav_same_turn = 0

    for traj_path in trajectories:
        traj = json.loads(traj_path.read_text())
        cid = traj["candidate_id"]
        case = cases.get(cid)
        if not case:
            continue

        pp1_target = str(case["pp1_target"])
        pp2_target = str(case["pp2_target"])
        pv_target = str(case["pv_target"])
        pv_base = str(case["pv_base_var"])
        family_shape = str(traj.get("turn_shape") or "")

        pp1_first_struct_turn: int | None = None
        pp2_first_struct_turn: int | None = None
        pv_first_struct_turn: int | None = None
        pp1_first_behav_turn: int | None = None
        pp2_first_behav_turn: int | None = None
        pv_first_behav_turn: int | None = None

        seq_struct_parts: list[str] = []
        seq_behav_parts: list[str] = []

        for attempt in traj.get("attempts", []):
            turn_idx = int(attempt.get("round") or 0)
            new_struct = str(attempt.get("new_structural_fix_pattern") or "none")
            new_behav = str(attempt.get("new_behavioral_fix_pattern") or "none")
            new_attempt = str(attempt.get("new_attempt_pattern") or "none")

            pp1_after = str(attempt.get("pp1_state_after") or "")
            pp2_after = str(attempt.get("pp2_state_after") or "")
            pv_after = str(attempt.get("pv_state_after") or "")

            # Structural FIXED states
            structural_fixed_states = {"structural_fixed", "structural_fixed_behavioral_incomplete", "behavioral_fixed"}
            # Behavioral FIXED
            BEHAVIORAL_FIXED = "behavioral_fixed"

            if pp1_after in structural_fixed_states and pp1_first_struct_turn is None:
                pp1_first_struct_turn = turn_idx
            if pp2_after in structural_fixed_states and pp2_first_struct_turn is None:
                pp2_first_struct_turn = turn_idx
            if pv_after in structural_fixed_states and pv_first_struct_turn is None:
                pv_first_struct_turn = turn_idx

            if pp1_after == BEHAVIORAL_FIXED and pp1_first_behav_turn is None:
                pp1_first_behav_turn = turn_idx
            if pp2_after == BEHAVIORAL_FIXED and pp2_first_behav_turn is None:
                pp2_first_behav_turn = turn_idx
            if pv_after == BEHAVIORAL_FIXED and pv_first_behav_turn is None:
                pv_first_behav_turn = turn_idx

            if turn_idx >= 1:
                seq_struct_parts.append(f"T{turn_idx}:{new_struct}")
                seq_behav_parts.append(f"T{turn_idx}:{new_behav}")
                if turn_idx == 1:
                    turn1_structural_counts[new_struct] = turn1_structural_counts.get(new_struct, 0) + 1
                    turn1_behavioral_counts[new_behav] = turn1_behavioral_counts.get(new_behav, 0) + 1
                    turn1_attempt_counts[new_attempt] = turn1_attempt_counts.get(new_attempt, 0) + 1

            row = {
                "candidate_id": cid,
                "turn_label": f"T{turn_idx}",
                "turn_index": turn_idx,
                "turn_shape": family_shape,
                "final_status": traj.get("final_status"),
                "pp1_target": pp1_target,
                "pp2_target": pp2_target,
                "pv_target": pv_target,
                "pv_base_var": pv_base,
                "check_pass_before": attempt.get("check_pass_before_patch"),
                "simulate_pass_before": attempt.get("simulate_pass_before_patch"),
                "check_pass_after": attempt.get("check_pass_after_patch"),
                "simulate_pass_after": attempt.get("simulate_pass_after_patch"),
                "pp1_state_after": pp1_after,
                "pp2_state_after": pp2_after,
                "pv_state_after": pv_after,
                "new_structural_fix_pattern": new_struct,
                "new_behavioral_fix_pattern": new_behav,
                "new_attempt_pattern": new_attempt,
                "reverted_pattern": str(attempt.get("reverted_pattern") or "none"),
            }
            rows.append(row)

        # Structural first-fixed order
        if pp1_first_struct_turn is not None and pp2_first_struct_turn is not None:
            if pp1_first_struct_turn < pp2_first_struct_turn:
                pp1_first_struct += 1
            elif pp2_first_struct_turn < pp1_first_struct_turn:
                pp2_first_struct += 1
            else:
                both_struct_same_turn += 1

        # Behavioral
        if pp1_first_behav_turn is not None:
            pp1_first_behav += 1
        if pp2_first_behav_turn is not None:
            pp2_first_behav += 1
        if pv_first_behav_turn is not None:
            pv_first_behav += 1
        if all(v is not None for v in [pp1_first_behav_turn, pp2_first_behav_turn, pv_first_behav_turn]):
            if pp1_first_behav_turn == pp2_first_behav_turn == pv_first_behav_turn:
                all_three_behav_same_turn += 1

        seq_struct = " | ".join(seq_struct_parts)
        seq_behav = " | ".join(seq_behav_parts)
        sequence_structural_counts[seq_struct] = sequence_structural_counts.get(seq_struct, 0) + 1
        sequence_behavioral_counts[seq_behav] = sequence_behavioral_counts.get(seq_behav, 0) + 1
        if family_shape == "partial_fix_then_continue":
            partial_structural_seq_counts[seq_struct] = partial_structural_seq_counts.get(seq_struct, 0) + 1

    by_shape_struct: dict[str, dict[str, int]] = {}
    for row in rows:
        if row["turn_index"] != 1:
            continue
        shape = str(row["turn_shape"] or "")
        bucket = by_shape_struct.setdefault(shape, {})
        key = row["new_structural_fix_pattern"]
        bucket[key] = bucket.get(key, 0) + 1

    # Compute per-trajectory turn_shape_simulate and aggregate counts
    trajectory_turn_shape_simulate_counts: dict[str, int] = {}
    for traj_path in trajectories:
        traj = json.loads(traj_path.read_text())
        cid = traj["candidate_id"]
        if cid not in {r["candidate_id"] for r in rows}:
            continue
        first_check_pass_turn: int | None = None
        first_simulate_pass_turn: int | None = None
        for a in traj.get("attempts", []):
            ridx = int(a.get("round") or 0)
            if ridx >= 1:
                if a.get("check_pass_after_patch") is True and first_check_pass_turn is None:
                    first_check_pass_turn = ridx
                if a.get("simulate_pass_after_patch") is True and first_simulate_pass_turn is None:
                    first_simulate_pass_turn = ridx
        if first_check_pass_turn is not None and first_simulate_pass_turn is not None:
            if first_check_pass_turn < first_simulate_pass_turn:
                tss = "check_then_simulate"
            elif first_simulate_pass_turn < first_check_pass_turn:
                tss = "simulate_then_check"
            else:
                tss = "check_and_simulate_same_turn"
        elif first_check_pass_turn is not None:
            tss = "check_only"
        elif first_simulate_pass_turn is not None:
            tss = "simulate_only"
        else:
            tss = "neither_ever_passed"
        trajectory_turn_shape_simulate_counts[tss] = trajectory_turn_shape_simulate_counts.get(tss, 0) + 1

    summary = {
        "version": "v0.19.45",
        "admitted_cases": str(args.admitted_cases),
        "trajectory_dir": str(raw_dir),
        "n_cases": len({r["candidate_id"] for r in rows}),
        "turn1_new_structural_fix_pattern_counts": turn1_structural_counts,
        "turn1_new_behavioral_fix_pattern_counts": turn1_behavioral_counts,
        "turn1_new_attempt_pattern_counts": turn1_attempt_counts,
        "turn1_new_structural_by_shape": by_shape_struct,
        "all_structural_sequence_counts": sequence_structural_counts,
        "all_behavioral_sequence_counts": sequence_behavioral_counts,
        "partial_structural_sequence_counts": partial_structural_seq_counts,
        "pp1_vs_pp2_first_structural_fixed": {
            "pp1_first": pp1_first_struct,
            "pp2_first": pp2_first_struct,
            "both_same_turn": both_struct_same_turn,
        },
        "behavioral_convergence": {
            "pp1_first_behav": pp1_first_behav,
            "pp2_first_behav": pp2_first_behav,
            "pv_first_behav": pv_first_behav,
            "all_three_same_turn": all_three_behav_same_turn,
        },
        "turn_shape_simulate_counts": trajectory_turn_shape_simulate_counts,
    }

    (out_dir / "turn_rows.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
