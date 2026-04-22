"""Hard case deep analysis for v0.19.47.

Analyzes two classes of hard cases from the v0.19.45–46 experiment sequence:

  1. Stalled cases: turn_shape = stalled_no_progress in raw-only multi-turn trajectories
  2. Hint-resistant cases: B_dm_hint = FAIL in the v0.19.46 single-turn hint experiment

Outputs per-case forensic reports and an aggregate failure-mode taxonomy.

New in this version:
  - Sub-type classification for stalled cases based on patch direction analysis
  - Per-round diff analysis (patched vs broken vs source)
  - Detection of wrong-repair-direction (adding equations for parameters)
  - Detection of incomplete-repair (fixing equation reference but not removing phantom decl)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "artifacts" / "hard_case_analysis_v0_19_47"

TRIPLE_TRAJECTORY_DIR = REPO_ROOT / "artifacts" / "raw_only_triple_trajectory_v0_19_45" / "raw"
HINT_EXPERIMENT_DIR = REPO_ROOT / "artifacts" / "triple_hint_experiment_v0_19_46"
TRIPLE_ADMITTED = REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45" / "admitted_cases.jsonl"
TRIPLE_PP_PV_PV_ADMITTED = REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45_pp_pv_pv" / "admitted_cases.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _extract_eq_var_counts(omc_output: str) -> tuple[int | None, int | None]:
    """Parse equation and variable counts from OMC checkModel output."""
    m = re.search(r"has\s+(\d+)\s+equation\(s\)\s+and\s+(\d+)\s+variable\(s\)", omc_output)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def _compute_diff_stats(text_a: str, text_b: str) -> dict[str, Any]:
    """Simple line-level diff stats between two model texts."""
    lines_a = text_a.splitlines()
    lines_b = text_b.splitlines()
    max_lines = max(len(lines_a), len(lines_b))
    diff_count = 0
    diffs = []
    for i in range(max_lines):
        a = lines_a[i] if i < len(lines_a) else ""
        b = lines_b[i] if i < len(lines_b) else ""
        if a.strip() != b.strip():
            diff_count += 1
            diffs.append((i + 1, a, b))
    return {
        "lines_a": len(lines_a),
        "lines_b": len(lines_b),
        "diff_lines": diff_count,
        "diffs": diffs,
    }


def _detect_repair_direction(patched_text: str, broken_text: str, source_text: str) -> dict[str, Any]:
    """Analyze what kind of repair the LLM attempted.

    Returns:
        - added_equations_for_vars: list of var names that got "X = value;" equations
        - restored_parameters: list of var names that got "parameter Real X = ..." restored
        - fixed_phantom_refs: list of phantom var names whose refs were changed in equations
        - removed_phantom_decls: list of phantom var names whose declarations were removed
        - added_bridge_equations: list of bridge equations found
    """
    result = {
        "added_equations_for_vars": [],
        "restored_parameters": [],
        "fixed_phantom_refs": [],
        "removed_phantom_decls": [],
        "added_bridge_equations": [],
    }

    pat_lines = patched_text.splitlines()
    brk_lines = broken_text.splitlines()
    src_lines = source_text.splitlines()

    # Detect "X = value;" equations added in patched but not in broken
    pat_eqs = set()
    brk_eqs = set()
    for line in pat_lines:
        m = re.match(r"^\s*(\w+)\s*=\s*[^=;]+;", line)
        if m and not line.strip().startswith("//"):
            pat_eqs.add(m.group(1))
    for line in brk_lines:
        m = re.match(r"^\s*(\w+)\s*=\s*[^=;]+;", line)
        if m and not line.strip().startswith("//"):
            brk_eqs.add(m.group(1))

    for var in pat_eqs - brk_eqs:
        # Check if source has this as parameter
        src_has_param = any(re.search(rf"parameter\s+Real\s+{re.escape(var)}\b", line) for line in src_lines)
        if src_has_param:
            result["added_equations_for_vars"].append(var)
        else:
            result["added_bridge_equations"].append(var)

    # Detect restored parameters
    for line in pat_lines:
        m = re.search(r"parameter\s+Real\s+(\w+)\b.*=", line)
        if m:
            var = m.group(1)
            # Was this a Real (non-parameter) in broken?
            brk_has_real = any(re.search(rf"^\s*Real\s+{re.escape(var)}\b", l) for l in brk_lines)
            if brk_has_real:
                result["restored_parameters"].append(var)

    # Detect phantom reference fixes: phantom name replaced with base name in equations
    # Find all "_phantom" vars in broken
    phantom_names = set()
    for line in brk_lines:
        for m in re.finditer(r"(\w+)_phantom", line):
            phantom_names.add(m.group(1) + "_phantom")

    def _code_part(line: str) -> str:
        """Strip // comments to avoid matching inside comments."""
        return line.split("//")[0]

    for phantom in phantom_names:
        base = phantom.replace("_phantom", "")
        # Check if broken uses phantom in equations (ignore comments)
        brk_uses_phantom = any(
            re.search(rf"\b{re.escape(phantom)}\b", _code_part(line)) and "=" in _code_part(line)
            for line in brk_lines
        )
        pat_uses_phantom = any(
            re.search(rf"\b{re.escape(phantom)}\b", _code_part(line)) and "=" in _code_part(line)
            for line in pat_lines
        )
        if brk_uses_phantom and not pat_uses_phantom:
            # Did it switch to base name?
            pat_uses_base = any(
                re.search(rf"\b{re.escape(base)}\b", _code_part(line)) and "=" in _code_part(line)
                for line in pat_lines
            )
            if pat_uses_base:
                result["fixed_phantom_refs"].append(phantom)

        # Check if phantom declaration was removed
        brk_has_decl = any(re.search(rf"^\s*Real\s+{re.escape(phantom)}\b", line) for line in brk_lines)
        pat_has_decl = any(re.search(rf"^\s*Real\s+{re.escape(phantom)}\b", line) for line in pat_lines)
        if brk_has_decl and not pat_has_decl:
            result["removed_phantom_decls"].append(phantom)

    return result


