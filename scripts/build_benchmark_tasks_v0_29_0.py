#!/usr/bin/env python3
"""Build OMC-admission-verified benchmark repair tasks."""
from __future__ import annotations

import json, re, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_tool_use_harness_v0_28_0 import _run_omc
from gateforge.agent_modelica_benchmark_schema_v0_29_0 import validate_benchmark_task

TASK_DIR = REPO_ROOT / "assets_private" / "benchmarks" / "agent_comparison_v1" / "tasks"


def admission_ok(model_text: str) -> tuple[bool, str]:
    name = "M"
    m = re.search(r'model\s+(\w+)', model_text)
    if m:
        name = m.group(1)
    _rc, output, check_ok, _sim = _run_omc(model_text, name)
    if check_ok:
        return False, "checkModel PASSED"
    errs = [l.strip() for l in output.splitlines() if "rror" in l.lower() or "arning" in l.lower()]
    return True, "; ".join(errs[:2])[:200] if errs else "error_detected"


REPAIR_CASES = []

# --- r1: simple missing equation ---
REPAIR_CASES.append({
    "case_id": "r_01_missing_eq",
    "task_type": "repair",
    "title": "Fix missing equation (under-determined standalone)",
    "difficulty": "simple",
    "source_backed": True,
    "description": "Variable y has no defining equation. Fix so checkModel and simulate pass.",
    "initial_model": (
        "model FixY\n"
        "  Real x;\n"
        "  Real y;\n"
        "equation\n"
        "  x = 1.0;\n"
        "end FixY;\n"
    ),
    "constraints": ["Keep model name unchanged."],
    "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
})

# --- r2: over-determined ---
REPAIR_CASES.append({
    "case_id": "r_02_duplicate_eq",
    "task_type": "repair",
    "title": "Fix duplicate equation (over-determined)",
    "difficulty": "simple",
    "source_backed": True,
    "description": "Variable x has conflicting equations. Fix so checkModel and simulate pass.",
    "initial_model": (
        "model FixDup\n"
        "  Real x;\n"
        "equation\n"
        "  x = 1.0;\n"
        "  x = 2.0;\n"
        "end FixDup;\n"
    ),
    "constraints": ["Keep model name unchanged."],
    "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
})

# --- r3: MSL with extra undeclared variable ---
REPAIR_CASES.append({
    "case_id": "r_03_msl_extra_var",
    "task_type": "repair",
    "title": "Fix extra variable in MSL RC circuit",
    "difficulty": "simple",
    "source_backed": True,
    "description": "Variable Vextra added without equation. Fix: add equation or remove it.",
    "initial_model": (
        "model RCExtra\n"
        "  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10);\n"
        "  Modelica.Electrical.Analog.Basic.Resistor R1(R=100);\n"
        "  Modelica.Electrical.Analog.Basic.Ground G;\n"
        "  Real Vextra;\n"
        "equation\n"
        "  connect(V1.p, R1.p);\n"
        "  connect(R1.n, V1.n);\n"
        "  connect(V1.n, G.p);\n"
        "end RCExtra;\n"
    ),
    "constraints": ["Keep MSL components.", "Keep connect topology."],
    "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
})

# --- r4: MSL over-determined ---
REPAIR_CASES.append({
    "case_id": "r_04_msl_over",
    "task_type": "repair",
    "title": "Fix over-determined MSL RC circuit",
    "difficulty": "simple",
    "source_backed": True,
    "description": "Duplicate Vmeas equation. Fix by removing the redundant equation.",
    "initial_model": (
        "model RCOver\n"
        "  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10);\n"
        "  Modelica.Electrical.Analog.Basic.Resistor R1(R=100);\n"
        "  Modelica.Electrical.Analog.Basic.Ground G;\n"
        "  Real Vmeas;\n"
        "equation\n"
        "  Vmeas = V1.v;\n"
        "  Vmeas = R1.i;\n"
        "  connect(V1.p, R1.p);\n"
        "  connect(R1.n, V1.n);\n"
        "  connect(V1.n, G.p);\n"
        "end RCOver;\n"
    ),
    "constraints": ["Keep MSL components.", "Keep connect topology."],
    "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
})

