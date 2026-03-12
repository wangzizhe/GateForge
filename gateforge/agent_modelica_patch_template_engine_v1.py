from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path

TEMPLATES: dict[str, dict] = {
    "underconstrained_system": {
        "template_id": "tpl_underconstrained_topology_restore_v1",
        "actions": [
            "restore the missing connect(...) edge before any declaration or equation rewrite",
            "restore dangling conservation path and connector balance before simulation",
            "rerun checkModel after every single topology repair step",
        ],
        "edit_directives": [
            {"kind": "restore_connect_edge", "priority": "high"},
            {"kind": "restore_conservation_path", "priority": "high"},
        ],
    },
    "model_check_error": {
        "template_id": "tpl_model_check_symbol_and_connector_v1",
        "actions": [
            "declare missing parameters/variables before equation usage",
            "align connector types and causality on each connect() pair",
            "rerun checkModel after every single edit chunk",
        ],
        "edit_directives": [
            {"kind": "declare_symbol", "priority": "high"},
            {"kind": "fix_connector_mismatch", "priority": "high"},
        ],
    },
    "simulate_error": {
        "template_id": "tpl_simulate_initialization_and_solver_v1",
        "actions": [
            "stabilize start values and initial equations near t=0",
            "bound unstable parameters before solver-facing equation edits",
            "reduce event chattering and verify short-horizon simulation",
        ],
        "edit_directives": [
            {"kind": "tune_initial_conditions", "priority": "high"},
            {"kind": "bound_parameters", "priority": "medium"},
        ],
    },
    "semantic_regression": {
        "template_id": "tpl_semantic_invariant_guard_v1",
        "actions": [
            "repair unit/sign/constraint violations first",
            "preserve invariant metrics before optimization edits",
            "block patches that improve speed but break steady-state/overshoot bounds",
        ],
        "edit_directives": [
            {"kind": "invariant_first_repair", "priority": "high"},
            {"kind": "guard_behavior_regression", "priority": "high"},
        ],
    },
}


FOCUS_GATE_ACTIONS: dict[str, list[str]] = {
    "regression_fail": [
        "enforce no-regression guard before accepting patch",
        "bound runtime drift within configured threshold before final merge",
        "prefer minimal localized edit over broad rewrite when regression risk rises",
    ],
    "physics_contract_fail": [
        "enforce invariant-first correction until physics contract re-passes",
        "reject edits that trade physical consistency for runtime speed",
    ],
    "simulate_fail": [
        "repair initialization stability before any structural optimization edits",
    ],
    "check_model_fail": [
        "restore compile/checkModel pass before touching simulation behavior",
    ],
}

REGRESSION_FAILURE_TYPE_ACTIONS: dict[str, list[str]] = {
    "model_check_error": [
        "after compile fixes, re-check runtime and steady-state deltas against baseline",
        "avoid declaration/connector fixes that silently alter physical parameter defaults",
    ],
    "simulate_error": [
        "after stability fixes, enforce no-regression checks on runtime and event count",
        "prefer parameter-bound edits over structural rewrites when runtime regression persists",
    ],
    "semantic_regression": [
        "restore steady-state/overshoot/settling metrics before any speed optimization",
        "re-run regression checkers after each invariant repair step",
    ],
}