def _classify_stalled_failure_mode(attempts: list[dict], broken_text: str, source_text: str) -> str:
    """Classify why a stalled case stopped making progress.

    Types:
      type_a_no_attempt        — never touched any root cause
      type_b1_wrong_direction  — attempted fix but wrong strategy (e.g. equation for parameter)
      type_b2_incomplete       — partial fix (e.g. fixed eq ref but not phantom decl)
      type_c_cycling           — model changes but same states repeat
      type_d_regression        — state regressed after partial fix
    """
    if not attempts:
        return "unknown"

    changed_attempts = [a for a in attempts if a.get("model_changed")]
    if not changed_attempts:
        return "type_a_no_attempt"

    # Analyze ALL changed attempts for repair direction
    has_wrong_direction = False
    has_incomplete = False
    for ca in changed_attempts:
        patched_path = str(ca.get("patched_model_path") or "")
        if patched_path and Path(patched_path).exists():
            patched_text = Path(patched_path).read_text(encoding="utf-8")
            direction = _detect_repair_direction(patched_text, broken_text, source_text)

            if direction["added_equations_for_vars"]:
                has_wrong_direction = True
            if direction["fixed_phantom_refs"] and not direction["removed_phantom_decls"]:
                has_incomplete = True

    if has_wrong_direction:
        return "type_b1_wrong_direction"
    if has_incomplete:
        return "type_b2_incomplete"

    # Check if states repeat in later rounds
    states_seq = []
    for a in attempts:
        states_seq.append((
            a.get("pp1_state_after", ""),
            a.get("pp2_state_after", ""),
            a.get("pv_state_after", ""),
        ))

    seen_states = set()
    for s in states_seq:
        if s in seen_states:
            return "type_c_cycling"
        seen_states.add(s)

    # Default: partial lock
    return "type_b2_incomplete"