# --- r5: phantom variable (medium) ---
REPAIR_CASES.append({
    "case_id": "r_05_phantom_msl",
    "task_type": "repair",
    "title": "Fix phantom variable in MSL RC circuit",
    "difficulty": "medium",
    "source_backed": True,
    "description": "Vprobe has an equation but Vactual has none. Phantom variable pattern: Vactual should get the equation, Vprobe should be removed.",
    "initial_model": (
        "model RCPhantomFix\n"
        "  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10);\n"
        "  Modelica.Electrical.Analog.Basic.Resistor R1(R=100);\n"
        "  Modelica.Electrical.Analog.Basic.Ground G;\n"
        "  Real Vprobe;\n"
        "  Real Vactual;\n"
        "equation\n"
        "  Vprobe = V1.v;\n"
        "  connect(V1.p, R1.p);\n"
        "  connect(R1.n, V1.n);\n"
        "  connect(V1.n, G.p);\n"
        "end RCPhantomFix;\n"
    ),
    "constraints": ["Keep MSL components.", "Keep connect topology.", "Remove unused variables."],
    "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
})

# --- r6: double missing (medium) ---
REPAIR_CASES.append({
    "case_id": "r_06_double_missing",
    "task_type": "repair",
    "title": "Fix two missing equations",
    "difficulty": "medium",
    "source_backed": True,
    "description": "Both b and c have no defining equations. Fix both.",
    "initial_model": (
        "model DoubleMiss\n"
        "  Real a;\n"
        "  Real b;\n"
        "  Real c;\n"
        "  Real d;\n"
        "equation\n"
        "  a = 1.0;\n"
        "  d = a + 1.0;\n"
        "end DoubleMiss;\n"
    ),
    "constraints": ["All variables need defining equations."],
    "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
})

# --- r7: broken connect (medium) ---
REPAIR_CASES.append({
    "case_id": "r_07_broken_connect",
    "task_type": "repair",
    "title": "Restore missing connect in RC circuit",
    "difficulty": "medium",
    "source_backed": True,
    "description": "A connect statement was removed, leaving floating nodes. Restore it.",
    "initial_model": (
        "model RCBroken\n"
        "  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10);\n"
        "  Modelica.Electrical.Analog.Basic.Resistor R1(R=100);\n"
        "  Modelica.Electrical.Analog.Basic.Ground G;\n"
        "equation\n"
        "  connect(V1.p, R1.p);\n"
        "  connect(V1.n, G.p);\n"
        "end RCBroken;\n"
    ),
    "constraints": ["Keep all components.", "Restore the missing connection."],
    "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
})

# --- r8: cascaded RC under (complex) ---
REPAIR_CASES.append({
    "case_id": "r_08_cascaded_probes",
    "task_type": "repair",
    "title": "Fix probe variables in cascaded RC network",
    "difficulty": "complex",
    "source_backed": True,
    "description": "Two probe variables (Vmid_probe, Vout_probe) added without equations in a cascaded RC network. Remove them or add equations.",
    "initial_model": (
        "model CascFix\n"
        "  Modelica.Electrical.Analog.Sources.StepVoltage V1(V=5, startTime=0.1);\n"
        "  Modelica.Electrical.Analog.Basic.Resistor R1(R=100);\n"
        "  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.001);\n"
        "  Modelica.Electrical.Analog.Basic.Resistor R2(R=220);\n"
        "  Modelica.Electrical.Analog.Basic.Capacitor C2(C=0.0022);\n"
        "  Modelica.Electrical.Analog.Basic.Ground G;\n"
        "  Real Vmid_probe;\n"
        "  Real Vout_probe;\n"
        "equation\n"
        "  connect(V1.p, R1.p);\n"
        "  connect(R1.n, C1.p);\n"
        "  connect(C1.n, V1.n);\n"
        "  connect(V1.n, R2.p);\n"
        "  connect(R2.n, C2.p);\n"
        "  connect(C2.n, V1.n);\n"
        "  connect(V1.n, G.p);\n"
        "end CascFix;\n"
    ),
    "constraints": ["Keep all components.", "Keep connect topology."],
    "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
})

