"""Analyze per-turn root-cause attribution on raw-only double-compound trajectories.

This is an offline analysis only. It does not feed anything back to the LLM.

Inputs:
  - admitted compound cases from v0.19.38
  - raw trajectory JSON files from v0.19.42/v0.19.43
  - patched intermediate model files saved per turn

Outputs:
  - per-case per-turn attribution rows
  - aggregate summaries of fix order patterns
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ADMITTED_PATH = REPO_ROOT / "artifacts" / "compound_underdetermined_experiment_v0_19_38" / "admitted_cases.jsonl"
RAW_DIR = REPO_ROOT / "artifacts" / "raw_only_underdetermined_trajectory_v0_19_42" / "raw"
OUT_DIR = REPO_ROOT / "artifacts" / "compound_turn_attribution_v0_19_44"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _parameter_fixed(text: str, target: str) -> bool:
    if re.search(rf"^\s*parameter\s+Real\s+{re.escape(target)}\b.*=", text, re.MULTILINE):
        return True
    if re.search(rf"^\s*Real\s+{re.escape(target)}\b.*=", text, re.MULTILINE):
        return True
    if re.search(rf"^\s*{re.escape(target)}\s*=", text, re.MULTILINE):
        return True
    return False


def _phantom_fixed(text: str, target: str, base_var: str) -> bool:
    decl_re = re.compile(rf"^\s*Real\s+{re.escape(target)}\b", re.MULTILINE)
    target_tokens = len(re.findall(rf"\b{re.escape(target)}\b", text))
    base_present = re.search(rf"\b{re.escape(base_var)}\b", text) is not None
    return (not decl_re.search(text)) and target_tokens == 0 and base_present


def _fix_pattern(pp_fixed: bool, pv_fixed: bool) -> str:
    if pp_fixed and pv_fixed:
        return "both"
    if pp_fixed:
        return "pp_only"
    if pv_fixed:
        return "pv_only"
    return "none"


def _new_fix_pattern(prev_pp: bool, prev_pv: bool, now_pp: bool, now_pv: bool) -> str:
    new_pp = now_pp and not prev_pp
    new_pv = now_pv and not prev_pv
    return _fix_pattern(new_pp, new_pv)


def _reverted_pattern(prev_pp: bool, prev_pv: bool, now_pp: bool, now_pv: bool) -> str:
    rev_pp = prev_pp and not now_pp
    rev_pv = prev_pv and not now_pv
    return _fix_pattern(rev_pp, rev_pv)


def _load_cases() -> dict[str, dict]:
    return {row["candidate_id"]: row for row in _read_jsonl(ADMITTED_PATH)}


def _load_trajectory_rows() -> list[dict]:
    rows = []
    for path in sorted(RAW_DIR.glob("v01938_*.json")):
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def run() -> None:
    cases = _load_cases()
    trajectories = _load_trajectory_rows()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    turn1_pattern_counts: dict[str, int] = {}
    sequence_counts: dict[str, int] = {}
    partial_sequence_counts: dict[str, int] = {}

    for traj in trajectories:
        cid = traj["candidate_id"]
        case = cases.get(cid)
        if not case:
            continue

        pp_target = str(case["pp_target"])
        pv_target = str(case["pv_target"])
        pv_base = str(case["pv_base_var"])
        family_shape = str(traj.get("turn_shape") or "")

        broken_path = Path(case["mutated_model_path"])
        current_text = broken_path.read_text(encoding="utf-8")
        prev_pp = _parameter_fixed(current_text, pp_target)
        prev_pv = _phantom_fixed(current_text, pv_target, pv_base)
        seq_parts: list[str] = []

        rows.append(
            {
                "candidate_id": cid,
                "turn_label": "broken",
                "turn_index": 0,
                "turn_shape": family_shape,
                "final_status": traj.get("final_status"),
                "pp_target": pp_target,
                "pv_target": pv_target,
                "pv_base_var": pv_base,
                "pp_fixed": prev_pp,
                "pv_fixed": prev_pv,
                "state_pattern": _fix_pattern(prev_pp, prev_pv),
                "new_fix_pattern": "none",
                "reverted_pattern": "none",
            }
        )

        for attempt in traj.get("attempts", []):
            turn_idx = int(attempt.get("round") or 0)
            patched_path = str(attempt.get("patched_model_path") or "").strip()
            if patched_path and Path(patched_path).exists():
                next_text = Path(patched_path).read_text(encoding="utf-8")
            else:
                next_text = current_text

            pp_fixed = _parameter_fixed(next_text, pp_target)
            pv_fixed = _phantom_fixed(next_text, pv_target, pv_base)
            state_pattern = _fix_pattern(pp_fixed, pv_fixed)
            new_fix = _new_fix_pattern(prev_pp, prev_pv, pp_fixed, pv_fixed)
            reverted = _reverted_pattern(prev_pp, prev_pv, pp_fixed, pv_fixed)
            row = {
                "candidate_id": cid,
                "turn_label": f"T{turn_idx}",
                "turn_index": turn_idx,
                "turn_shape": family_shape,
                "final_status": traj.get("final_status"),
                "pp_target": pp_target,
                "pv_target": pv_target,
                "pv_base_var": pv_base,
                "pp_fixed": pp_fixed,
                "pv_fixed": pv_fixed,
                "state_pattern": state_pattern,
                "new_fix_pattern": new_fix,
                "reverted_pattern": reverted,
            }
            rows.append(row)

            if turn_idx >= 1:
                seq_parts.append(f"T{turn_idx}:{new_fix}")
                if turn_idx == 1:
                    turn1_pattern_counts[new_fix] = turn1_pattern_counts.get(new_fix, 0) + 1

            prev_pp = pp_fixed
            prev_pv = pv_fixed
            current_text = next_text

        seq = " | ".join(seq_parts)
        sequence_counts[seq] = sequence_counts.get(seq, 0) + 1
        if family_shape == "partial_fix_then_continue":
            partial_sequence_counts[seq] = partial_sequence_counts.get(seq, 0) + 1

    by_shape: dict[str, dict[str, int]] = {}
    for row in rows:
        if row["turn_index"] != 1:
            continue
        shape = str(row["turn_shape"] or "")
        bucket = by_shape.setdefault(shape, {})
        key = row["new_fix_pattern"]
        bucket[key] = bucket.get(key, 0) + 1

    summary = {
        "version": "v0.19.44",
        "source_version": "v0.19.43",
        "n_cases": len({r["candidate_id"] for r in rows}),
        "turn1_new_fix_pattern_counts": turn1_pattern_counts,
        "turn1_new_fix_pattern_by_shape": by_shape,
        "all_sequence_counts": sequence_counts,
        "partial_fix_sequence_counts": partial_sequence_counts,
    }

    (OUT_DIR / "turn_rows.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    run()
