"""
Build and OMC-verify Type 1 intra-layer multi-turn mutations for v0.19.3.

Strategy:
- LargeGrid has 3 equations (x/y/z), each using 7 parameters in alternating +/- pattern
- Inject realistic-looking typo suffixes into parameter names (e.g. p7_final, p14_v2)
- OMC reports errors one at a time → fixing error A reveals error B
- Verify the full masking chain with real OMC runs before accepting a candidate

Outputs:
  artifacts/type1_mutations_v0_19_3/
    candidates.jsonl        - verified mutation candidates
    summary.json
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_MODEL = (
    REPO_ROOT
    / "artifacts"
    / "run_private_model_mutation_scale_batch_v1_demo"
    / "private_models"
    / "LargeGrid.mo"
)
OUT_DIR = REPO_ROOT / "artifacts" / "type1_mutations_v0_19_3"
DOCKER_IMAGE = "openmodelica/openmodelica:v1.26.1-minimal"

# ---------------------------------------------------------------------------
# Mutation templates
# ---------------------------------------------------------------------------

# Each mutation spec: list of (original_token, replacement_token) per equation.
# Replacements look like realistic typos/version suffixes.
MUTATION_SPECS = [
    {
        "candidate_id": "type1_2turn_yz",
        "description": "2-turn: error in y (p14_v2) then z (p21_orig)",
        "expected_turns": 2,
        "replacements": [
            ("p14;", "p14_v2;"),   # y equation: last param wrong
            ("p21;", "p21_orig;"), # z equation: last param wrong (hidden by y)
        ],
    },
    {
        "candidate_id": "type1_3turn_xyz",
        "description": "3-turn: error in x (p7_final), y (p14_v2), z (p21_orig)",
        "expected_turns": 3,
        "replacements": [
            ("p7;",  "p7_final;"),  # x equation: last param wrong (reported first)
            ("p14;", "p14_v2;"),    # y equation: hidden by x error
            ("p21;", "p21_orig;"),  # z equation: hidden by y error
        ],
    },
    {
        "candidate_id": "type1_2turn_xz",
        "description": "2-turn: error in x (p7_final) then z (p21_orig), y correct",
        "expected_turns": 2,
        "replacements": [
            ("p7;",  "p7_final;"),
            ("p21;", "p21_orig;"),
        ],
    },
]

# Surface fix rules: what the agent should restore at each turn.
# Key = wrong token, value = correct token
SURFACE_FIXES = {
    "p7_final;":  "p7;",
    "p14_v2;":    "p14;",
    "p21_orig;":  "p21;",
}


# ---------------------------------------------------------------------------
# OMC helpers
# ---------------------------------------------------------------------------

def _omc_check(model_text: str, model_name: str = "LargeGrid") -> tuple[bool, str]:
    """Run OMC checkModel, return (passed, error_string)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        mo_file = tmp_path / "model.mo"
        mos_file = tmp_path / "run.mos"
        mo_file.write_text(model_text, encoding="utf-8")
        mos_file.write_text(
            f'loadFile("{tmp}/model.mo");\n'
            f"checkModel({model_name});\n"
            f"getErrorString();\n",
            encoding="utf-8",
        )
        import os
        uid = os.getuid()
        gid = os.getgid()
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{tmp}:{tmp}",
                "--user", f"{uid}:{gid}",
                "-e", "HOME=/tmp",
                DOCKER_IMAGE,
                "omc", str(mos_file),
            ],
            capture_output=True, text=True, timeout=60,
        )
        output = result.stdout + result.stderr
        # Parse: checkModel returns "true" or "false"
        lines = [l.strip() for l in output.splitlines() if l.strip()]
        # Grab error string from getErrorString() — last non-empty quoted block
        errors = ""
        for l in lines:
            if l.startswith('"') and len(l) > 2:
                errors = l.strip('"')
        # Model truly passes only if checkModel returned true AND no errors reported
        check_model_true = any(l == "true" for l in lines)
        has_errors = "Error" in errors
        passed = check_model_true and not has_errors
        return passed, errors


