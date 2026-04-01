#!/usr/bin/env python3
"""
Block A GateForge runner for v0.3.5 dual-layer candidates.

Reads each task JSON from the Block A artifacts directory, writes model
texts to temp files, runs the GateForge executor, and collects planner
evidence (planner_invoked, rounds_used, resolution_path, success).

Usage:
  source .env
  python3 scripts/block_a_gf_run_v0_3_5.py

Requires:
  GEMINI_API_KEY or OPENAI_API_KEY set in environment
  Docker running (for OMC backend)
"""

import sys
import os
import json
import pathlib
import subprocess
import tempfile
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CANDIDATES_DIR = REPO_ROOT / "artifacts" / "agent_modelica_block_a_dual_layer_candidates_v0_3_5"

# Load .env before checking API keys (same logic as l2_plan_replan_engine_v1)
def _load_dotenv() -> None:
    for env_path in [pathlib.Path.cwd() / ".env", REPO_ROOT / ".env"]:
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
            break

_load_dotenv()
RESULTS_DIR = REPO_ROOT / "artifacts" / "agent_modelica_block_a_gf_results_v0_3_5"

DOCKER_IMAGE = os.environ.get(
    "GATEFORGE_DOCKER_IMAGE", "openmodelica/openmodelica:v1.26.1-minimal"
)

# Pick planner backend based on available key
def _planner_backend() -> str:
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return None


def run_one(task_path: pathlib.Path, out_dir: pathlib.Path) -> dict:
    task = json.loads(task_path.read_text())
    task_id = task["task_id"]
    print(f"\n{'='*60}")
    print(f"[{task_id}]")

    with tempfile.TemporaryDirectory(prefix="gf_run_") as tmpdir:
        tmp = pathlib.Path(tmpdir)

        source_mo = tmp / "source_model.mo"
        mutated_mo = tmp / "mutated_model.mo"
        source_mo.write_text(task["source_model_text"], encoding="utf-8")
        mutated_mo.write_text(task["mutated_model_text"], encoding="utf-8")

        result_file = out_dir / f"{task_id}_result.json"

        cmd = [
            sys.executable, "-m",
            "gateforge.agent_modelica_live_executor_gemini_v1",
            "--task-id", task_id,
            "--failure-type", task.get("declared_failure_type", "post_restore_init_residual"),
            "--expected-stage", task.get("expected_stage", "simulate"),
            "--mutated-model-path", str(mutated_mo),
            "--source-model-path", str(source_mo),
            "--backend", "openmodelica_docker",
            "--docker-image", DOCKER_IMAGE,
            "--planner-backend", _planner_backend(),
            "--max-rounds", "5",
            "--simulate-stop-time", "10.0",
            "--simulate-intervals", "500",
            "--out", str(result_file),
        ]

        print(f"  planner-backend: {_planner_backend()}")
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(REPO_ROOT),
                env={**os.environ, "PATH": "/usr/local/bin:" + os.environ.get("PATH", "")},
            )
        except subprocess.TimeoutExpired:
            elapsed = time.time() - t0
            print(f"  TIMEOUT after {elapsed:.0f}s")
            return {"task_id": task_id, "verdict": "TIMEOUT", "elapsed_sec": elapsed}

        elapsed = time.time() - t0
        print(f"  elapsed: {elapsed:.1f}s  rc={proc.returncode}")

        # Parse executor output JSON if written
        result_json = None
        for candidate in sorted(out_dir.glob(f"{task_id}*.json")):
            try:
                result_json = json.loads(candidate.read_text())
                break
            except Exception:
                pass

        if result_json:
            planner_invoked = result_json.get("planner_invoked")
            rounds_used = result_json.get("rounds_used")
            resolution_path = result_json.get("resolution_path")
            success = result_json.get("success") or result_json.get("executor_status") == "PASS"
            print(f"  planner_invoked={planner_invoked}  rounds={rounds_used}  "
                  f"resolution={resolution_path}  success={success}")
            return {
                "task_id": task_id,
                "verdict": "PASS" if success else "FAIL",
                "planner_invoked": planner_invoked,
                "rounds_used": rounds_used,
                "resolution_path": resolution_path,
                "elapsed_sec": elapsed,
            }

        # Fallback: parse stdout
        if proc.returncode != 0:
            print(f"  STDERR: {proc.stderr[-400:]!r}")
        stdout = proc.stdout + proc.stderr
        print(f"  (no structured output found; stdout snippet: {stdout[:200]!r})")
        return {
            "task_id": task_id,
            "verdict": "UNKNOWN",
            "rc": proc.returncode,
            "elapsed_sec": elapsed,
        }


def main():
    backend = _planner_backend()
    if not backend:
        print("ERROR: Set GEMINI_API_KEY or OPENAI_API_KEY before running.")
        print("  source .env  # or export GEMINI_API_KEY=xxx")
        return 1

    candidates = sorted(CANDIDATES_DIR.glob("*.json"))
    candidates = [c for c in candidates if c.stem != "lane_summary"]
    if not candidates:
        print(f"No candidate JSONs found in {CANDIDATES_DIR}")
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Running GateForge on {len(candidates)} candidates")
    print(f"  planner backend: {backend}")
    print(f"  results dir: {RESULTS_DIR}")

    all_results = []
    for task_path in candidates:
        r = run_one(task_path, RESULTS_DIR)
        all_results.append(r)

    # Summary
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    total = len(all_results)
    passed = sum(1 for r in all_results if r.get("verdict") == "PASS")
    planner_invoked = sum(1 for r in all_results if r.get("planner_invoked") is True)
    det_only = sum(1 for r in all_results
                   if r.get("resolution_path") == "deterministic_rule_only")

    print(f"  success rate:          {passed}/{total} ({100*passed//total if total else 0}%)")
    print(f"  planner_invoked:       {planner_invoked}/{total} ({100*planner_invoked//total if total else 0}%)")
    print(f"  deterministic_only:    {det_only}/{total} ({100*det_only//total if total else 0}%)")
    print()
    for r in all_results:
        print(f"  {r['task_id']:40s}  {r.get('verdict','?'):7s}  "
              f"planner={r.get('planner_invoked','?')}  "
              f"rounds={r.get('rounds_used','?')}  "
              f"path={r.get('resolution_path','?')}")

    summary = {
        "total": total,
        "passed": passed,
        "planner_invoked_count": planner_invoked,
        "planner_invoked_pct": round(100 * planner_invoked / total, 1) if total else 0,
        "deterministic_only_count": det_only,
        "deterministic_only_pct": round(100 * det_only / total, 1) if total else 0,
        "sc1_deterministic_le_40pct": (det_only / total <= 0.4) if total else False,
        "results": all_results,
    }

    summary_path = RESULTS_DIR / "run_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary saved to: {summary_path}")
    print(f"\nSC1 (deterministic_only <= 40%): {'PASS' if summary['sc1_deterministic_le_40pct'] else 'FAIL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