def _load_adaptations_from_path(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    payload = json.loads(p.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _merge_actions(*groups: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for row in group:
            text = str(row).strip()
            if text and text not in seen:
                out.append(text)
                seen.add(text)
    return out


def _focus_actions(focus_queue_payload: dict, failure_type: str) -> list[str]:
    queue = focus_queue_payload.get("queue") if isinstance(focus_queue_payload.get("queue"), list) else []
    queue = [x for x in queue if isinstance(x, dict)]
    ftype = str(failure_type or "").strip().lower()
    out: list[str] = []
    seen: set[str] = set()
    has_global_regression_focus = any(str(x.get("gate_break_reason") or "").strip().lower() == "regression_fail" for x in queue)
    if has_global_regression_focus:
        for item in FOCUS_GATE_ACTIONS.get("regression_fail", []):
            text = str(item).strip()
            if text and text not in seen:
                out.append(text)
                seen.add(text)
    for row in queue:
        row_ftype = str(row.get("failure_type") or "").strip().lower()
        if row_ftype != ftype:
            continue
        gate = str(row.get("gate_break_reason") or "").strip().lower()
        for item in FOCUS_GATE_ACTIONS.get(gate, []):
            text = str(item).strip()
            if text and text not in seen:
                out.append(text)
                seen.add(text)
        if gate == "regression_fail":
            for item in REGRESSION_FAILURE_TYPE_ACTIONS.get(ftype, []):
                text = str(item).strip()
                if text and text not in seen:
                    out.append(text)
                    seen.add(text)
    return out


def build_patch_template(
    failure_type: str,
    expected_stage: str | None = None,
    focus_queue_payload: dict | None = None,
    adaptations_payload: dict | None = None,
) -> dict:
    ftype = str(failure_type or "unknown").strip().lower()
    base = TEMPLATES.get(ftype)
    focus_actions = _focus_actions(focus_queue_payload or {}, failure_type=ftype)
    loaded_adaptations = adaptations_payload
    if not isinstance(loaded_adaptations, dict):
        adapt_path = str(os.environ.get("GATEFORGE_AGENT_PATCH_TEMPLATE_ADAPTATIONS_PATH") or "").strip()
        if adapt_path:
            loaded_adaptations = _load_adaptations_from_path(adapt_path)
        else:
            loaded_adaptations = {}
    adapt_root = loaded_adaptations.get("failure_types") if isinstance(loaded_adaptations.get("failure_types"), dict) else loaded_adaptations
    adapt_row = adapt_root.get(ftype) if isinstance(adapt_root, dict) and isinstance(adapt_root.get(ftype), dict) else {}
    adapt_actions = [str(x) for x in (adapt_row.get("actions") or []) if isinstance(x, str)]
    adapt_directives = [x for x in (adapt_row.get("edit_directives") or []) if isinstance(x, dict)]
    if not base:
        return {
            "template_id": "tpl_generic_minimal_repair_v1",
            "failure_type": ftype,
            "expected_stage": str(expected_stage or "unknown"),
            "actions": _merge_actions([
                "classify failure signal before editing",
                "apply minimal deterministic fix and rerun hard gates",
            ], focus_actions, adapt_actions),
            "edit_directives": [{"kind": "minimal_safe_fix", "priority": "medium"}, *adapt_directives],
            "focus_actions_count": len(focus_actions),
            "adaptation_actions_count": len(adapt_actions),
        }
    return {
        "template_id": str(base.get("template_id") or "tpl_unknown"),
        "failure_type": ftype,
        "expected_stage": str(expected_stage or "unknown"),
        "actions": _merge_actions(
            [str(x) for x in (base.get("actions") or []) if isinstance(x, str)],
            focus_actions,
            adapt_actions,
        ),
        "edit_directives": [x for x in (base.get("edit_directives") or []) if isinstance(x, dict)] + adapt_directives,
        "focus_actions_count": len(focus_actions),
        "adaptation_actions_count": len(adapt_actions),
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
        "# GateForge Agent Modelica Patch Template Engine v1",
        "",
        f"- template_id: `{payload.get('template_id')}`",
        f"- failure_type: `{payload.get('failure_type')}`",
        f"- expected_stage: `{payload.get('expected_stage')}`",
        "",
    ]
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    lines.extend(["## Actions", ""])
    if actions:
        lines.extend([f"- {str(x)}" for x in actions])
    else:
        lines.append("- none")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build failure_type patch template for modelica repair")
    parser.add_argument("--failure-type", required=True)
    parser.add_argument("--expected-stage", default="unknown")
    parser.add_argument("--adaptations", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_patch_template_engine_v1/template.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    adaptations_payload = _load_adaptations_from_path(args.adaptations) if str(args.adaptations).strip() else {}
    payload = build_patch_template(
        failure_type=args.failure_type,
        expected_stage=args.expected_stage,
        adaptations_payload=adaptations_payload,
    )
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["schema_version"] = "agent_modelica_patch_template_engine_v1"
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"template_id": payload.get("template_id"), "failure_type": payload.get("failure_type")}))


if __name__ == "__main__":
    main()
