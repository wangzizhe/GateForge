from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

PATTERNS: list[tuple[str, str, str]] = [
    (r"undefined\s+symbol|undeclared", "declare_missing_symbol", "declare missing symbol and align declaration scope"),
    (r"connect(or)?\s+mismatch|incompatible\s+connector", "fix_connector_mismatch", "fix connector type/causality mismatch"),
    (r"initial(ization)?\s+failed|cannot\s+initialize", "fix_initialization", "stabilize initial equations and start values"),
    (r"singular|division\s+by\s+zero|nan|inf", "numerical_stability_guard", "add numerical guards and bounded parameters"),
    (r"too\s+many\s+events|event\s+chatter", "reduce_event_chatter", "reduce event triggering oscillations"),
]


def map_error_to_actions(error_message: str, failure_type: str | None = None) -> dict:
    text = str(error_message or "").strip().lower()
    tags: list[str] = []
    actions: list[str] = []
    if text:
        for pattern, tag, action in PATTERNS:
            if re.search(pattern, text):
                if tag not in tags:
                    tags.append(tag)
                if action not in actions:
                    actions.append(action)

    ftype = str(failure_type or "").strip().lower()
    if not actions and ftype == "model_check_error":
        tags.append("generic_model_check_repair")
        actions.append("resolve compile-time symbol/connector issues before simulate")
    elif not actions and ftype == "simulate_error":
        tags.append("generic_simulate_repair")
        actions.append("repair initialization and solver-facing constraints")
    elif not actions and ftype == "semantic_regression":
        tags.append("generic_semantic_repair")
        actions.append("repair invariant and behavioral regression before performance tuning")

    return {
        "tags": tags,
        "actions": actions,
        "mapped_count": len(actions),
    }


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Error Action Mapper v1",
        "",
        f"- mapped_count: `{payload.get('mapped_count')}`",
        f"- tags: `{','.join(payload.get('tags') or [])}`",
        "",
        "## Actions",
        "",
    ]
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    if actions:
        lines.extend([f"- {str(x)}" for x in actions])
    else:
        lines.append("- none")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Map compile/simulate error text into model edit actions")
    parser.add_argument("--error-message", required=True)
    parser.add_argument("--failure-type", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_error_action_mapper_v1/mapped.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    payload = map_error_to_actions(error_message=args.error_message, failure_type=args.failure_type)
    payload["schema_version"] = "agent_modelica_error_action_mapper_v1"
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"mapped_count": payload.get("mapped_count"), "tags": payload.get("tags")}))


if __name__ == "__main__":
    main()
