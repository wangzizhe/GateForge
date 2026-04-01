from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_dual_layer_mutation_v0_3_6 import (
    build_dual_layer_multi_param_task,
)


SCHEMA_VERSION = "agent_modelica_post_restore_taskset_v0_3_6"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_post_restore_taskset_v0_3_6"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


CANDIDATE_SPECS: list[dict[str, str]] = [
    {
        "task_id": "v036_rc_dual_collapse",
        "model_name": "V036TwoParamRC",
        "operator": "paired_value_collapse",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_rc_dual_collapse.mo",
        "model_text": """\
model V036TwoParamRC
  parameter Real R = 100.0;
  parameter Real C = 0.001;
  Real v(start = 1.0);
equation
  R * C * der(v) = -v;
end V036TwoParamRC;""",
    },
    {
        "task_id": "v036_msd_dual_collapse",
        "model_name": "V036MassSpringDamper",
        "operator": "paired_value_collapse",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_msd_dual_collapse.mo",
        "model_text": """\
model V036MassSpringDamper
  parameter Real m = 2.0;
  parameter Real d = 0.5;
  parameter Real k = 10.0;
  Real x(start = 1.0);
  Real v(start = 0.0);
equation
  der(x) = v;
  m * der(v) = -k * x - d * v;
end V036MassSpringDamper;""",
    },
    {
        "task_id": "v036_rlc_dual_collapse",
        "model_name": "V036RLC",
        "operator": "paired_value_collapse",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_rlc_dual_collapse.mo",
        "model_text": """\
model V036RLC
  parameter Real R = 20.0;
  parameter Real L = 0.1;
  parameter Real C = 0.001;
  Real i(start = 0.0);
  Real v_c(start = 1.0);
equation
  L * der(i) = 5.0 - R * i - v_c;
  C * der(v_c) = i;
end V036RLC;""",
    },
    {
        "task_id": "v036_tank_dual_collapse",
        "model_name": "V036Tank",
        "operator": "paired_value_collapse",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_tank_dual_collapse.mo",
        "model_text": """\
model V036Tank
  parameter Real A = 1.0;
  parameter Real c = 0.5;
  parameter Real Qin = 0.3;
  Real h(start = 2.0);
equation
  A * der(h) = Qin - c * sqrt(max(h, 0.0));
end V036Tank;""",
    },
    {
        "task_id": "v036_thermal_bias_shift",
        "model_name": "V036ThermalNode",
        "operator": "paired_value_bias_shift",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_thermal_bias_shift.mo",
        "model_text": """\
model V036ThermalNode
  parameter Real Cth = 500.0;
  parameter Real h = 10.0;
  parameter Real Tenv = 20.0;
  Real T(start = 80.0);
equation
  Cth * der(T) = -h * (T - Tenv);
end V036ThermalNode;""",
    },
    {
        "task_id": "v036_lag_bias_shift",
        "model_name": "V036Lag",
        "operator": "paired_value_bias_shift",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_lag_bias_shift.mo",
        "model_text": """\
model V036Lag
  parameter Real K = 2.0;
  parameter Real T = 1.5;
  Real y(start = 0.0);
equation
  T * der(y) = K - y;
end V036Lag;""",
    },
    {
        "task_id": "v036_oscillator_bias_shift",
        "model_name": "V036Oscillator",
        "operator": "paired_value_bias_shift",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_oscillator_bias_shift.mo",
        "model_text": """\
model V036Oscillator
  parameter Real omega = 3.0;
  parameter Real damping = 0.2;
  Real x(start = 1.0);
  Real v(start = 0.0);
equation
  der(x) = v;
  der(v) = -(omega * omega) * x - damping * v;
end V036Oscillator;""",
    },
    {
        "task_id": "v036_hydraulic_bias_shift",
        "model_name": "V036Hydraulic",
        "operator": "paired_value_bias_shift",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_hydraulic_bias_shift.mo",
        "model_text": """\
model V036Hydraulic
  parameter Real A = 2.0;
  parameter Real Rout = 0.8;
  parameter Real Qin = 0.4;
  Real h(start = 1.0);
equation
  A * der(h) = Qin - h / Rout;
end V036Hydraulic;""",
    },
    {
        "task_id": "v036_heater_dual_collapse",
        "model_name": "V036Heater",
        "operator": "paired_value_collapse",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_heater_dual_collapse.mo",
        "model_text": """\
model V036Heater
  parameter Real C = 100.0;
  parameter Real G = 5.0;
  parameter Real Tenv = 293.15;
  parameter Real Q = 200.0;
  Real T(start = 350.0);
equation
  C * der(T) = Q - G * (T - Tenv);
end V036Heater;""",
    },
    {
        "task_id": "v036_decay_ab_dual_collapse",
        "model_name": "V036DecayAB",
        "operator": "paired_value_collapse",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_decay_ab_dual_collapse.mo",
        "model_text": """\
model V036DecayAB
  parameter Real a = 2.0;
  parameter Real b = 5.0;
  Real x(start = 1.0);
equation
  der(x) = -x / (a * b);
end V036DecayAB;""",
    },
    {
        "task_id": "v036_thermal_rc_dual_collapse",
        "model_name": "V036ThermalRC",
        "operator": "paired_value_collapse",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_thermal_rc_dual_collapse.mo",
        "model_text": """\
model V036ThermalRC
  parameter Real Cth = 100.0;
  parameter Real Rth = 5.0;
  parameter Real Tenv = 293.15;
  Real T(start = 350.0);
equation
  der(T) = -(T - Tenv) / (Cth * Rth);
end V036ThermalRC;""",
    },
    {
        "task_id": "v036_hydraulic_ar_dual_collapse",
        "model_name": "V036HydraulicAR",
        "operator": "paired_value_collapse",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_hydraulic_ar_dual_collapse.mo",
        "model_text": """\
model V036HydraulicAR
  parameter Real A = 2.0;
  parameter Real R = 4.0;
  parameter Real Qin = 0.4;
  Real h(start = 1.0);
equation
  der(h) = (Qin - h / R) / A;
end V036HydraulicAR;""",
    },
    {
        "task_id": "v036_charge_rc_dual_collapse",
        "model_name": "V036ChargeRC",
        "operator": "paired_value_collapse",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_charge_rc_dual_collapse.mo",
        "model_text": """\
model V036ChargeRC
  parameter Real R = 50.0;
  parameter Real C = 0.01;
  Real v(start = 5.0);
equation
  der(v) = -v / (R * C);
end V036ChargeRC;""",
    },
    {
        "task_id": "v036_mix_vtau_dual_collapse",
        "model_name": "V036MixVTau",
        "operator": "paired_value_collapse",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_mix_vtau_dual_collapse.mo",
        "model_text": """\
model V036MixVTau
  parameter Real V = 3.0;
  parameter Real tau = 2.0;
  parameter Real cin = 1.0;
  Real c(start = 0.0);
equation
  der(c) = (cin - c) / (V * tau);
end V036MixVTau;""",
    },
    {
        "task_id": "v036_flow_bias_shift",
        "model_name": "V036FlowLag",
        "operator": "paired_value_bias_shift",
        "source_library": "GateForge_v036",
        "source_model_path": "gateforge/source_models/v036/v036_flow_bias_shift.mo",
        "model_text": """\
model V036FlowLag
  parameter Real gain = 4.0;
  parameter Real tau = 0.8;
  parameter Real target = 2.0;
  Real y(start = 0.0);
equation
  tau * der(y) = gain * target - y;
end V036FlowLag;""",
    },
]


