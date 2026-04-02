from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_failure_analysis_v0_3_2 import DEFAULT_CONFIGS, analyze_failure_matrix


SCHEMA_VERSION = "agent_modelica_v0_3_12_failure_note"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_12_failure_note"
MAX_REPRESENTATIVE_CASES = 2


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _classify_terminal_failure(case: dict) -> str:
    resolution_paths = set(str(item or "") for item in (case.get("failure_resolution_paths") or []))
    stage_subtypes = set(str(item or "") for item in (case.get("failure_stage_subtypes") or []))
    rounds_used_values = [int(value or 0) for value in (case.get("rounds_used_values") or [])]
    max_rounds = max(rounds_used_values) if rounds_used_values else 0
    if resolution_paths == {"unresolved"} and "stage_3_behavioral_contract_semantic" in stage_subtypes and max_rounds <= 1:
        return "early_behavioral_contract_rejection"
    if resolution_paths == {"unresolved"} and max_rounds >= 3:
        return "budget_exhaustion_or_non_progress"
    if resolution_paths == {"unresolved"}:
        return "unresolved_search_path"
    return "other_terminal_path"


def _build_case_note(case: dict) -> dict:
    terminal_failure_class = _classify_terminal_failure(case)
    planner_invoked = bool(case.get("planner_invoked_any"))
    planner_decisive = bool(case.get("planner_decisive_any"))
    replay_used = bool(case.get("replay_used_any"))
    rounds_used_values = [int(value or 0) for value in (case.get("rounds_used_values") or [])]
    return {
        "mutation_id": str(case.get("mutation_id") or ""),
        "target_scale": str(case.get("target_scale") or ""),
        "expected_failure_type": str(case.get("expected_failure_type") or ""),
        "failed_configs": list(case.get("failed_configs") or []),
        "terminal_failure_class": terminal_failure_class,
        "failure_resolution_paths": list(case.get("failure_resolution_paths") or []),
        "failure_stage_subtypes": list(case.get("failure_stage_subtypes") or []),
        "planner_invoked_any": planner_invoked,
        "planner_decisive_any": planner_decisive,
        "replay_used_any": replay_used,
        "rounds_used_values": rounds_used_values,
        "elapsed_sec_range": list(case.get("elapsed_sec_range") or []),
        "interpretation": (
            "Planner is consistently invoked, but the failure terminates immediately at the behavioral contract semantic stage before any decisive recovery signal appears."
            if terminal_failure_class == "early_behavioral_contract_rejection"
            else "Failure remains unresolved across configs and should be treated as a structured terminal path, not an attribution gap."
        ),
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# GateForge v0.3.12 Failure Note",
        "",
        f"- generated_at_utc: `{payload.get('generated_at_utc')}`",
        f"- representative_case_count: `{payload.get('representative_case_count')}`",
        "",
    ]
    for case in payload.get("representative_cases") or []:
        if not isinstance(case, dict):
            continue
        lines.append(f"## {case.get('mutation_id')}")
        lines.append("")
        lines.append(f"- expected_failure_type: `{case.get('expected_failure_type')}`")
        lines.append(f"- terminal_failure_class: `{case.get('terminal_failure_class')}`")
        lines.append(f"- failed_configs: `{', '.join(case.get('failed_configs') or [])}`")
        lines.append(f"- failure_stage_subtypes: `{', '.join(case.get('failure_stage_subtypes') or [])}`")
        lines.append(f"- failure_resolution_paths: `{', '.join(case.get('failure_resolution_paths') or [])}`")
        lines.append(f"- planner_invoked_any: `{case.get('planner_invoked_any')}`, planner_decisive_any: `{case.get('planner_decisive_any')}`, replay_used_any: `{case.get('replay_used_any')}`")
        lines.append(f"- rounds_used_values: `{case.get('rounds_used_values')}`")
        lines.append(f"- elapsed_sec_range: `{case.get('elapsed_sec_range')}`")
        lines.append(f"- interpretation: `{case.get('interpretation')}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_v0_3_12_failure_note(*, out_dir: str = DEFAULT_OUT_DIR, configs: list[dict] | None = None) -> dict:
    analysis = analyze_failure_matrix(list(configs) if configs is not None else list(DEFAULT_CONFIGS))
    persistent = [row for row in analysis.get("persistent_failures") or [] if isinstance(row, dict)]
    representative = [_build_case_note(row) for row in persistent[:MAX_REPRESENTATIVE_CASES]]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "representative_case_count": len(representative),
        "representative_cases": representative,
        "source_config_labels": list(analysis.get("config_labels") or []),
        "persistent_failure_count": int(analysis.get("persistent_failure_count") or 0),
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.12 focused failure note from harder-holdout ablation results.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_12_failure_note(out_dir=str(args.out_dir))
    print(json.dumps({"representative_case_count": payload.get("representative_case_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