def _analyze_stalled_case(traj_path: Path, admitted_map: dict[str, dict]) -> dict[str, Any]:
    """Deep analysis of one stalled trajectory case."""
    traj = json.loads(traj_path.read_text(encoding="utf-8"))
    cid = traj["candidate_id"]
    case = admitted_map.get(cid, {})

    # Read models
    source_path = Path(case.get("source_model_path", ""))
    source_text = source_path.read_text(encoding="utf-8") if source_path.exists() else ""

    broken_path = REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45_pp_pv_pv" / f"{cid}.mo"
    if not broken_path.exists():
        broken_path = REPO_ROOT / "artifacts" / "triple_underdetermined_experiment_v0_19_45" / f"{cid}.mo"
    broken_text = broken_path.read_text(encoding="utf-8") if broken_path.exists() else ""

    attempts = traj.get("attempts", [])
    round_reports: list[dict] = []

    for a in attempts:
        omc_out = str(a.get("omc_output_before_patch") or "")
        eq_n, var_n = _extract_eq_var_counts(omc_out)
        omc_after = str(a.get("omc_output_after_patch") or "")
        eq_after, var_after = _extract_eq_var_counts(omc_after)

        # Diff analysis for this round
        patch_path = str(a.get("patched_model_path") or "")
        diff_to_broken = None
        diff_to_source = None
        repair_direction = None
        if patch_path and Path(patch_path).exists():
            pat_text = Path(patch_path).read_text(encoding="utf-8")
            diff_to_broken = _compute_diff_stats(broken_text, pat_text)
            diff_to_source = _compute_diff_stats(source_text, pat_text)
            if broken_text and source_text:
                repair_direction = _detect_repair_direction(pat_text, broken_text, source_text)

        report = {
            "round": a.get("round"),
            "check_pass_before": a.get("check_pass_before_patch"),
            "check_pass_after": a.get("check_pass_after_patch"),
            "eq_before": eq_n,
            "var_before": var_n,
            "eq_after": eq_after,
            "var_after": var_after,
            "model_changed": a.get("model_changed"),
            "pp1_state": a.get("pp1_state_after"),
            "pp2_state": a.get("pp2_state_after"),
            "pv_state": a.get("pv_state_after"),
            "new_fix_pattern": a.get("new_fix_pattern"),
            "diff_to_broken_lines": diff_to_broken["diff_lines"] if diff_to_broken else None,
            "diff_to_source_lines": diff_to_source["diff_lines"] if diff_to_source else None,
            "repair_direction": repair_direction,
        }
        round_reports.append(report)

    failure_mode = _classify_stalled_failure_mode(attempts, broken_text, source_text)

    return {
        "candidate_id": cid,
        "case_type": "stalled",
        "source_file": traj.get("source_file", ""),
        "model_name": traj.get("model_name", ""),
        "turn_count": traj.get("turn_count"),
        "turn_shape": traj.get("turn_shape"),
        "final_status": traj.get("final_status"),
        "pp1_target": case.get("pp1_target", ""),
        "pp2_target": case.get("pp2_target", ""),
        "pv_target": case.get("pv_target", ""),
        "failure_mode": failure_mode,
        "rounds": round_reports,
    }


