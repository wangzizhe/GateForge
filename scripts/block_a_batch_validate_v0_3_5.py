#!/usr/bin/env python3
"""
Block A Batch Validator for v0.3.5 dual-layer mutation lane.

For each candidate model:
  1. Simulate clean version  -> must PASS
  2. Simulate hidden-base-mutated version -> must FAIL (stage_4/5)
  3. Build dual-layer task record
  4. Run admission gates
  5. Report lane status

Usage:
  python3 scripts/block_a_batch_validate_v0_3_5.py
"""

import sys
import os
import json
import pathlib

# Ensure gateforge package is importable
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
os.environ["PATH"] = "/usr/local/bin:" + os.environ.get("PATH", "")

from gateforge.agent_modelica_omc_workspace_v1 import (
    run_check_and_simulate,
    rel_mos_path,
    temporary_workspace,
)
from gateforge.agent_modelica_dual_layer_mutation_v0_3_5 import (
    apply_init_value_collapse,
    apply_init_equation_sign_flip,
    apply_marked_top_mutation,
    build_dual_layer_task,
    validate_dual_layer_text_pair,
)
from gateforge.agent_modelica_post_restore_family_spec_v0_3_5 import (
    run_admission_gates,
    build_lane_summary,
)

DOCKER_IMAGE = os.environ.get(
    "GATEFORGE_DOCKER_IMAGE", "openmodelica/openmodelica:v1.26.1-minimal"
)
TIMEOUT = 90
STOP_TIME_DEFAULT = 5.0

# ---------------------------------------------------------------------------
# Candidate model definitions
# Each entry: (task_id, model_name, clean_text, operator, op_kwargs, stop_time)
# ---------------------------------------------------------------------------