def build_post_restore_taskset(*, out_dir: str = DEFAULT_OUT_DIR) -> dict:
    out_root = Path(out_dir)
    tasks: list[dict] = []
    for spec in CANDIDATE_SPECS:
        task = build_dual_layer_multi_param_task(
            task_id=spec["task_id"],
            clean_source_text=spec["model_text"],
            source_model_path=spec["source_model_path"],
            source_library=spec["source_library"],
            model_hint=spec["model_name"],
            hidden_base_operator=spec["operator"],
        )
        tasks.append(task)
        _write_json(out_root / "tasks" / f"{spec['task_id']}.json", task)

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if tasks else "FAIL",
        "family_id": "post_restore_residual_semantic_conflict",
        "task_count": len(tasks),
        "task_ids": [task["task_id"] for task in tasks],
        "operators_used": sorted({str(task.get("hidden_base_operator") or "") for task in tasks}),
        "tasks": tasks,
    }
    _write_json(out_root / "taskset.json", summary)
    _write_text(out_root / "summary.md", render_markdown(summary))
    return summary


def render_markdown(summary: dict) -> str:
    lines = [
        "# Post-Restore Taskset v0.3.6",
        "",
        f"- status: `{summary.get('status')}`",
        f"- family_id: `{summary.get('family_id')}`",
        f"- task_count: `{summary.get('task_count')}`",
        f"- operators_used: `{', '.join(summary.get('operators_used') or [])}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the self-contained v0.3.6 post-restore candidate taskset.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_post_restore_taskset(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "task_count": payload.get("task_count")}))


if __name__ == "__main__":
    main()