# --- r9: RC circuit with capacitor + under (complex) ---
REPAIR_CASES.append({
    "case_id": "r_09_rc_cap_under",
    "task_type": "repair",
    "title": "Fix under-determined RC circuit with capacitor",
    "difficulty": "complex",
    "source_backed": True,
    "description": "An extra variable C1_current in a working RC circuit creates under-determination. Fix.",
    "initial_model": (
        "model RCCapFix\n"
        "  Modelica.Electrical.Analog.Sources.ConstantVoltage V1(V=10);\n"
        "  Modelica.Electrical.Analog.Basic.Resistor R1(R=100);\n"
        "  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.01);\n"
        "  Modelica.Electrical.Analog.Basic.Ground G;\n"
        "  Real C1_current;\n"
        "equation\n"
        "  connect(V1.p, R1.p);\n"
        "  connect(R1.n, C1.p);\n"
        "  connect(C1.n, V1.n);\n"
        "  connect(V1.n, G.p);\n"
        "end RCCapFix;\n"
    ),
    "constraints": ["Keep all components.", "Keep connect topology."],
    "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
})

# --- r10: RLC under (complex) ---
REPAIR_CASES.append({
    "case_id": "r_10_rlc_probes",
    "task_type": "repair",
    "title": "Fix probe variables in RLC series circuit",
    "difficulty": "complex",
    "source_backed": True,
    "description": "Two probe variables in an RLC circuit without equations. Fix.",
    "initial_model": (
        "model RLCFix\n"
        "  Modelica.Electrical.Analog.Sources.StepVoltage V1(V=5, startTime=0.1);\n"
        "  Modelica.Electrical.Analog.Basic.Inductor L1(L=0.1);\n"
        "  Modelica.Electrical.Analog.Basic.Resistor R1(R=10);\n"
        "  Modelica.Electrical.Analog.Basic.Capacitor C1(C=0.001);\n"
        "  Modelica.Electrical.Analog.Basic.Ground G;\n"
        "  Real IL_probe;\n"
        "  Real VR_probe;\n"
        "equation\n"
        "  connect(V1.p, L1.p);\n"
        "  connect(L1.n, R1.p);\n"
        "  connect(R1.n, C1.p);\n"
        "  connect(C1.n, V1.n);\n"
        "  connect(V1.n, G.p);\n"
        "end RLCFix;\n"
    ),
    "constraints": ["Keep all components.", "Keep connect topology."],
    "verification": {"check_model": True, "simulate": {"stop_time": 0.1, "intervals": 100}},
})

# ── Write & validate ────────────────────────────────────────────────────
if __name__ == "__main__":
    out = TASK_DIR / "repair"
    out.mkdir(parents=True, exist_ok=True)
    written = 0

    for task in REPAIR_CASES:
        cid = task["case_id"]
        # Schema validation
        errs = validate_benchmark_task(task)
        if errs:
            print(f"SKIP {cid}: schema — {'; '.join(errs)}")
            continue
        # OMC admission
        has_error, msg = admission_ok(task["initial_model"])
        if not has_error:
            print(f"SKIP {cid}: no OMC error — {msg}")
            continue
        # Write
        path = out / f"{cid}.json"
        path.write_text(json.dumps(task, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written += 1
        print(f"OK  {cid}: [{task['difficulty']}] {msg[:120]}")

    print(f"\nAdmitted: {written}/{len(REPAIR_CASES)}")