CANDIDATES = [
    # ---- Group A: init_value_collapse (R/C_th/m → 0.0) --------------------
    (
        "rc_collapse_R",
        "DualLayerRC",
        """\
model DualLayerRC
  parameter Real R = 100.0;
  parameter Real C = 0.001;
  Real v(start = 1.0);
equation
  R * C * der(v) = -v;
end DualLayerRC;""",
        "init_value_collapse",
        {},  # default: first Real param → 0.0
        1.0,
    ),
    (
        "thermal_collapse_Cth",
        "DualLayerThermal",
        """\
model DualLayerThermal
  parameter Real C_th = 500.0;
  parameter Real h = 10.0;
  parameter Real T_env = 20.0;
  Real T(start = 80.0);
equation
  C_th * der(T) = -h * (T - T_env);
end DualLayerThermal;""",
        "init_value_collapse",
        {},
        100.0,
    ),
    (
        "msd_collapse_m",
        "DualLayerMSD",
        """\
model DualLayerMSD
  parameter Real m = 2.0;
  parameter Real d = 0.5;
  parameter Real k = 10.0;
  Real x(start = 1.0);
  Real v(start = 0.0);
equation
  der(x) = v;
  m * der(v) = -k * x - d * v;
end DualLayerMSD;""",
        "init_value_collapse",
        {},
        10.0,
    ),
    (
        "rlc_collapse_L",
        "DualLayerRLC",
        """\
model DualLayerRLC
  parameter Real R = 20.0;
  parameter Real L = 0.1;
  parameter Real C = 0.001;
  Real i(start = 0.0);
  Real v_c(start = 1.0);
equation
  L * der(i) = 5.0 - R * i - v_c;
  C * der(v_c) = i;
end DualLayerRLC;""",
        "init_value_collapse",
        {"target_param_pattern": r"parameter\s+Real\s+(L)\s*=\s*([0-9]+\.?[0-9]*)"},
        5.0,
    ),
    (
        "hydraulic_collapse_A",
        "DualLayerTank",
        """\
model DualLayerTank
  parameter Real A = 1.0;
  parameter Real c = 0.5;
  parameter Real Q_in = 0.3;
  Real h(start = 2.0);
equation
  A * der(h) = Q_in - c * sqrt(max(h, 0.0));
end DualLayerTank;""",
        "init_value_collapse",
        {},
        20.0,
    ),
    (
        "spring_collapse_m",
        "DualLayerSpring",
        """\
model DualLayerSpring
  parameter Real m = 1.0;
  parameter Real omega = 3.0;
  Real x(start = 2.0);
  Real v(start = 0.0);
equation
  der(x) = v;
  m * der(v) = -(omega * omega) * x;
end DualLayerSpring;""",
        "init_value_collapse",
        {},
        10.0,
    ),
    # ---- Group B: init_equation_sign_flip (sqrt/log domain violation) ------
    (
        "sqrt_decay_sign_flip",
        "DualLayerSqrtDecay",
        """\
model DualLayerSqrtDecay
  Real x(start = 10.0);
initial equation
  x = 10.0;
equation
  der(x) = 1.0 - sqrt(x);
end DualLayerSqrtDecay;""",
        "init_equation_sign_flip",
        {},
        5.0,
    ),
    (
        "log_decay_sign_flip",
        "DualLayerLogDecay",
        """\
model DualLayerLogDecay
  Real x(start = 3.0);
initial equation
  x = 3.0;
equation
  der(x) = log(x) - x;
end DualLayerLogDecay;""",
        "init_equation_sign_flip",
        {},
        5.0,
    ),
    (
        "sqrt_growth_sign_flip",
        "DualLayerSqrtGrowth",
        """\
model DualLayerSqrtGrowth
  Real x(start = 4.0);
initial equation
  x = 4.0;
equation
  der(x) = sqrt(x) * (1.0 - x / 9.0);
end DualLayerSqrtGrowth;""",
        "init_equation_sign_flip",
        {},
        5.0,
    ),
    (
        "tank_level_sign_flip",
        "DualLayerTankLevel",
        """\
model DualLayerTankLevel
  parameter Real A = 1.0;
  Real h(start = 4.0);
initial equation
  h = 4.0;
equation
  A * der(h) = 1.0 - sqrt(h);
end DualLayerTankLevel;""",
        "init_equation_sign_flip",
        {},
        10.0,
    ),
    (
        "log_osc_sign_flip",
        "DualLayerLogOsc",
        """\
model DualLayerLogOsc
  Real y(start = 2.0);
initial equation
  y = 2.0;
equation
  der(y) = -log(y) * y;
end DualLayerLogOsc;""",
        "init_equation_sign_flip",
        {},
        5.0,
    ),
    (
        "sqrt_two_state_sign_flip",
        "DualLayerSqrtTwo",
        """\
model DualLayerSqrtTwo
  Real x(start = 1.0);
  Real y(start = 4.0);
initial equation
  x = 1.0;
  y = 4.0;
equation
  der(x) = sqrt(y) - x;
  der(y) = x - y;
end DualLayerSqrtTwo;""",
        "init_equation_sign_flip",
        {},
        5.0,
    ),
]

# ---------------------------------------------------------------------------
# OMC helper
# ---------------------------------------------------------------------------

def omc_simulate(model_name: str, model_text: str, stop_time: float) -> dict:
    with temporary_workspace("gf_block_a_") as wdir:
        wpath = pathlib.Path(wdir)
        mo = wpath / f"{model_name}.mo"
        mo.write_text(model_text, encoding="utf-8")
        rel = rel_mos_path(mo, wpath)
        rc, output, check_ok, sim_ok = run_check_and_simulate(
            workspace=wpath,
            model_load_files=[rel],
            model_name=model_name,
            timeout_sec=TIMEOUT,
            backend="docker",
            docker_image=DOCKER_IMAGE,
            stop_time=stop_time,
            intervals=500,
        )
    return {"rc": rc, "check_ok": check_ok, "sim_ok": sim_ok, "output": output[:400]}


# ---------------------------------------------------------------------------
# Main batch loop
# ---------------------------------------------------------------------------

