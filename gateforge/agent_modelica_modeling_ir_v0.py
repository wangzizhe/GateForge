from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .agent_modelica_electrical_msl_semantics_v0 import (
    allowed_ir_param_names,
    is_valid_port,
    normalize_ir_params_for_modelica_emit,
    normalize_ir_params_for_validation,
    normalize_modelica_params_for_ir,
)


SCHEMA_VERSION = "modeling_ir_v0"
MODEL_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COMPONENT_ID_RE = MODEL_NAME_RE
ENDPOINT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")

DEFAULT_COMPONENT_WHITELIST = (
    "Modelica.Electrical.Analog.Basic.Resistor",
    "Modelica.Electrical.Analog.Basic.Capacitor",
    "Modelica.Electrical.Analog.Basic.Inductor",
    "Modelica.Electrical.Analog.Basic.Ground",
    "Modelica.Electrical.Analog.Sources.ConstantVoltage",
    "Modelica.Electrical.Analog.Sources.StepVoltage",
    "Modelica.Electrical.Analog.Sources.SineVoltage",
    "Modelica.Electrical.Analog.Sensors.VoltageSensor",
    "Modelica.Electrical.Analog.Sensors.CurrentSensor",
)


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except Exception:
        return None


def _to_int(value: Any) -> int | None:
    try:
        return int(value)
    except Exception:
        return None


def _json_scalar(value: Any) -> bool:
    return isinstance(value, (bool, int, float, str))


def _parse_endpoint(endpoint: str) -> tuple[str, str] | None:
    text = str(endpoint or "").strip()
    if not ENDPOINT_RE.match(text):
        return None
    comp_id, port = text.split(".", 1)
    return comp_id, port


def _normalize_param_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return float(value)
    return str(value)


def _default_structural_balance(payload: dict) -> dict:
    components = payload.get("components") if isinstance(payload.get("components"), list) else []
    count = max(1, len([x for x in components if isinstance(x, dict)]))
    return {"variable_count": count, "equation_count": count}


def _extract_structural_balance(payload: dict) -> tuple[int | None, int | None]:
    structural = payload.get("structural_balance") if isinstance(payload.get("structural_balance"), dict) else {}
    return _to_int(structural.get("variable_count")), _to_int(structural.get("equation_count"))