def _apply_replacements(text: str, replacements: list[tuple[str, str]]) -> str:
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _apply_surface_fix(text: str, wrong_token: str) -> str:
    correct = SURFACE_FIXES[wrong_token]
    return text.replace(wrong_token, correct)


# ---------------------------------------------------------------------------
# Verify masking chain for a single candidate
# ---------------------------------------------------------------------------

def _verify_candidate(spec: dict, source_text: str) -> dict:
    replacements = spec["replacements"]
    wrong_tokens = [r[1] for r in replacements]  # e.g. ["p14_v2;", "p21_orig;"]

    # Step 0: source model must pass
    src_pass, src_err = _omc_check(source_text)
    if not src_pass:
        return {"ok": False, "reason": f"source model fails: {src_err}"}

    # Step 1: apply all mutations → should fail with first wrong token's error
    mutated = _apply_replacements(source_text, replacements)
    pass1, err1 = _omc_check(mutated)
    if pass1:
        return {"ok": False, "reason": "mutated model unexpectedly passes checkModel"}

    first_wrong = wrong_tokens[0].rstrip(";")  # e.g. "p14_v2"
    if first_wrong not in err1:
        return {
            "ok": False,
            "reason": f"expected first error to mention '{first_wrong}', got: {err1[:200]}",
        }

    # Step 2..N: iteratively apply surface fixes, verify each step exposes next error
    current_text = mutated
    chain = [{"turn": 0, "state": "mutated", "error": err1, "contains": first_wrong}]

    for turn_idx, wrong_token in enumerate(wrong_tokens, start=1):
        # Apply fix for this turn's error
        current_text = _apply_surface_fix(current_text, wrong_token)
        step_pass, step_err = _omc_check(current_text)

        is_last = (turn_idx == len(wrong_tokens))
        if is_last:
            if not step_pass:
                return {
                    "ok": False,
                    "reason": f"after fixing all errors, model still fails: {step_err[:200]}",
                }
            chain.append({"turn": turn_idx, "state": "all_fixed", "error": "", "pass": True})
        else:
            if step_pass:
                return {
                    "ok": False,
                    "reason": f"after fixing turn {turn_idx}, model passes but expected more errors",
                }
            next_wrong = wrong_tokens[turn_idx].rstrip(";")
            if next_wrong not in step_err:
                return {
                    "ok": False,
                    "reason": (
                        f"after fixing turn {turn_idx}, expected '{next_wrong}' in error, "
                        f"got: {step_err[:200]}"
                    ),
                }
            chain.append({
                "turn": turn_idx,
                "state": f"fixed_{wrong_token.rstrip(';')}",
                "error": step_err,
                "contains": next_wrong,
            })

    return {"ok": True, "chain": chain, "mutated_text": mutated}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source_text = SOURCE_MODEL.read_text(encoding="utf-8")

    candidates = []
    results = []

    for spec in MUTATION_SPECS:
        cid = spec["candidate_id"]
        print(f"\n[{cid}] {spec['description']}")
        result = _verify_candidate(spec, source_text)

        if result["ok"]:
            print(f"  ✓ masking chain verified ({len(spec['replacements'])} turns)")
            for step in result["chain"]:
                if step["turn"] == 0:
                    print(f"    turn 0 (mutated): error contains '{step['contains']}'")
                elif step.get("pass"):
                    print(f"    turn {step['turn']}: PASS")
                else:
                    print(f"    turn {step['turn']} (after fix): error contains '{step['contains']}'")

            # Save mutated model file
            mut_path = OUT_DIR / f"{cid}.mo"
            mut_path.write_text(result["mutated_text"], encoding="utf-8")

            candidates.append({
                "candidate_id": cid,
                "description": spec["description"],
                "expected_turns": spec["expected_turns"],
                "source_model_path": str(SOURCE_MODEL),
                "mutated_model_path": str(mut_path),
                "failure_type": "model_check_error",
                "expected_stage": "check",
                "wrong_tokens": [r[1] for r in spec["replacements"]],
                "surface_fix_sequence": [
                    {"wrong": r[1], "correct": r[0]} for r in spec["replacements"]
                ],
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
    print(f"  candidates written to: {OUT_DIR}/candidates.jsonl")


if __name__ == "__main__":
    main()
