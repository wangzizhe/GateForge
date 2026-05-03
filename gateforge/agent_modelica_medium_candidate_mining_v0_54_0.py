from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .agent_modelica_hard_core_training_substrate_v0_43_0 import load_json, load_jsonl


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ARTIFACT_ROOT = REPO_ROOT / "artifacts"
DEFAULT_HARD_PACK = REPO_ROOT / "artifacts" / "hard_benchmark_pack_v0_49_2" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "medium_candidate_mining_v0_54_0"

MIN_EVIDENCE_COUNT = 2
MEDIUM_PASS_RATE_MIN = 0.2
MEDIUM_PASS_RATE_MAX = 0.7


def discover_result_paths(artifact_root: Path = DEFAULT_ARTIFACT_ROOT) -> list[Path]:
    if not artifact_root.exists():
        return []
    return sorted(artifact_root.glob("*/results.jsonl"))


def _row_outcome(row: dict[str, Any]) -> str:
    if str(row.get("provider_error") or "").strip():
        return "provider_error"
    verdict = str(row.get("final_verdict") or "").upper()
    if verdict == "PASS":
        return "pass"
    if verdict in {"FAIL", "FAILED"}:
        return "fail"
    return "unknown"


def collect_base_tool_use_outcomes(*, result_paths: list[Path]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in result_paths:
        for row in load_jsonl(path):
            if str(row.get("run_mode") or "") != "tool_use":
                continue
            if str(row.get("tool_profile") or "base") != "base":
                continue
            case_id = str(row.get("case_id") or "")
            if not case_id:
                continue
            outcome = _row_outcome(row)
            if outcome == "provider_error":
                records.setdefault(case_id, {"case_id": case_id, "pass": 0, "fail": 0, "provider_error": 0, "paths": []})
                records[case_id]["provider_error"] += 1
                continue
            if outcome not in {"pass", "fail"}:
                continue
            record = records.setdefault(case_id, {"case_id": case_id, "pass": 0, "fail": 0, "provider_error": 0, "paths": []})
            record[outcome] += 1
            record["paths"].append(str(path))
    return records


def summarize_medium_candidates(
    *,
    outcomes: dict[str, dict[str, Any]],
    hard_case_ids: list[str],
    version: str = "v0.54.0",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    hard_set = set(hard_case_ids)
    candidates: list[dict[str, Any]] = []
    easy_prior: list[str] = []
    hard_prior: list[str] = []
    for case_id, record in sorted(outcomes.items()):
        pass_count = int(record.get("pass") or 0)
        fail_count = int(record.get("fail") or 0)
        evidence_count = pass_count + fail_count
        if evidence_count < MIN_EVIDENCE_COUNT:
            continue
        pass_rate = pass_count / evidence_count
        row = {
            "case_id": case_id,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "provider_error_count": int(record.get("provider_error") or 0),
            "evidence_count": evidence_count,
            "pass_rate": round(pass_rate, 4),
            "already_hard_pack": case_id in hard_set,
            "source_result_paths": sorted(set(str(path) for path in record.get("paths") or [])),
        }
        if MEDIUM_PASS_RATE_MIN <= pass_rate <= MEDIUM_PASS_RATE_MAX and case_id not in hard_set:
            row["candidate_status"] = "medium_candidate"
            candidates.append(row)
        elif pass_rate > MEDIUM_PASS_RATE_MAX:
            easy_prior.append(case_id)
        elif pass_rate < MEDIUM_PASS_RATE_MIN:
            hard_prior.append(case_id)
    summary = {
        "version": version,
        "analysis_scope": "medium_candidate_mining",
        "status": "PASS" if candidates else "REVIEW",
        "evidence_role": "debug",
        "conclusion_allowed": False,
        "artifact_complete": True,
        "readiness_status": "medium_candidates_found" if candidates else "medium_candidates_missing",
        "min_evidence_count": MIN_EVIDENCE_COUNT,
        "target_pass_rate_band": [MEDIUM_PASS_RATE_MIN, MEDIUM_PASS_RATE_MAX],
        "observed_case_count": len(outcomes),
        "medium_candidate_count": len(candidates),
        "easy_prior_count": len(easy_prior),
        "hard_prior_count": len(hard_prior),
        "hard_pack_excluded_count": len(hard_set),
        "medium_candidate_ids": [row["case_id"] for row in candidates],
        "next_actions": [
            "audit_medium_candidates_for_blind_lint_and_source_backing",
            "rerun_medium_candidates_under_current_provider_before_promotion",
            "construct_new_medium_variants_if_candidate_count_is_too_low",
        ],
    }
    return summary, candidates


def write_medium_candidate_outputs(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    summary: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with (out_dir / "medium_candidates.jsonl").open("w", encoding="utf-8") as fh:
        for row in candidates:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def run_medium_candidate_mining(
    *,
    artifact_root: Path = DEFAULT_ARTIFACT_ROOT,
    hard_pack_path: Path = DEFAULT_HARD_PACK,
    out_dir: Path = DEFAULT_OUT_DIR,
) -> dict[str, Any]:
    result_paths = discover_result_paths(artifact_root)
    hard_pack = load_json(hard_pack_path)
    summary, candidates = summarize_medium_candidates(
        outcomes=collect_base_tool_use_outcomes(result_paths=result_paths),
        hard_case_ids=[str(case_id) for case_id in hard_pack.get("hard_case_ids") or []],
    )
    write_medium_candidate_outputs(out_dir=out_dir, summary=summary, candidates=candidates)
    return summary