def validate_ir(
    ir: dict,
    *,
    allowed_component_types: list[str] | tuple[str, ...] | None = None,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    payload = ir if isinstance(ir, dict) else {}
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version_invalid")

    model_name = str(payload.get("model_name") or "")
    if not MODEL_NAME_RE.match(model_name):
        errors.append("model_name_invalid")

    components = payload.get("components")
    if not isinstance(components, list) or not components:
        errors.append("components_missing")
        components = []

    allowed = {str(x) for x in (allowed_component_types or []) if str(x).strip()}
    ids: set[str] = set()
    component_type_by_id: dict[str, str] = {}
    for idx, component in enumerate(components):
        if not isinstance(component, dict):
            errors.append(f"component_not_object:{idx}")
            continue
        cid = str(component.get("id") or "")
        ctype = str(component.get("type") or "")
        params = component.get("params")

        if not COMPONENT_ID_RE.match(cid):
            errors.append(f"component_id_invalid:{idx}")
        if cid in ids:
            errors.append(f"component_id_duplicate:{cid}")
        ids.add(cid)
        component_type_by_id[cid] = ctype

        if not ctype:
            errors.append(f"component_type_missing:{cid or idx}")
        elif allowed and ctype not in allowed:
            errors.append(f"component_type_not_allowed:{ctype}")

        if not isinstance(params, dict):
            errors.append(f"component_params_invalid:{cid or idx}")
            continue
        normalized_params, normalize_errors = normalize_ir_params_for_validation(ctype, params)
        for row in normalize_errors:
            errors.append(f"{row}:{cid or idx}")
        allowed_param_names = allowed_ir_param_names(ctype)
        for key, value in params.items():
            if not MODEL_NAME_RE.match(str(key or "")):
                errors.append(f"param_key_invalid:{cid}:{key}")
            elif allowed_param_names and str(key) not in allowed_param_names:
                errors.append(f"param_key_not_allowed:{cid}:{key}")
            if not _json_scalar(value):
                errors.append(f"param_value_invalid:{cid}:{key}")
        for key in normalized_params.keys():
            if not MODEL_NAME_RE.match(str(key or "")):
                errors.append(f"param_key_invalid:{cid}:{key}")

    connections = payload.get("connections")
    if not isinstance(connections, list):
        errors.append("connections_missing")
        connections = []
    normalized_edges: set[tuple[str, str]] = set()
    for idx, row in enumerate(connections):
        if not isinstance(row, dict):
            errors.append(f"connection_not_object:{idx}")
            continue
        src = str(row.get("from") or "")
        dst = str(row.get("to") or "")
        src_ep = _parse_endpoint(src)
        dst_ep = _parse_endpoint(dst)
        if src_ep is None:
            errors.append(f"connection_from_invalid:{idx}")
        if dst_ep is None:
            errors.append(f"connection_to_invalid:{idx}")
        if src_ep and src_ep[0] not in ids:
            errors.append(f"connection_from_component_missing:{src_ep[0]}")
        if dst_ep and dst_ep[0] not in ids:
            errors.append(f"connection_to_component_missing:{dst_ep[0]}")
        if src_ep and src_ep[0] in component_type_by_id:
            if not is_valid_port(component_type_by_id[src_ep[0]], src_ep[1]):
                errors.append(f"connection_from_port_invalid:{src_ep[0]}.{src_ep[1]}")
        if dst_ep and dst_ep[0] in component_type_by_id:
            if not is_valid_port(component_type_by_id[dst_ep[0]], dst_ep[1]):
                errors.append(f"connection_to_port_invalid:{dst_ep[0]}.{dst_ep[1]}")
        if src_ep and dst_ep:
            edge = tuple(sorted([f"{src_ep[0]}.{src_ep[1]}", f"{dst_ep[0]}.{dst_ep[1]}"]))
            if edge in normalized_edges:
                errors.append(f"connection_duplicate:{edge[0]}|{edge[1]}")
            normalized_edges.add(edge)

    var_count, eq_count = _extract_structural_balance(payload)
    if var_count is None or var_count <= 0:
        errors.append("structural_balance_variable_count_invalid")
    if eq_count is None or eq_count <= 0:
        errors.append("structural_balance_equation_count_invalid")
    if isinstance(var_count, int) and isinstance(eq_count, int) and var_count != eq_count:
        errors.append("structural_balance_not_square")

    simulation = payload.get("simulation")
    if not isinstance(simulation, dict):
        errors.append("simulation_missing")
        simulation = {}
    start_time = _to_float(simulation.get("start_time"))
    stop_time = _to_float(simulation.get("stop_time"))
    number_of_intervals = _to_int(simulation.get("number_of_intervals"))
    tolerance = _to_float(simulation.get("tolerance"))
    method = str(simulation.get("method") or "")
    if start_time is None:
        errors.append("simulation_start_time_invalid")
    if stop_time is None or stop_time <= 0.0:
        errors.append("simulation_stop_time_invalid")
    if start_time is not None and stop_time is not None and stop_time <= start_time:
        errors.append("simulation_time_window_invalid")
    if number_of_intervals is None or number_of_intervals <= 0:
        errors.append("simulation_number_of_intervals_invalid")
    if tolerance is None or tolerance <= 0.0:
        errors.append("simulation_tolerance_invalid")
    if not method:
        errors.append("simulation_method_invalid")

    targets = payload.get("validation_targets")
    if not isinstance(targets, list):
        errors.append("validation_targets_missing")
        targets = []
    for idx, target in enumerate(targets):
        parsed = _parse_endpoint(str(target or ""))
        if parsed is None:
            errors.append(f"validation_target_invalid:{idx}")
        elif parsed[0] not in ids:
            errors.append(f"validation_target_component_missing:{parsed[0]}")

    return len(errors) == 0, errors


def _format_modelica_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=True)


def _param_block(params: dict[str, Any]) -> str:
    if not params:
        return ""
    items = [f"{key}={_format_modelica_value(params[key])}" for key in sorted(params.keys())]
    return "(" + ", ".join(items) + ")"