def _analyze_hint_resistant_case(hint_path: Path, admitted_map: dict[str, dict]) -> dict[str, Any]:
    """Deep analysis of one hint-resistant case."""
    hint = json.loads(hint_path.read_text(encoding="utf-8"))
    cid = hint["candidate_id"]
    case = admitted_map.get(cid, {})

    cond_a = hint.get("condition_a", {})
    cond_b = hint.get("condition_b", {})

    a_eq, a_var = _extract_eq_var_counts(cond_a.get("omc_output_snippet", ""))
    b_eq, b_var = _extract_eq_var_counts(cond_b.get("omc_output_snippet", ""))

    return {
        "candidate_id": cid,
        "case_type": "hint_resistant",
        "source_file": hint.get("source_file", ""),
        "pp1_target": hint.get("pp1_target", ""),
        "pv_target": hint.get("pv_target", ""),
        "condition_a": {
            "fix_pass": cond_a.get("fix_pass"),
            "eq": a_eq,
            "var": a_var,
            "error_class": cond_a.get("error_class", ""),
        },
        "condition_b": {
            "fix_pass": cond_b.get("fix_pass"),
            "eq": b_eq,
            "var": b_var,
            "error_class": cond_b.get("error_class", ""),
        },
        "var_reduction": (a_var - b_var) if (a_var and b_var) else None,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build admitted case maps
    admitted_map: dict[str, dict] = {}
    for path in [TRIPLE_ADMITTED, TRIPLE_PP_PV_PV_ADMITTED]:
        if path.exists():
            for row in _read_jsonl(path):
                admitted_map[row["candidate_id"]] = row

    results: list[dict] = []

    # ── Stalled cases ─────────────────────────────────────────────────────────
    print("=== STALLED CASES ===")
    stalled_count = 0
    for traj_path in sorted(TRIPLE_TRAJECTORY_DIR.glob("v01945_*.json")):
        traj = json.loads(traj_path.read_text(encoding="utf-8"))
        if traj.get("turn_shape") == "stalled_no_progress":
            report = _analyze_stalled_case(traj_path, admitted_map)
            results.append(report)
            stalled_count += 1
            print(f"  {report['candidate_id']} → {report['failure_mode']}")
            for r in report["rounds"]:
                rd = r.get("repair_direction") or {}
                extra = ""
                if rd.get("added_equations_for_vars"):
                    extra = f" [added_eq_for: {rd['added_equations_for_vars']}]"
                elif rd.get("fixed_phantom_refs"):
                    extra = f" [fixed_phantom: {rd['fixed_phantom_refs']}, removed_decl: {rd['removed_phantom_decls']}]"
                print(f"    R{r['round']}: changed={r['model_changed']}, pp1={r['pp1_state']}, pp2={r['pp2_state']}, pv={r['pv_state']}, eq={r['eq_before']}->{r['eq_after']}, var={r['var_before']}->{r['var_after']}{extra}")

    # ── Hint-resistant cases ──────────────────────────────────────────────────
    print("\n=== HINT-RESISTANT CASES ===")
    hint_count = 0
    for hint_path in sorted(HINT_EXPERIMENT_DIR.glob("v01945_*.json")):
        if hint_path.name in ("results.jsonl", "summary.json"):
            continue
        hint = json.loads(hint_path.read_text(encoding="utf-8"))
        if not hint.get("condition_b", {}).get("fix_pass"):
            report = _analyze_hint_resistant_case(hint_path, admitted_map)
            results.append(report)
            hint_count += 1
            a = report["condition_a"]
            b = report["condition_b"]
            print(f"  {report['candidate_id']}")
            print(f"    A_raw: eq={a['eq']}, var={a['var']}, pass={a['fix_pass']}")
            print(f"    B_hint: eq={b['eq']}, var={b['var']}, pass={b['fix_pass']}, reduction={report['var_reduction']}")

    # ── Aggregate summary ─────────────────────────────────────────────────────
    failure_mode_counts: dict[str, int] = {}
    for r in results:
        if r["case_type"] == "stalled":
            fm = r["failure_mode"]
            failure_mode_counts[fm] = failure_mode_counts.get(fm, 0) + 1

    summary = {
        "version": "v0.19.47",
        "n_stalled": stalled_count,
        "n_hint_resistant": hint_count,
        "total_hard_cases": len(results),
        "failure_mode_counts": failure_mode_counts,
        "cases": [r["candidate_id"] for r in results],
    }

    (OUT_DIR / "reports.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in results) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\n=== HARD CASE ANALYSIS SUMMARY ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
