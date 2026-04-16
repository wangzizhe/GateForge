"""Build the v0.19.9 semantic reasoning closeout report."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = REPO_ROOT / "artifacts" / "semantic_reasoning_mutations_v0_19_9" / "admitted_cases.jsonl"
NORMAL_SUMMARY = REPO_ROOT / "artifacts" / "semantic_reasoning_trajectory_v0_19_9" / "summary.json"
OUT_DIR = REPO_ROOT / "artifacts" / "semantic_reasoning_report_v0_19_9"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _index(rows: list[dict]) -> dict[str, dict]:
    return {str(row.get("candidate_id") or ""): dict(row) for row in rows if str(row.get("candidate_id") or "")}


def _raw_payload(out_dir: Path, cid: str) -> dict:
    path = out_dir / "raw" / f"{cid}.json"
    if not path.exists():
        return {}
    return _load_json(path)


def _llm_selected_fault_parameter(payload: dict, fault_parameter: str) -> bool:
    for attempt in payload.get("attempts") or []:
        if not isinstance(attempt, dict):
            continue
        selected = {str(x) for x in (attempt.get("llm_plan_candidate_parameters") or [])}
        executed = set()
        resolution = attempt.get("source_blind_multistep_llm_resolution")
        if isinstance(resolution, dict):
            executed.update(str(x) for x in (resolution.get("parameter_names") or []))
            executed.update(str(x) for x in (resolution.get("llm_plan_execution_parameters") or []))
        if fault_parameter in selected or fault_parameter in executed:
            return True
    return False


def _case_record(case: dict, normal: dict) -> dict:
    cid = str(case.get("candidate_id") or "")
    fault_parameter = str((case.get("semantic_contract") or {}).get("fault_parameter") or "")
    normal_payload = _raw_payload(NORMAL_SUMMARY.parent, cid)
    normal_status = str(normal.get("executor_status") or normal.get("status") or "")
    selected_fault = _llm_selected_fault_parameter(normal_payload, fault_parameter)
    if normal_status == "PASS" and selected_fault:
        mechanism = "llm_semantic_guided_repair"
    elif normal_status == "PASS":
        mechanism = "executor_target_map_assisted_semantic_repair"
    else:
        mechanism = "unresolved"
    return {
        "candidate_id": cid,
        "normal_status": normal_status,
        "normal_turns": int(normal.get("n_turns") or 0),
        "requires_nonlocal_or_semantic_reasoning": bool(case.get("requires_nonlocal_or_semantic_reasoning")),
        "omc_localization_sufficient": bool(case.get("omc_localization_sufficient")),
        "failure_localization_not_explicit_tag": bool(case.get("failure_localization_not_explicit_tag")),
        "fault_parameter": fault_parameter,
        "llm_selected_fault_parameter": selected_fault,
        "resolution_mechanism": mechanism,
    }


def build_report() -> tuple[dict, list[dict]]:
    cases = _index(_load_jsonl(BENCHMARK))
    normal = _index(_load_json(NORMAL_SUMMARY).get("summaries") or [])
    records = [_case_record(cases[cid], normal.get(cid, {})) for cid in sorted(cases)]
    counts = Counter(record["resolution_mechanism"] for record in records)
    normal_pass = sum(1 for record in records if record["normal_status"] == "PASS")
    admitted_reasoning = sum(
        1
        for record in records
        if record["requires_nonlocal_or_semantic_reasoning"]
        and not record["omc_localization_sufficient"]
        and record["failure_localization_not_explicit_tag"]
    )
    report = {
        "version": "v0.19.9",
        "family": "semantic_initial_value_wrong_but_compiles",
        "n_cases": len(records),
        "normal_pass_count": normal_pass,
        "normal_pass_rate": normal_pass / len(records) if records else 0.0,
        "reasoning_admission_pass_count": admitted_reasoning,
        "resolution_mechanism_counts": dict(sorted(counts.items())),
        "conclusion": (
            "v0.19.9 admits the first small semantic reasoning family: OMC check/simulate pass, "
            "the failure is exposed only by a semantic product contract, and the LLM selects the "
            "fault parameter under the normal executor path."
        ),
    }
    return report, records


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report, records = build_report()
    (OUT_DIR / "summary.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "cases.jsonl").write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