def ir_to_modelica(
    ir: dict,
    *,
    allowed_component_types: list[str] | tuple[str, ...] | None = None,
) -> str:
    ok, errors = validate_ir(ir, allowed_component_types=allowed_component_types)
    if not ok:
        raise ValueError("invalid_ir:" + ",".join(errors))

    model_name = str(ir.get("model_name"))
    components = ir.get("components") or []
    connections = ir.get("connections") or []
    sim = ir.get("simulation") or {}
    targets = [str(x) for x in (ir.get("validation_targets") or []) if str(x).strip()]
    structural = ir.get("structural_balance") if isinstance(ir.get("structural_balance"), dict) else _default_structural_balance(ir)
    var_count = _to_int(structural.get("variable_count"))
    eq_count = _to_int(structural.get("equation_count"))

    lines = [f"model {model_name}"]
    if isinstance(var_count, int) and isinstance(eq_count, int):
        lines.append(f"  // gateforge_structural_balance: variables={var_count}, equations={eq_count}")
    if targets:
        lines.append(f"  // gateforge_validation_targets: {', '.join(targets)}")
    for component in components:
        ctype = str(component.get("type"))
        cid = str(component.get("id"))
        params = component.get("params") if isinstance(component.get("params"), dict) else {}
        params = normalize_ir_params_for_modelica_emit(ctype, params)
        lines.append(f"  {ctype} {cid}{_param_block(params)};")
    lines.append("equation")
    for row in connections:
        src = str(row.get("from"))
        dst = str(row.get("to"))
        lines.append(f"  connect({src}, {dst});")
    lines.append(
        "  annotation(experiment(StartTime="
        + str(sim.get("start_time"))
        + ", StopTime="
        + str(sim.get("stop_time"))
        + ", NumberOfIntervals="
        + str(sim.get("number_of_intervals"))
        + ", Tolerance="
        + str(sim.get("tolerance"))
        + ", __Dymola_Algorithm="
        + json.dumps(str(sim.get("method") or ""), ensure_ascii=True)
        + "));"
    )
    lines.append(f"end {model_name};")
    return "\n".join(lines) + "\n"


def _parse_param_value(text: str) -> Any:
    raw = str(text or "").strip()
    if not raw:
        return ""
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if raw.startswith('"') and raw.endswith('"'):
        try:
            return json.loads(raw)
        except Exception:
            return raw.strip('"')
    if re.match(r"^-?[0-9]+$", raw):
        try:
            return int(raw)
        except Exception:
            return raw
    if re.match(r"^-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$", raw):
        try:
            return float(raw)
        except Exception:
            return raw
    return raw


def _parse_params(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    out: dict[str, Any] = {}
    for part in [x.strip() for x in text.split(",") if x.strip()]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if not MODEL_NAME_RE.match(key):
            continue
        out[key] = _parse_param_value(value)
    return out


def _extract_validation_targets(text: str) -> list[str]:
    m = re.search(r"(?im)^\s*//\s*gateforge_validation_targets\s*:\s*(.+)\s*$", text)
    if not m:
        return []
    rows = [x.strip() for x in str(m.group(1) or "").split(",") if x.strip()]
    return rows


def _extract_structural_balance_comment(text: str) -> dict:
    m = re.search(
        r"(?im)^\s*//\s*gateforge_structural_balance\s*:\s*variables\s*=\s*([0-9]+)\s*,\s*equations\s*=\s*([0-9]+)\s*$",
        text,
    )
    if not m:
        return {}
    var_count = _to_int(m.group(1))
    eq_count = _to_int(m.group(2))
    if var_count is None or eq_count is None:
        return {}
    return {"variable_count": var_count, "equation_count": eq_count}


def _extract_parenthesized_argument(text: str, keyword: str) -> str:
    pattern = re.compile(rf"{re.escape(keyword)}\s*\(", flags=re.IGNORECASE)
    m = pattern.search(text)
    if not m:
        return ""
    start = text.find("(", int(m.start()))
    if start < 0:
        return ""
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i]
        i += 1
    return ""


