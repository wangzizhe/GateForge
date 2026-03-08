from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_modelica_electrical_msl_semantics_v0 import allowed_ir_param_names
from .agent_modelica_modeling_ir_v0 import (
    DEFAULT_COMPONENT_WHITELIST,
    ir_to_modelica,
    modelica_to_ir,
    validate_ir,
)
from .agent_modelica_repair_action_ir_v0 import validate_action_batch_v0


SCHEMA_VERSION = "agent_modelica_action_applier_v0"


def _clone_json(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: str) -> Any:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _component_index_by_id(ir_payload: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    components = ir_payload.get("components") if isinstance(ir_payload.get("components"), list) else []
    for idx, row in enumerate(components):
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "").strip()
        if cid:
            out[cid] = idx
    return out


def _normalized_edge(src: str, dst: str) -> tuple[str, str]:
    left = str(src or "").strip()
    right = str(dst or "").strip()
    return tuple(sorted([left, right]))


def _apply_set_parameter(ir_payload: dict, action: dict) -> None:
    components = ir_payload.get("components") if isinstance(ir_payload.get("components"), list) else []
    index_by_id = _component_index_by_id(ir_payload)
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    cid = str(target.get("component_id") or target.get("id") or "").strip()
    idx = index_by_id.get(cid)
    if idx is None:
        raise ValueError("apply_error_component_missing")
    component = components[idx]
    if not isinstance(component, dict):
        raise ValueError("apply_error_component_invalid")
    params = component.get("params") if isinstance(component.get("params"), dict) else {}
    ctype = str(component.get("type") or "")
    key = str(target.get("parameter") or target.get("param") or "").strip()
    allowed_params = allowed_ir_param_names(ctype)
    if allowed_params and key not in allowed_params:
        raise ValueError("apply_error_parameter_not_allowed")
    params[key] = args.get("value")
    component["params"] = params


def _apply_set_start_value(ir_payload: dict, action: dict) -> None:
    components = ir_payload.get("components") if isinstance(ir_payload.get("components"), list) else []
    index_by_id = _component_index_by_id(ir_payload)
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    cid = str(target.get("component_id") or target.get("id") or "").strip()
    idx = index_by_id.get(cid)
    if idx is None:
        raise ValueError("apply_error_component_missing")
    component = components[idx]
    if not isinstance(component, dict):
        raise ValueError("apply_error_component_invalid")
    params = component.get("params") if isinstance(component.get("params"), dict) else {}
    ctype = str(component.get("type") or "")
    variable = str(target.get("variable") or target.get("parameter") or target.get("param") or "").strip()
    allowed_params = allowed_ir_param_names(ctype)

    candidate_keys: list[str] = []
    if str(target.get("parameter") or target.get("param") or "").strip():
        candidate_keys.append(str(target.get("parameter") or target.get("param") or "").strip())
    candidate_keys.extend([f"{variable}Start", f"{variable}_start", "start", variable])
    key = ""
    if allowed_params:
        for row in candidate_keys:
            if row in allowed_params:
                key = row
                break
    else:
        key = candidate_keys[0] if candidate_keys else ""
    if not key:
        raise ValueError("apply_error_start_parameter_not_allowed")
    params[key] = args.get("value")
    component["params"] = params


def _apply_connect_ports(ir_payload: dict, action: dict) -> None:
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    src = str(target.get("from") or args.get("from") or "").strip()
    dst = str(target.get("to") or args.get("to") or "").strip()
    if not src or not dst:
        raise ValueError("apply_error_connection_endpoint_missing")
    connections = ir_payload.get("connections") if isinstance(ir_payload.get("connections"), list) else []
    for row in connections:
        if not isinstance(row, dict):
            continue
        if _normalized_edge(row.get("from"), row.get("to")) == _normalized_edge(src, dst):
            raise ValueError("apply_error_connection_duplicate")
    connections.append({"from": src, "to": dst})
    ir_payload["connections"] = connections


