from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_modelica_electrical_msl_semantics_v0 import allowed_ir_param_names, is_valid_port
from .agent_modelica_modeling_ir_v0 import DEFAULT_COMPONENT_WHITELIST


SCHEMA_VERSION = "agent_modelica_repair_action_ir_v0"
ACTION_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
COMPONENT_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FIELD_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ENDPOINT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")

ALLOWED_OPS = {
    "set_parameter",
    "set_start_value",
    "connect_ports",
    "disconnect_ports",
    "replace_component",
}
ALLOWED_SOURCES = {"rule", "llm"}


def _to_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except Exception:
        return float(default)


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _component_maps(ir_payload: dict) -> tuple[dict[str, dict], dict[str, str]]:
    components = ir_payload.get("components") if isinstance(ir_payload.get("components"), list) else []
    by_id: dict[str, dict] = {}
    type_by_id: dict[str, str] = {}
    for row in components:
        if not isinstance(row, dict):
            continue
        cid = str(row.get("id") or "").strip()
        ctype = str(row.get("type") or "").strip()
        if not cid:
            continue
        by_id[cid] = row
        type_by_id[cid] = ctype
    return by_id, type_by_id


def _parse_endpoint(endpoint: str) -> tuple[str, str] | None:
    text = str(endpoint or "").strip()
    if not ENDPOINT_RE.match(text):
        return None
    comp_id, port = text.split(".", 1)
    return comp_id, port


def _validate_endpoint(
    endpoint: str,
    *,
    component_type_by_id: dict[str, str],
) -> str:
    parsed = _parse_endpoint(endpoint)
    if parsed is None:
        return "endpoint_invalid"
    comp_id, port = parsed
    ctype = str(component_type_by_id.get(comp_id) or "")
    if not ctype:
        return "endpoint_component_missing"
    if not is_valid_port(ctype, port):
        return "endpoint_port_invalid"
    return ""


def _normalize_action_shape(action: dict) -> dict:
    payload = action if isinstance(action, dict) else {}
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
    return {
        "action_id": str(payload.get("action_id") or "").strip(),
        "op": str(payload.get("op") or "").strip().lower(),
        "target": {str(k): target[k] for k in sorted(target.keys()) if FIELD_KEY_RE.match(str(k))},
        "args": {str(k): args[k] for k in sorted(args.keys()) if FIELD_KEY_RE.match(str(k))},
        "reason_tag": str(payload.get("reason_tag") or "").strip(),
        "source": str(payload.get("source") or "").strip().lower(),
        "confidence": round(max(0.0, min(1.0, _to_float(payload.get("confidence"), 0.0))), 4),
    }


def _validate_common_fields(action: dict) -> list[str]:
    errors: list[str] = []
    action_id = str(action.get("action_id") or "")
    op = str(action.get("op") or "")
    reason_tag = str(action.get("reason_tag") or "")
    source = str(action.get("source") or "")
    confidence = action.get("confidence")
    target = action.get("target")
    args = action.get("args")

    if not ACTION_ID_RE.match(action_id):
        errors.append("action_id_invalid")
    if op not in ALLOWED_OPS:
        errors.append("op_not_allowed")
    if not reason_tag:
        errors.append("reason_tag_missing")
    if source not in ALLOWED_SOURCES:
        errors.append("source_invalid")
    if not isinstance(target, dict):
        errors.append("target_missing")
    if not isinstance(args, dict):
        errors.append("args_missing")
    if not isinstance(confidence, (int, float)):
        errors.append("confidence_invalid")
    return errors


