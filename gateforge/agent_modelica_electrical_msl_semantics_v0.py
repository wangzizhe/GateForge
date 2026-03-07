from __future__ import annotations

from typing import Any


SINE_VOLTAGE_TYPE = "Modelica.Electrical.Analog.Sources.SineVoltage"

# Canonical IR parameter names per component type.
IR_PARAM_KEYS_BY_COMPONENT_TYPE: dict[str, set[str]] = {
    "Modelica.Electrical.Analog.Basic.Resistor": {"R"},
    "Modelica.Electrical.Analog.Basic.Capacitor": {"C"},
    "Modelica.Electrical.Analog.Basic.Inductor": {"L"},
    "Modelica.Electrical.Analog.Basic.Ground": set(),
    "Modelica.Electrical.Analog.Sources.ConstantVoltage": {"V"},
    "Modelica.Electrical.Analog.Sources.StepVoltage": {"V", "startTime"},
    SINE_VOLTAGE_TYPE: {"V", "freqHz"},
    "Modelica.Electrical.Analog.Sensors.VoltageSensor": set(),
    "Modelica.Electrical.Analog.Sensors.CurrentSensor": set(),
}

# IR param aliases accepted in validation and normalized for model emission.
IR_PARAM_ALIAS_TO_CANONICAL_BY_COMPONENT_TYPE: dict[str, dict[str, str]] = {
    SINE_VOLTAGE_TYPE: {
        "freqHz": "freqHz",
        "f": "freqHz",
        "frequency": "freqHz",
        "V": "V",
    }
}

# Canonical IR param -> Modelica emitted param name.
IR_TO_MODELICA_PARAM_BY_COMPONENT_TYPE: dict[str, dict[str, str]] = {
    SINE_VOLTAGE_TYPE: {
        "freqHz": "f",
        "V": "V",
    }
}

# Modelica parsed param -> canonical IR param.
MODELICA_TO_IR_PARAM_BY_COMPONENT_TYPE: dict[str, dict[str, str]] = {
    SINE_VOLTAGE_TYPE: {
        "f": "freqHz",
        "freqHz": "freqHz",
        "frequency": "freqHz",
        "V": "V",
    }
}

PORT_SIGNATURES_BY_COMPONENT_TYPE: dict[str, set[str]] = {
    "Modelica.Electrical.Analog.Basic.Resistor": {"p", "n"},
    "Modelica.Electrical.Analog.Basic.Capacitor": {"p", "n"},
    "Modelica.Electrical.Analog.Basic.Inductor": {"p", "n"},
    "Modelica.Electrical.Analog.Basic.Ground": {"p"},
    "Modelica.Electrical.Analog.Sources.ConstantVoltage": {"p", "n"},
    "Modelica.Electrical.Analog.Sources.StepVoltage": {"p", "n"},
    SINE_VOLTAGE_TYPE: {"p", "n"},
    "Modelica.Electrical.Analog.Sensors.VoltageSensor": {"p", "n"},
    "Modelica.Electrical.Analog.Sensors.CurrentSensor": {"p", "n"},
}


def allowed_ir_param_names(component_type: str) -> set[str]:
    ctype = str(component_type or "")
    canonical = set(IR_PARAM_KEYS_BY_COMPONENT_TYPE.get(ctype, set()))
    alias_map = IR_PARAM_ALIAS_TO_CANONICAL_BY_COMPONENT_TYPE.get(ctype, {})
    return canonical.union(set(alias_map.keys()))


def normalize_ir_params_for_validation(component_type: str, params: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    ctype = str(component_type or "")
    alias_map = IR_PARAM_ALIAS_TO_CANONICAL_BY_COMPONENT_TYPE.get(ctype, {})
    normalized: dict[str, Any] = {}
    errors: list[str] = []
    for raw_key, value in params.items():
        key = str(raw_key or "")
        canonical = alias_map.get(key, key)
        if canonical in normalized and normalized[canonical] != value:
            errors.append(f"param_alias_conflict:{key}->{canonical}")
            continue
        normalized[canonical] = value
    return normalized, errors


def normalize_ir_params_for_modelica_emit(component_type: str, params: dict[str, Any]) -> dict[str, Any]:
    ctype = str(component_type or "")
    normalized, _ = normalize_ir_params_for_validation(ctype, params)
    mapping = IR_TO_MODELICA_PARAM_BY_COMPONENT_TYPE.get(ctype, {})
    out: dict[str, Any] = {}
    for key, value in normalized.items():
        out[mapping.get(key, key)] = value
    return out


def normalize_modelica_params_for_ir(component_type: str, params: dict[str, Any]) -> dict[str, Any]:
    ctype = str(component_type or "")
    mapping = MODELICA_TO_IR_PARAM_BY_COMPONENT_TYPE.get(ctype, {})
    out: dict[str, Any] = {}
    for key, value in params.items():
        canonical = mapping.get(str(key), str(key))
        if canonical in out and out[canonical] != value:
            # Keep first occurrence to make normalization stable.
            continue
        out[canonical] = value
    return out


def is_valid_port(component_type: str, port: str) -> bool:
    ctype = str(component_type or "")
    pname = str(port or "")
    allowed = PORT_SIGNATURES_BY_COMPONENT_TYPE.get(ctype)
    if not isinstance(allowed, set):
        return True
    return pname in allowed