def _apply_disconnect_ports(ir_payload: dict, action: dict) -> None:
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    src = str(target.get("from") or args.get("from") or "").strip()
    dst = str(target.get("to") or args.get("to") or "").strip()
    if not src or not dst:
        raise ValueError("apply_error_connection_endpoint_missing")
    wanted = _normalized_edge(src, dst)
    connections = ir_payload.get("connections") if isinstance(ir_payload.get("connections"), list) else []
    kept: list[dict] = []
    removed = 0
    for row in connections:
        if not isinstance(row, dict):
            continue
        if _normalized_edge(row.get("from"), row.get("to")) == wanted and removed == 0:
            removed = 1
            continue
        kept.append({"from": str(row.get("from") or ""), "to": str(row.get("to") or "")})
    if removed <= 0:
        raise ValueError("apply_error_connection_not_found")
    ir_payload["connections"] = kept


def _apply_replace_component(
    ir_payload: dict,
    action: dict,
    *,
    allowed_component_types: set[str],
) -> None:
    components = ir_payload.get("components") if isinstance(ir_payload.get("components"), list) else []
    index_by_id = _component_index_by_id(ir_payload)
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    args = action.get("args") if isinstance(action.get("args"), dict) else {}
    cid = str(target.get("component_id") or target.get("id") or "").strip()
    idx = index_by_id.get(cid)
    if idx is None:
        raise ValueError("apply_error_component_missing")
    component = components[idx]
    if not isinstance(component, dict):
        raise ValueError("apply_error_component_invalid")
    new_type = str(args.get("new_type") or "").strip()
    if not new_type:
        raise ValueError("apply_error_new_type_missing")
    if allowed_component_types and new_type not in allowed_component_types:
        raise ValueError("apply_error_new_type_not_allowed")

    current_params = component.get("params") if isinstance(component.get("params"), dict) else {}
    allowed_params = allowed_ir_param_names(new_type)
    if allowed_params:
        next_params = {str(k): current_params[k] for k in current_params.keys() if str(k) in allowed_params}
    else:
        next_params = {str(k): current_params[k] for k in current_params.keys()}
    overrides = args.get("param_overrides") if isinstance(args.get("param_overrides"), dict) else {}
    for key, value in overrides.items():
        k = str(key)
        if allowed_params and k not in allowed_params:
            continue
        next_params[k] = value
    component["type"] = new_type
    component["params"] = next_params