def main():
    results = []
    passed_tasks = []

    for (task_id, model_name, clean_text, operator, op_kwargs, stop_time) in CANDIDATES:
        print(f"\n{'='*60}")
        print(f"[{task_id}] operator={operator}")

        # 1. Apply hidden base mutation
        if operator == "init_value_collapse":
            mutated_text, audit = apply_init_value_collapse(clean_text, **op_kwargs)
        elif operator == "init_equation_sign_flip":
            mutated_text, audit = apply_init_equation_sign_flip(clean_text, **op_kwargs)
        else:
            print(f"  SKIP: unknown operator {operator}")
            continue

        if not audit.get("applied"):
            print(f"  SKIP: mutation not applied: {audit.get('reason')}")
            continue

        print(f"  mutation audit: {json.dumps(audit, default=str)[:200]}")

        # 2. Test clean version
        print(f"  [clean] simulate ...", flush=True)
        r_clean = omc_simulate(model_name, clean_text, stop_time)
        print(f"  [clean] check_ok={r_clean['check_ok']} sim_ok={r_clean['sim_ok']}")

        if not r_clean["sim_ok"]:
            print(f"  SKIP: clean version already fails simulation!")
            results.append({"task_id": task_id, "verdict": "SKIP_clean_fails", **r_clean})
            continue

        # 3. Test mutated (hidden base only) version
        print(f"  [mutated] simulate ...", flush=True)
        r_mut = omc_simulate(model_name, mutated_text, stop_time)
        print(f"  [mutated] check_ok={r_mut['check_ok']} sim_ok={r_mut['sim_ok']}")

        if not r_mut["check_ok"]:
            print(f"  SKIP: mutated version fails check_model (too early stage)")
            results.append({"task_id": task_id, "verdict": "SKIP_check_fails", **r_mut})
            continue

        if r_mut["sim_ok"]:
            print(f"  SKIP: mutated version unexpectedly passes simulation!")
            results.append({"task_id": task_id, "verdict": "SKIP_sim_passes", **r_mut})
            continue

        # 4. Build full dual-layer task
        print(f"  BUILD dual-layer task ...")
        try:
            task = build_dual_layer_task(
                task_id=task_id,
                clean_source_text=clean_text,
                source_model_path=f"gateforge/source_models/v035/{model_name.lower()}.mo",
                source_library="GateForge_v035",
                model_hint=f"{model_name} self-contained model for dual-layer mutation",
                hidden_base_operator=operator,
                declared_failure_type="simulate_error",
                expected_stage="simulate",
                hidden_base_kwargs=op_kwargs or None,
            )
        except Exception as exc:
            print(f"  SKIP: build_dual_layer_task failed: {exc}")
            results.append({"task_id": task_id, "verdict": "SKIP_build_error", "error": str(exc)})
            continue

        # 5. Validate text pair
        pair_check = validate_dual_layer_text_pair(
            task["source_model_text"], task["mutated_model_text"]
        )
        if pair_check["status"] != "PASS":
            print(f"  SKIP: text pair validation failed: {pair_check['reasons']}")
            results.append({"task_id": task_id, "verdict": "SKIP_pair_fail", "reasons": pair_check["reasons"]})
            continue

        # 6. Pre-fill admission gate fields (planner fields from OMC evidence)
        # At this stage planner_invoked=None; gates that require planner data
        # will not penalize (check_planner_sensitivity_gate passes if
        # dual_layer_mutation=True)
        gate_result = run_admission_gates(task)
        print(f"  admission gates: passed={gate_result['passed']} gates={gate_result['gates']}")

        verdict = "PASS" if gate_result["passed"] else "NEEDS_REVIEW"
        print(f"  verdict: {verdict}")
        results.append({
            "task_id": task_id,
            "verdict": verdict,
            "gates": gate_result,
            "operator": operator,
        })
        if gate_result["passed"]:
            passed_tasks.append(task)

    # 7. Lane summary
    print(f"\n{'='*60}")
    print("LANE SUMMARY")
    summary = build_lane_summary(passed_tasks)
    print(json.dumps(summary, indent=2))

    print(f"\nPassed tasks: {len(passed_tasks)}/{len(CANDIDATES)}")
    for r in results:
        print(f"  {r['task_id']:40s}  {r['verdict']}")

    # 8. Save candidates to artifacts
    if passed_tasks:
        out_dir = REPO_ROOT / "artifacts" / "agent_modelica_block_a_dual_layer_candidates_v0_3_5"
        out_dir.mkdir(parents=True, exist_ok=True)
        for task in passed_tasks:
            fname = out_dir / f"{task['task_id']}.json"
            fname.write_text(json.dumps(task, indent=2), encoding="utf-8")
            print(f"  saved: {fname.name}")
        summary_path = out_dir / "lane_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"\nLane summary saved to: {summary_path}")

    return 0 if len(passed_tasks) >= 10 else 1


if __name__ == "__main__":
    sys.exit(main())