def _extract_simulation(text: str) -> dict[str, Any]:
    defaults = {
        "start_time": 0.0,
        "stop_time": 1.0,
        "number_of_intervals": 500,
        "tolerance": 1e-6,
        "method": "dassl",
    }
    experiment_args = _extract_parenthesized_argument(text, "experiment")
    if not experiment_args:
        return defaults
    params = _parse_params(experiment_args)
    return {
        "start_time": _to_float(params.get("StartTime")) if _to_float(params.get("StartTime")) is not None else defaults["start_time"],
        "stop_time": _to_float(params.get("StopTime")) if _to_float(params.get("StopTime")) is not None else defaults["stop_time"],
        "number_of_intervals": _to_int(params.get("NumberOfIntervals")) if _to_int(params.get("NumberOfIntervals")) is not None else defaults["number_of_intervals"],
        "tolerance": _to_float(params.get("Tolerance")) if _to_float(params.get("Tolerance")) is not None else defaults["tolerance"],
        "method": str(params.get("__Dymola_Algorithm") or params.get("Method") or defaults["method"]),
    }


def modelica_to_ir(text: str) -> dict:
    model_match = re.search(r"(?im)^\s*(?:partial\s+)?model\s+([A-Za-z_][A-Za-z0-9_]*)\b", text)
    if not model_match:
        raise ValueError("model_block_missing")
    model_name = str(model_match.group(1))
    end_match = re.search(rf"(?im)^\s*end\s+{re.escape(model_name)}\s*;", text)
    if not end_match:
        raise ValueError("model_end_missing")
    body = text[int(model_match.end()) : int(end_match.start())]
    eq_match = re.search(r"(?im)^\s*equation\b", body)
    decl_text = body if not eq_match else body[: int(eq_match.start())]
    eq_text = "" if not eq_match else body[int(eq_match.end()) :]

    component_re = re.compile(
        r"^\s*([A-Za-z_][A-Za-z0-9_\.]*)\s+([A-Za-z_][A-Za-z0-9_]*)(?:\(([^)]*)\))?\s*;\s*$",
        flags=re.MULTILINE,
    )
    components: list[dict] = []
    for match in component_re.finditer(decl_text):
        ctype = str(match.group(1))
        cid = str(match.group(2))
        params = _parse_params(str(match.group(3) or ""))
        params = normalize_modelica_params_for_ir(ctype, params)
        components.append({"id": cid, "type": ctype, "params": params})

    connect_re = re.compile(
        r"connect\(\s*([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*;",
        flags=re.MULTILINE,
    )
    connections: list[dict] = []
    for match in connect_re.finditer(eq_text):
        connections.append({"from": str(match.group(1)), "to": str(match.group(2))})

    structural_balance = _extract_structural_balance_comment(text)
    if not structural_balance:
        inferred = max(1, len(components))
        structural_balance = {"variable_count": inferred, "equation_count": inferred}

    payload = {
        "schema_version": SCHEMA_VERSION,
        "model_name": model_name,
        "source_meta": {},
        "components": components,
        "connections": connections,
        "structural_balance": structural_balance,
        "simulation": _extract_simulation(text),
        "validation_targets": _extract_validation_targets(text),
    }
    return payload


def normalize_ir(ir: dict, *, ignore_source_meta: bool = True) -> dict:
    payload = ir if isinstance(ir, dict) else {}
    components = payload.get("components") if isinstance(payload.get("components"), list) else []
    normalized_components = []
    for row in components:
        if not isinstance(row, dict):
            continue
        params = row.get("params") if isinstance(row.get("params"), dict) else {}
        normalized_components.append(
            {
                "id": str(row.get("id") or ""),
                "type": str(row.get("type") or ""),
                "params": {str(k): _normalize_param_value(v) for k, v in sorted(params.items())},
            }
        )
    normalized_components.sort(key=lambda x: (x["id"], x["type"]))

    connections = payload.get("connections") if isinstance(payload.get("connections"), list) else []
    normalized_connections = []
    for row in connections:
        if not isinstance(row, dict):
            continue
        normalized_connections.append({"from": str(row.get("from") or ""), "to": str(row.get("to") or "")})
    normalized_connections.sort(key=lambda x: (x["from"], x["to"]))

    targets = payload.get("validation_targets") if isinstance(payload.get("validation_targets"), list) else []
    normalized_targets = sorted([str(x) for x in targets if str(x).strip()])

    simulation = payload.get("simulation") if isinstance(payload.get("simulation"), dict) else {}
    normalized_sim = {
        "start_time": _to_float(simulation.get("start_time")),
        "stop_time": _to_float(simulation.get("stop_time")),
        "number_of_intervals": _to_int(simulation.get("number_of_intervals")),
        "tolerance": _to_float(simulation.get("tolerance")),
        "method": str(simulation.get("method") or ""),
    }
    var_count, eq_count = _extract_structural_balance(payload)
    normalized_structural = {"variable_count": var_count, "equation_count": eq_count}

    out = {
        "schema_version": SCHEMA_VERSION,
        "model_name": str(payload.get("model_name") or ""),
        "components": normalized_components,
        "connections": normalized_connections,
        "structural_balance": normalized_structural,
        "simulation": normalized_sim,
        "validation_targets": normalized_targets,
    }
    if not ignore_source_meta:
        source_meta = payload.get("source_meta") if isinstance(payload.get("source_meta"), dict) else {}
        out["source_meta"] = {str(k): source_meta[k] for k in sorted(source_meta.keys())}
    return out


