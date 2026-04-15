"""
Build and OMC-verify Type 2 inter-layer multi-turn mutations for v0.19.4.

Strategy (inter-layer masking):
  - Layer 1 (model_check_error): inject `assert(gateforge_undef_trigger_v2 > 0.0, ...)`
    in the equation section, where `gateforge_undef_trigger_v2` is never declared.
    OMC checkModel reports "Variable gateforge_undef_trigger_v2 not found" and exits
    before translating the rest — including the Layer 2 assert.
  - Layer 2 (simulate_error): inject `assert(false, "type2_l2_sim_fail_<id>")` in
    the equation section. OMC checkModel silently ignores assert(false,...) at check
    time, but simulate fails during translation.

Turn sequence the agent must execute:
  1. model_check_error → fix/remove the undefined-reference assert
  2. simulate_error   → fix/remove the assert(false,...) line

Base models: MSL-based electrical circuit models (pre-compiled in Docker → simulate works).

Verification chain (per candidate):
  A. source model → simulate passes
  B. mutated state (L1+L2) → checkModel fails: "gateforge_undef_trigger_v2 not found"
  C. L1-fixed state (remove undef assert) → checkModel passes, simulate fails: assert msg
  D. L2-fixed state (remove both asserts) → simulate passes

Outputs:
  artifacts/type2_mutations_v0_19_4/
    candidates.jsonl
    summary.json
    type2_2turn_<name>.mo   (mutated model files)
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = (
    REPO_ROOT
    / "artifacts"
    / "agent_modelica_electrical_frozen_taskset_v1_smoke"
    / "source_models"
)
OUT_DIR = REPO_ROOT / "artifacts" / "type2_mutations_v0_19_4"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

def _l2_assert(candidate_id: str) -> str:
    return f'  assert(false, "type2_l2_sim_fail_{candidate_id}");'


def _l1_var(candidate_id: str) -> str:
    suffix = candidate_id.replace("type2_2turn_", "").replace("_", "")
    return f"gateforge_undef_{suffix}_v4"


def _l1_assert(candidate_id: str) -> str:
    l1_var = _l1_var(candidate_id)
    return f'  assert({l1_var} > 0.0, "type2_l1_undef_check_{candidate_id}");'


# ---------------------------------------------------------------------------
# Mutation specs: which source model → candidate ID
# ---------------------------------------------------------------------------

MUTATION_SPECS = [
    {
        "candidate_id": "type2_2turn_rc_const",
        "description": "2-turn inter-layer: SmallRCConstantV0, L1=undef_var, L2=assert_false",
        "source_file": "small_rc_constant_v0.mo",
        "model_name": "SmallRCConstantV0",
        "expected_turns": 2,
        "source_model_path_key": "source_model_path",
    },
    {
        "candidate_id": "type2_2turn_rl_step",
        "description": "2-turn inter-layer: SmallRLStepV0, L1=undef_var, L2=assert_false",
        "source_file": "small_rl_step_v0.mo",
        "model_name": "SmallRLStepV0",
        "expected_turns": 2,
    },
    {
        "candidate_id": "type2_2turn_rlc_series",
        "description": "2-turn inter-layer: MediumRLCSeriesV0, L1=undef_var, L2=assert_false",
        "source_file": "medium_rlc_series_v0.mo",
        "model_name": "MediumRLCSeriesV0",
        "expected_turns": 2,
    },
    {
        "candidate_id": "type2_2turn_r_divider",
        "description": "2-turn inter-layer: SmallRDividerV0, L1=undef_var, L2=assert_false",
        "source_file": "small_r_divider_v0.mo",
        "model_name": "SmallRDividerV0",
        "expected_turns": 2,
    },
    {
        "candidate_id": "type2_2turn_ladder_rc",
        "description": "2-turn inter-layer: MediumLadderRCV0, L1=undef_var, L2=assert_false",
        "source_file": "medium_ladder_rc_v0.mo",
        "model_name": "MediumLadderRCV0",
        "expected_turns": 2,
    },
    {
        "candidate_id": "type2_2turn_parallel_rc",
        "description": "2-turn inter-layer: MediumParallelRCV0, L1=undef_var, L2=assert_false",
        "source_file": "medium_parallel_rc_v0.mo",
        "model_name": "MediumParallelRCV0",
        "expected_turns": 2,
    },
    {
        "candidate_id": "type2_2turn_rc_ladder4",
        "description": "2-turn inter-layer: LargeRCLadder4V0, L1=undef_var, L2=assert_false",
        "source_file": "large_rc_ladder4_v0.mo",
        "model_name": "LargeRCLadder4V0",
        "expected_turns": 2,
    },
    {
        "candidate_id": "type2_2turn_dual_source_ladder",
        "description": "2-turn inter-layer: LargeDualSourceLadderV0, L1=undef_var, L2=assert_false",
        "source_file": "large_dual_source_ladder_v0.mo",
        "model_name": "LargeDualSourceLadderV0",
        "expected_turns": 2,
    },
    {
        "candidate_id": "type2_2turn_ladder_rc_alt",
        "description": "2-turn inter-layer: MediumLadderRCV0 alt L1 variable, L2=assert_false",
        "source_file": "medium_ladder_rc_v0.mo",
        "model_name": "MediumLadderRCV0",
        "expected_turns": 2,
    },
    {
        "candidate_id": "type2_2turn_parallel_rc_alt",
        "description": "2-turn inter-layer: MediumParallelRCV0 alt L1 variable, L2=assert_false",
        "source_file": "medium_parallel_rc_v0.mo",
        "model_name": "MediumParallelRCV0",
        "expected_turns": 2,
    },
    {
        "candidate_id": "type2_2turn_rc_ladder4_alt",
        "description": "2-turn inter-layer: LargeRCLadder4V0 alt L1 variable, L2=assert_false",
        "source_file": "large_rc_ladder4_v0.mo",
        "model_name": "LargeRCLadder4V0",
        "expected_turns": 2,
    },
    {
        "candidate_id": "type2_2turn_dual_source_ladder_alt",
        "description": "2-turn inter-layer: LargeDualSourceLadderV0 alt L1 variable, L2=assert_false",
        "source_file": "large_dual_source_ladder_v0.mo",
        "model_name": "LargeDualSourceLadderV0",
        "expected_turns": 2,
    },
]


# ---------------------------------------------------------------------------
# Model text mutation helpers
# ---------------------------------------------------------------------------

def _inject_mutations(source_text: str, candidate_id: str) -> str:
    """Inject Layer 1 and Layer 2 assertions into the equation section."""
    l1_line = _l1_assert(candidate_id)
    l2_line = _l2_assert(candidate_id)
    # Find "equation" keyword and insert the two assert lines right after it
    lines = source_text.splitlines()
    new_lines = []
    injected = False
    for line in lines:
        new_lines.append(line)
        if not injected and line.strip() == "equation":
            new_lines.append(l1_line)
            new_lines.append(l2_line)
            injected = True
    if not injected:
        raise ValueError("Could not find 'equation' keyword in source model")
    return "\n".join(new_lines) + "\n"


def _remove_l1(text: str, candidate_id: str) -> str:
    """Remove the Layer 1 assert line (after agent fixes undefined-var error)."""
    l1_var = _l1_var(candidate_id)
    lines = [l for l in text.splitlines() if l1_var not in l]
    return "\n".join(lines) + "\n"


def _remove_l2(text: str, candidate_id: str) -> str:
    """Remove the Layer 2 assert(false,...) line (after agent fixes simulate_error)."""
    tag = f"type2_l2_sim_fail_{candidate_id}"
    lines = [l for l in text.splitlines() if tag not in l]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# OMC helpers
# ---------------------------------------------------------------------------

def _get_lib_cache() -> Path:
    """Return the host-side library cache dir (mirrors how omc_workspace does it)."""
    raw = str(os.getenv("GATEFORGE_OM_DOCKER_LIBRARY_CACHE") or "").strip()
    return Path(raw) if raw else (Path.home() / ".openmodelica" / "libraries")



def _omc_check(model_text: str, model_name: str) -> tuple[bool, str]:
    """Run OMC checkModel; return (passed, error_string)."""
    mos = (
        "loadModel(Modelica);\n"
        "loadFile(\"/workspace/model.mo\");\n"
        f"checkModel({model_name});\n"
        "getErrorString();\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / ".omc_home" / ".openmodelica" / "cache").mkdir(parents=True, exist_ok=True)
        (tmp_path / "model.mo").write_text(model_text, encoding="utf-8")
        (tmp_path / "run.mos").write_text(mos, encoding="utf-8")
        lib_cache = _get_lib_cache()
        lib_cache.mkdir(parents=True, exist_ok=True)
        uid_gid = f"{os.getuid()}:{os.getgid()}"
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--user", uid_gid,
                "-e", "HOME=/workspace/.omc_home",
                "-v", f"{tmp}:/workspace",
                "-v", f"{str(lib_cache)}:/workspace/.omc_home/.openmodelica/libraries",
                "-w", "/workspace",
                DOCKER_IMAGE,
                "omc", "run.mos",
            ],
            capture_output=True, text=True, timeout=90,
        )
        output = result.stdout + result.stderr
        lines = [l.strip() for l in output.splitlines() if l.strip()]
        errors = ""
        for l in lines:
            if l.startswith('"') and len(l) > 2:
                errors = l.strip('"')
        check_model_true = any(l == "true" for l in lines)
        has_errors = "Error" in errors
        passed = check_model_true and not has_errors
        return passed, errors


def _omc_simulate(model_text: str, model_name: str) -> tuple[bool, str]:
    """Run OMC simulate (short run); return (passed, error_string)."""
    mos = (
        "loadModel(Modelica);\n"
        "loadFile(\"/workspace/model.mo\");\n"
        f"simulate({model_name}, startTime=0.0, stopTime=0.01, "
        f"numberOfIntervals=10, tolerance=1e-06);\n"
        "getErrorString();\n"
    )
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / ".omc_home" / ".openmodelica" / "cache").mkdir(parents=True, exist_ok=True)
        (tmp_path / "model.mo").write_text(model_text, encoding="utf-8")
        (tmp_path / "run.mos").write_text(mos, encoding="utf-8")
        lib_cache = _get_lib_cache()
        lib_cache.mkdir(parents=True, exist_ok=True)
        uid_gid = f"{os.getuid()}:{os.getgid()}"
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "--user", uid_gid,
                "-e", "HOME=/workspace/.omc_home",
                "-v", f"{tmp}:/workspace",
                "-v", f"{str(lib_cache)}:/workspace/.omc_home/.openmodelica/libraries",
                "-w", "/workspace",
                DOCKER_IMAGE,
                "omc", "run.mos",
            ],
            capture_output=True, text=True, timeout=150,
        )
        output = result.stdout + result.stderr
        lines = [l.strip() for l in output.splitlines() if l.strip()]
        error_text = ""
        for l in lines:
            if l.startswith('"') and len(l) > 2:
                error_text = l.strip('"')
        has_error = "Error" in error_text
        has_result = any("resultFile" in l for l in lines)
        passed = has_result and not has_error
        return passed, error_text if error_text else output[:400]


# ---------------------------------------------------------------------------
# Verify masking chain
# ---------------------------------------------------------------------------

def _verify_candidate(spec: dict, source_text: str, source_path: Path) -> dict:
    cid = spec["candidate_id"]
    model_name = spec["model_name"]
    l1_var = _l1_var(cid)

    print(f"  [A] Verifying source model simulates cleanly...")
    src_sim_pass, src_sim_err = _omc_simulate(source_text, model_name)
    if not src_sim_pass:
        return {"ok": False, "reason": f"source model simulate fails: {src_sim_err[:300]}"}
    print(f"      ✓ source simulate passes")

    print(f"  [B] Injecting L1+L2 mutations...")
    try:
        mutated_text = _inject_mutations(source_text, cid)
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}

    mut_check_pass, mut_check_err = _omc_check(mutated_text, model_name)
    if mut_check_pass:
        return {"ok": False, "reason": "mutated model unexpectedly passes checkModel"}
    if l1_var not in mut_check_err:
        return {
            "ok": False,
            "reason": f"expected '{l1_var}' in checkModel error, got: {mut_check_err[:200]}",
        }
    print(f"      ✓ mutated checkModel fails: mentions '{l1_var}'")

    print(f"  [C] Removing L1 (undefined assert)...")
    l1_fixed_text = _remove_l1(mutated_text, cid)
    l1_check_pass, l1_check_err = _omc_check(l1_fixed_text, model_name)
    if not l1_check_pass:
        return {
            "ok": False,
            "reason": f"after L1 fix, checkModel still fails: {l1_check_err[:200]}",
        }
    print(f"      ✓ L1-fixed checkModel passes")

    l1_sim_pass, l1_sim_err = _omc_simulate(l1_fixed_text, model_name)
    if l1_sim_pass:
        return {
            "ok": False,
            "reason": "after L1 fix, simulate unexpectedly passes (L2 assert not catching)",
        }
    l2_tag = f"type2_l2_sim_fail_{cid}"
    if l2_tag not in l1_sim_err:
        # Check full output too
        print(f"      ! L2 sim error (tag not in excerpt): {l1_sim_err[:300]}")
        # Still accept if simulate fails — assert fires even if tag truncated
        if "Assertion" not in l1_sim_err and "assert" not in l1_sim_err.lower():
            return {
                "ok": False,
                "reason": f"after L1 fix, simulate fails but not due to L2 assert: {l1_sim_err[:300]}",
            }
    print(f"      ✓ L1-fixed simulate fails with L2 assert trigger")

    print(f"  [D] Removing L2 (assert false)...")
    l2_fixed_text = _remove_l2(l1_fixed_text, cid)
    l2_sim_pass, l2_sim_err = _omc_simulate(l2_fixed_text, model_name)
    if not l2_sim_pass:
        return {
            "ok": False,
            "reason": f"after L2 fix, simulate still fails: {l2_sim_err[:300]}",
        }
    print(f"      ✓ fully-fixed simulate passes")

    chain = [
        {
            "turn": 0,
            "state": "mutated_L1_and_L2",
            "failure_type": "model_check_error",
            "error": mut_check_err,
            "contains": l1_var,
        },
        {
            "turn": 1,
            "state": "L1_fixed_L2_remaining",
            "failure_type": "simulate_error",
            "error": l1_sim_err,
            "contains": l2_tag,
        },
        {
            "turn": 2,
            "state": "both_fixed",
            "failure_type": None,
            "pass": True,
        },
    ]
    return {
        "ok": True,
        "mutated_text": mutated_text,
        "chain": chain,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    candidates = []
    results = []

    for spec in MUTATION_SPECS:
        cid = spec["candidate_id"]
        source_path = SOURCE_DIR / spec["source_file"]
        print(f"\n[{cid}] {spec['description']}")

        if not source_path.exists():
            print(f"  ✗ source file not found: {source_path}")
            results.append({"candidate_id": cid, "status": "FAIL", "reason": "source_not_found"})
            continue

        source_text = source_path.read_text(encoding="utf-8")
        result = _verify_candidate(spec, source_text, source_path)

        if result["ok"]:
            print(f"  ✓ masking chain verified (2 turns: model_check_error → simulate_error)")

            # Save mutated model file
            mut_path = OUT_DIR / f"{cid}.mo"
            mut_path.write_text(result["mutated_text"], encoding="utf-8")

            candidates.append({
                "candidate_id": cid,
                "task_id": cid,
                "benchmark_family": "type2_inter_layer",
                "description": spec["description"],
                "expected_turns": spec["expected_turns"],
                "source_model_path": str(source_path),
                "mutated_model_path": str(mut_path),
                # Initial failure is model_check_error (L1 hides L2).
                # expected_stage=simulate so the executor runs simulate after
                # checkModel passes, exposing the L2 simulate_error on turn 2.
                "failure_type": "model_check_error",
                "expected_stage": "simulate",
                "layer1_type": "undefined_variable",
                "layer2_type": "simulate_assert_false",
                "layer1_var": _l1_var(cid),
                "layer2_tag": f"type2_l2_sim_fail_{cid}",
                "turn_sequence": ["model_check_error", "simulate_error"],
                "masking_chain_verified": True,
                "chain": result["chain"],
            })
            results.append({"candidate_id": cid, "status": "PASS"})
        else:
            print(f"  ✗ verification failed: {result['reason']}")
            results.append({"candidate_id": cid, "status": "FAIL", "reason": result["reason"]})

    # Write outputs
    jsonl_path = OUT_DIR / "candidates.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for c in candidates:
            f.write(json.dumps(c) + "\n")

    summary = {
        "total": len(MUTATION_SPECS),
        "verified": len(candidates),
        "failed": len(MUTATION_SPECS) - len(candidates),
        "results": results,
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    print(f"\n=== Summary ===")
    print(f"  verified: {summary['verified']} / {summary['total']}")
    if candidates:
        print(f"  candidates written to: {OUT_DIR}/candidates.jsonl")
    for r in results:
        status = r["status"]
        reason = r.get("reason", "")
        mark = "✓" if status == "PASS" else "✗"
        print(f"  {mark} {r['candidate_id']}: {status}" + (f" ({reason})" if reason else ""))


if __name__ == "__main__":
    main()