def apply_repair_actions_to_ir_v0(
    *,
    ir_payload: dict,
    actions_payload: list[dict],
    max_actions_per_round: int = 3,
    allowed_component_types: list[str] | tuple[str, ...] | None = None,
) -> dict:
    allowed_types = {str(x) for x in (allowed_component_types or DEFAULT_COMPONENT_WHITELIST) if str(x).strip()}
    original_ir = _clone_json(ir_payload if isinstance(ir_payload, dict) else {})
    ok, ir_errors = validate_ir(original_ir, allowed_component_types=sorted(allowed_types))
    if not ok:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "apply_error_code": "input_ir_invalid",
            "errors": ir_errors,
            "rolled_back": True,
            "applied_actions": [],
        }

    action_validation = validate_action_batch_v0(
        actions_payload=actions_payload,
        ir_payload=original_ir,
        max_actions_per_round=max(1, int(max_actions_per_round)),
        allowed_component_types=sorted(allowed_types),
    )
    normalized_actions = action_validation.get("normalized_actions") if isinstance(action_validation.get("normalized_actions"), list) else []
    if action_validation.get("status") != "PASS":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "apply_error_code": "action_batch_invalid",
            "errors": list(action_validation.get("errors") or []),
            "rejected_actions": action_validation.get("rejected_actions") or [],
            "rolled_back": True,
            "applied_actions": [],
        }

    working_ir = _clone_json(original_ir)
    applied_actions: list[dict] = []
    try:
        for action in normalized_actions:
            op = str(action.get("op") or "")
            if op == "set_parameter":
                _apply_set_parameter(working_ir, action)
            elif op == "set_start_value":
                _apply_set_start_value(working_ir, action)
            elif op == "connect_ports":
                _apply_connect_ports(working_ir, action)
            elif op == "disconnect_ports":
                _apply_disconnect_ports(working_ir, action)
            elif op == "replace_component":
                _apply_replace_component(working_ir, action, allowed_component_types=allowed_types)
            else:
                raise ValueError("apply_error_op_not_supported")
            applied_actions.append(_clone_json(action))
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "apply_error_code": str(exc),
            "errors": [str(exc)],
            "rolled_back": True,
            "applied_actions": [],
        }

    ok_after, errors_after = validate_ir(working_ir, allowed_component_types=sorted(allowed_types))
    if not ok_after:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "apply_error_code": "static_validation_failed",
            "errors": errors_after,
            "rolled_back": True,
            "applied_actions": [],
        }

    try:
        modelica_text = ir_to_modelica(working_ir, allowed_component_types=sorted(allowed_types))
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "apply_error_code": "ir_to_modelica_failed",
            "errors": [str(exc)],
            "rolled_back": True,
            "applied_actions": [],
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS",
        "apply_error_code": "",
        "errors": [],
        "rolled_back": False,
        "applied_actions": applied_actions,
        "updated_ir": working_ir,
        "updated_modelica_text": modelica_text,
    }


def apply_repair_actions_to_modelica_v0(
    *,
    modelica_text: str,
    actions_payload: list[dict],
    max_actions_per_round: int = 3,
    allowed_component_types: list[str] | tuple[str, ...] | None = None,
) -> dict:
    try:
        parsed_ir = modelica_to_ir(str(modelica_text or ""))
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "apply_error_code": "modelica_to_ir_failed",
            "errors": [str(exc)],
            "rolled_back": True,
            "applied_actions": [],
        }

    result = apply_repair_actions_to_ir_v0(
        ir_payload=parsed_ir,
        actions_payload=actions_payload,
        max_actions_per_round=max_actions_per_round,
        allowed_component_types=allowed_component_types,
    )
    result["source_ir"] = parsed_ir
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply Modelica repair action batch deterministically")
    parser.add_argument("--modelica-in", required=True)
    parser.add_argument("--actions", required=True, help="JSON list path or payload with `actions` list")
    parser.add_argument("--max-actions-per-round", type=int, default=3)
    parser.add_argument("--modelica-out", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_action_applier_v0/summary.json")
    args = parser.parse_args()

    modelica_text = Path(str(args.modelica_in)).read_text(encoding="utf-8")
    raw_actions = _load_json(str(args.actions))
    if isinstance(raw_actions, dict) and isinstance(raw_actions.get("actions"), list):
        actions_payload = [x for x in raw_actions.get("actions") if isinstance(x, dict)]
    elif isinstance(raw_actions, list):
        actions_payload = [x for x in raw_actions if isinstance(x, dict)]
    else:
        actions_payload = []

    summary = apply_repair_actions_to_modelica_v0(
        modelica_text=modelica_text,
        actions_payload=actions_payload,
        max_actions_per_round=max(1, int(args.max_actions_per_round)),
    )
    summary["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary["sources"] = {"modelica_in": str(args.modelica_in), "actions": str(args.actions)}

    updated_text = str(summary.get("updated_modelica_text") or "")
    if str(args.modelica_out).strip() and summary.get("status") == "PASS":
        Path(str(args.modelica_out)).write_text(updated_text, encoding="utf-8")

    _write_json(str(args.out), summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "apply_error_code": summary.get("apply_error_code"),
                "applied_action_count": len(summary.get("applied_actions") or []),
            }
        )
    )
    if summary.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