def compare_ir_roundtrip(src_ir: dict, parsed_ir: dict, *, ignore_source_meta: bool = True) -> dict:
    src = normalize_ir(src_ir, ignore_source_meta=ignore_source_meta)
    parsed = normalize_ir(parsed_ir, ignore_source_meta=ignore_source_meta)
    match = src == parsed
    diff_keys: list[str] = []
    for key in sorted(set(src.keys()) | set(parsed.keys())):
        if src.get(key) != parsed.get(key):
            diff_keys.append(key)
    return {"match": match, "diff_keys": diff_keys, "source_normalized": src, "parsed_normalized": parsed}


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Modeling IR v0",
        "",
        f"- status: `{payload.get('status')}`",
        f"- mode: `{payload.get('mode')}`",
        f"- model_name: `{payload.get('model_name')}`",
        f"- roundtrip_match: `{payload.get('roundtrip_match')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="GateForge Modeling IR v0 helper")
    parser.add_argument("--ir", default="")
    parser.add_argument("--modelica-in", default="")
    parser.add_argument("--modelica-out", default="")
    parser.add_argument("--ir-out", default="")
    parser.add_argument("--out", default="artifacts/agent_modelica_modeling_ir_v0/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    if not str(args.ir).strip() and not str(args.modelica_in).strip():
        raise SystemExit("--ir or --modelica-in is required")

    mode = "ir_to_modelica"
    source_ir: dict = {}
    modelica_text = ""
    parsed_ir: dict = {}

    if str(args.ir).strip():
        source_ir = _load_json(args.ir)
        ok, errors = validate_ir(source_ir, allowed_component_types=DEFAULT_COMPONENT_WHITELIST)
        if not ok:
            _write_json(
                args.out,
                {
                    "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                    "status": "FAIL",
                    "mode": "ir_to_modelica",
                    "errors": errors,
                },
            )
            raise SystemExit(1)
        modelica_text = ir_to_modelica(source_ir, allowed_component_types=DEFAULT_COMPONENT_WHITELIST)
        if str(args.modelica_out).strip():
            _write_text(args.modelica_out, modelica_text)
        parsed_ir = modelica_to_ir(modelica_text)
    else:
        mode = "modelica_to_ir"
        modelica_text = Path(args.modelica_in).read_text(encoding="utf-8")
        parsed_ir = modelica_to_ir(modelica_text)
        source_ir = parsed_ir

    if str(args.ir_out).strip():
        _write_json(args.ir_out, parsed_ir)

    cmp = compare_ir_roundtrip(source_ir, parsed_ir, ignore_source_meta=True)
    status = "PASS" if bool(cmp.get("match")) else "NEEDS_REVIEW"
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "mode": mode,
        "model_name": str(source_ir.get("model_name") or ""),
        "roundtrip_match": bool(cmp.get("match")),
        "diff_keys": cmp.get("diff_keys") or [],
        "out_paths": {
            "modelica_out": str(args.modelica_out or ""),
            "ir_out": str(args.ir_out or ""),
        },
    }
    _write_json(args.out, summary)
    _write_markdown(args.report_out or _default_md_path(args.out), summary)
    print(json.dumps({"status": status, "mode": mode, "roundtrip_match": bool(cmp.get("match"))}))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