def _validate_action_by_op(
    action: dict,
    *,
    component_type_by_id: dict[str, str],
    allowed_component_types: set[str],
) -> list[str]:
    errors: list[str] = []
    op = str(action.get("op") or "")
    target = action.get("target") if isinstance(action.get("target"), dict) else {}
    args = action.get("args") if isinstance(action.get("args"), dict) else {}

    def _component_id() -> str:
        return str(target.get("component_id") or target.get("id") or "").strip()

    if op in {"set_parameter", "set_start_value", "replace_component"}:
        cid = _component_id()
        if not COMPONENT_ID_RE.match(cid):
            errors.append("target_component_id_invalid")
            return errors
        ctype = str(component_type_by_id.get(cid) or "")
        if not ctype:
            errors.append("target_component_missing")
            return errors
        if allowed_component_types and ctype not in allowed_component_types:
            errors.append("target_component_type_not_allowed")
            return errors

    if op == "set_parameter":
        cid = _component_id()
        ctype = str(component_type_by_id.get(cid) or "")
        param = str(target.get("parameter") or target.get("param") or "").strip()
        if not FIELD_KEY_RE.match(param):
            errors.append("target_parameter_invalid")
        allowed_params = allowed_ir_param_names(ctype)
        if allowed_params and param not in allowed_params:
            errors.append("target_parameter_not_allowed")
        if "value" not in args:
            errors.append("args_value_missing")
    elif op == "set_start_value":
        cid = _component_id()
        ctype = str(component_type_by_id.get(cid) or "")
        variable = str(target.get("variable") or target.get("parameter") or target.get("param") or "").strip()
        if not FIELD_KEY_RE.match(variable):
            errors.append("target_variable_invalid")
        if "value" not in args:
            errors.append("args_value_missing")
        # If a concrete parameter is provided, enforce whitelist.
        allowed_params = allowed_ir_param_names(ctype)
        if allowed_params and variable in {"parameter", "param"}:
            param_name = str(target.get("parameter") or target.get("param") or "").strip()
            if param_name and param_name not in allowed_params:
                errors.append("target_parameter_not_allowed")
    elif op in {"connect_ports", "disconnect_ports"}:
        src = str(target.get("from") or args.get("from") or "").strip()
        dst = str(target.get("to") or args.get("to") or "").strip()
        if not src or not dst:
            errors.append("connection_endpoint_missing")
        src_err = _validate_endpoint(src, component_type_by_id=component_type_by_id) if src else "endpoint_invalid"
        dst_err = _validate_endpoint(dst, component_type_by_id=component_type_by_id) if dst else "endpoint_invalid"
        if src_err:
            errors.append(f"from_{src_err}")
        if dst_err:
            errors.append(f"to_{dst_err}")
        if src and dst and src == dst:
            errors.append("connection_self_loop_invalid")
    elif op == "replace_component":
        new_type = str(args.get("new_type") or "").strip()
        if not new_type:
            errors.append("args_new_type_missing")
        elif allowed_component_types and new_type not in allowed_component_types:
            errors.append("args_new_type_not_allowed")
    return errors


def validate_action_batch_v0(
    *,
    actions_payload: list[dict],
    ir_payload: dict,
    max_actions_per_round: int = 3,
    allowed_component_types: list[str] | tuple[str, ...] | None = None,
) -> dict:
    allowed_types = {str(x) for x in (allowed_component_types or DEFAULT_COMPONENT_WHITELIST) if str(x).strip()}
    component_by_id, component_type_by_id = _component_maps(ir_payload if isinstance(ir_payload, dict) else {})

    normalized: list[dict] = []
    rejected: list[dict] = []
    errors: list[str] = []
    seen_ids: set[str] = set()

    if not isinstance(actions_payload, list):
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "FAIL",
            "normalized_actions": [],
            "rejected_actions": [{"index": 0, "reason": "actions_payload_not_list"}],
            "errors": ["actions_payload_not_list"],
            "max_actions_per_round": int(max(1, max_actions_per_round)),
        }

    if len(actions_payload) > int(max(1, max_actions_per_round)):
        errors.append("max_actions_per_round_exceeded")

    for idx, row in enumerate(actions_payload):
        if not isinstance(row, dict):
            rejected.append({"index": idx, "reason": "action_not_object"})
            continue
        action = _normalize_action_shape(row)
        item_errors = _validate_common_fields(action)
        if action["action_id"] in seen_ids:
            item_errors.append("action_id_duplicate")
        seen_ids.add(action["action_id"])
        item_errors.extend(
            _validate_action_by_op(
                action,
                component_type_by_id=component_type_by_id,
                allowed_component_types=allowed_types,
            )
        )
        if item_errors:
            rejected.append({"index": idx, "action_id": action.get("action_id"), "errors": sorted(set(item_errors))})
            continue
        normalized.append(action)

    if not component_by_id:
        errors.append("ir_components_missing")
    status = "PASS" if not errors and not rejected else "FAIL"
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "normalized_actions": normalized,
        "rejected_actions": rejected,
        "errors": sorted(set(errors)),
        "max_actions_per_round": int(max(1, max_actions_per_round)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate GateForge Modelica repair action IR v0")
    parser.add_argument("--actions", required=True, help="Path to JSON list of actions")
    parser.add_argument("--ir", required=True, help="Path to modeling_ir_v0 payload")
    parser.add_argument("--max-actions-per-round", type=int, default=3)
    parser.add_argument("--out", default="artifacts/agent_modelica_repair_action_ir_v0/summary.json")
    args = parser.parse_args()

    actions_path = str(args.actions or "")
    actions_payload: list[dict] = []
    raw_actions = _load_json(actions_path)
    if isinstance(raw_actions, dict) and isinstance(raw_actions.get("actions"), list):
        actions_payload = [x for x in raw_actions.get("actions", []) if isinstance(x, dict)]
    elif isinstance(raw_actions, list):
        actions_payload = [x for x in raw_actions if isinstance(x, dict)]
    ir_payload = _load_json(str(args.ir))
    summary = validate_action_batch_v0(
        actions_payload=actions_payload,
        ir_payload=ir_payload,
        max_actions_per_round=max(1, int(args.max_actions_per_round)),
    )
    summary["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    summary["sources"] = {"actions": actions_path, "ir": str(args.ir)}
    _write_json(args.out, summary)
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "normalized_action_count": len(summary.get("normalized_actions") or []),
                "rejected_action_count": len(summary.get("rejected_actions") or []),
            }
        )
    )
    if summary.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
