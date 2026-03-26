"""
agent_modelica_gf_hardpack_runner_v1.py
Run the GateForge executor on every case in a hardpack JSON and produce
a results file compatible with agent_modelica_generalization_benchmark_v1.

Schema of output JSON:
    {
        "schema_version": "agent_modelica_gf_hardpack_runner_v1",
        "generated_at_utc": "...",
        "metrics": {
            "total": N,
            "success": K,
            "failure": N-K,
            "repair_rate": 0.xx,
            "by_failure_type": {...},
            "by_scale": {...}
        },
        "results": [
            {
                "mutation_id": "...",
                "target_scale": "...",
                "expected_failure_type": "...",
                "success": true/false,
                "executor_status": "PASS"/"FAILED",
                "elapsed_sec": 12.3,
                "error": null / "missing_file" / "subprocess_error" / ...
            },
            ...
        ]
    }

The `metrics` dict is consumed directly by agent_modelica_generalization_benchmark_v1
when passed via --gateforge-results.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def infer_project_root_from_pack(pack_path: str) -> Path:
    """Infer project root by walking upward from the hardpack location."""
    pack_parent = Path(str(pack_path or "")).resolve().parent
    for candidate in [pack_parent, *pack_parent.parents]:
        if (candidate / ".git").exists():
            return candidate
    return pack_parent.parent if pack_parent.parent != pack_parent else pack_parent


def resolve_case_path(pack_path: str, case: dict, key: str) -> Path:
    """Resolve a case file path relative to the inferred project root."""
    raw = str(case.get(key, "") or "").strip()
    if not raw:
        return Path("")
    path = Path(raw)
    if path.is_absolute():
        return path
    return infer_project_root_from_pack(pack_path) / path


def validate_hardpack_cases(pack_path: str, cases: list[dict]) -> dict:
    """Validate that every case points to an existing mutated model file."""
    missing_cases: list[dict] = []
    for idx, case in enumerate(cases, 1):
        mutation_id = str(case.get("mutation_id", "") or f"case_{idx}")
        resolved = resolve_case_path(pack_path, case, "mutated_model_path")
        if not str(resolved) or not resolved.exists():
            missing_cases.append(
                {
                    "mutation_id": mutation_id,
                    "expected_failure_type": str(case.get("expected_failure_type", "") or ""),
                    "target_scale": str(case.get("target_scale", "") or ""),
                    "mutated_model_path": str(case.get("mutated_model_path", "") or ""),
                    "resolved_mutated_model_path": str(resolved),
                }
            )

    total = len(cases)
    missing = len(missing_cases)
    return {
        "status": "PASS" if missing == 0 else "FAIL",
        "is_complete": missing == 0,
        "total_cases": total,
        "missing_mutated_model_count": missing,
        "present_mutated_model_count": total - missing,
        "missing_cases": missing_cases,
    }


def _load_hardpack(pack_path: str, max_cases: int = 0) -> tuple[list[dict], list[str]]:
    """Load hardpack cases and optional library_load_models list.

    Returns ``(cases, extra_model_loads)`` where *extra_model_loads* is the
    value of the optional ``library_load_models`` key at the hardpack root
    (e.g. ``["AixLib"]`` for AixLib zero-shot cases).
    """
    with open(pack_path, encoding="utf-8") as f:
        hp = json.load(f)
    cases = [c for c in hp.get("cases", []) if isinstance(c, dict)]
    if max_cases and max_cases > 0:
        cases = cases[:max_cases]
    extra = [str(m) for m in hp.get("library_load_models", []) if str(m or "").strip()]
    return cases, extra


def _run_one_case(
    case: dict,
    pack_path: str,
    docker_image: str,
    planner_backend: str,
    max_rounds: int,
    timeout_sec: int,
    extra_model_loads: list[str] | None = None,
    experience_replay: str = "off",
    experience_source: str = "",
    planner_experience_injection: str = "off",
    planner_experience_max_tokens: int = 400,
) -> dict:
    """Run the GateForge executor on a single hardpack case.

    Returns a result dict with at least:
        mutation_id, target_scale, expected_failure_type,
        success (bool), executor_status (str), elapsed_sec (float),
        error (str | None)
    """
    mutation_id = case.get("mutation_id", "")
    target_scale = case.get("target_scale", "")
    expected_failure_type = case.get("expected_failure_type", "")
    mutated_model_path = str(resolve_case_path(pack_path, case, "mutated_model_path"))
    source_model_path = str(resolve_case_path(pack_path, case, "source_model_path"))
    expected_stage = case.get("expected_stage", "")

    base = {
        "mutation_id": mutation_id,
        "target_scale": target_scale,
        "expected_failure_type": expected_failure_type,
    }

    if not mutated_model_path or not Path(mutated_model_path).exists():
        return {
            **base,
            "success": False,
            "executor_status": "FAILED",
            "elapsed_sec": 0.0,
            "error": "missing_file",
        }

    with tempfile.NamedTemporaryFile(
        suffix=".json", delete=False, mode="w", encoding="utf-8"
    ) as tmp:
        out_path = tmp.name

    try:
        cmd = [
            sys.executable,
            "-m",
            "gateforge.agent_modelica_live_executor_gemini_v1",
            "--task-id", mutation_id,
            "--failure-type", expected_failure_type,
            "--expected-stage", expected_stage,
            "--mutated-model-path", mutated_model_path,
            "--backend", "openmodelica_docker",
            "--docker-image", docker_image,
            "--planner-backend", planner_backend,
            "--max-rounds", str(max_rounds),
            "--timeout-sec", str(timeout_sec),
            "--out", out_path,
        ]
        if str(experience_replay or "off") == "on":
            cmd += ["--experience-replay", "on"]
        if str(experience_source or "").strip():
            cmd += ["--experience-source", str(experience_source)]
        if str(planner_experience_injection or "off") == "on":
            cmd += ["--planner-experience-injection", "on"]
        if int(planner_experience_max_tokens or 0) > 0:
            cmd += ["--planner-experience-max-tokens", str(int(planner_experience_max_tokens))]
        if source_model_path and Path(source_model_path).exists():
            cmd += ["--source-model-path", source_model_path]
        for m in extra_model_loads or []:
            cmd += ["--extra-model-load", m]

        t0 = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_sec + 60,  # generous subprocess timeout
        )
        elapsed = round(time.time() - t0, 2)

        if result.returncode != 0:
            return {
                **base,
                "success": False,
                "executor_status": "FAILED",
                "elapsed_sec": elapsed,
                "error": f"subprocess_exit_{result.returncode}",
                "stderr_tail": result.stderr[-500:] if result.stderr else "",
            }

        try:
            payload = json.loads(Path(out_path).read_text(encoding="utf-8"))
        except Exception as exc:
            # Executor may print JSON to stdout
            try:
                payload = json.loads(result.stdout)
            except Exception:
                return {
                    **base,
                    "success": False,
                    "executor_status": "FAILED",
                    "elapsed_sec": elapsed,
                    "error": f"output_parse_error: {exc}",
                }

        executor_status = str(payload.get("executor_status", "FAILED"))
        success = executor_status.upper() == "PASS"
        return {
            **base,
            "success": success,
            "executor_status": executor_status,
            "elapsed_sec": elapsed,
            "error": None,
            "check_model_pass": payload.get("check_model_pass"),
            "simulate_pass": payload.get("simulate_pass"),
            "rounds_used": len(payload.get("attempts", [])),
            "experience_replay": payload.get("experience_replay") or {},
        }

    except subprocess.TimeoutExpired:
        return {
            **base,
            "success": False,
            "executor_status": "FAILED",
            "elapsed_sec": float(timeout_sec + 60),
            "error": "subprocess_timeout",
        }
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass


def _compute_metrics(results: list[dict]) -> dict:
    total = len(results)
    success = sum(1 for r in results if r.get("success"))
    failure = total - success
    repair_rate = round(success / total, 4) if total else 0.0

    by_failure_type: dict[str, dict] = {}
    by_scale: dict[str, dict] = {}

    for r in results:
        ft = r.get("expected_failure_type", "unknown")
        sc = r.get("target_scale", "unknown")
        ok = bool(r.get("success"))

        for key, bucket_map in [(ft, by_failure_type), (sc, by_scale)]:
            if key not in bucket_map:
                bucket_map[key] = {"total": 0, "success": 0, "repair_rate": 0.0}
            bucket_map[key]["total"] += 1
            if ok:
                bucket_map[key]["success"] += 1

    for bm in list(by_failure_type.values()) + list(by_scale.values()):
        bm["repair_rate"] = round(bm["success"] / bm["total"], 4) if bm["total"] else 0.0

    return {
        "total": total,
        "success": success,
        "failure": failure,
        "repair_rate": repair_rate,
        "by_failure_type": by_failure_type,
        "by_scale": by_scale,
    }


def run_batch(
    pack_path: str,
    docker_image: str = "openmodelica/openmodelica:v1.26.1-minimal",
    planner_backend: str = "gemini",
    max_rounds: int = 8,
    timeout_sec: int = 300,
    max_cases: int = 0,
    out_path: str = "",
    allow_missing_files: bool = False,
    experience_replay: str = "off",
    experience_source: str = "",
    planner_experience_injection: str = "off",
    planner_experience_max_tokens: int = 400,
) -> dict:
    """Run GateForge executor on all hardpack cases and return summary dict."""
    cases, extra_model_loads = _load_hardpack(pack_path, max_cases)
    pack_validation = validate_hardpack_cases(pack_path, cases)
    if not pack_validation["is_complete"] and not allow_missing_files:
        summary = {
            "schema_version": "agent_modelica_gf_hardpack_runner_v1",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "error": "hardpack_incomplete",
            "pack_path": pack_path,
            "planner_backend": planner_backend,
            "experience_replay": str(experience_replay or "off"),
            "experience_source": str(experience_source or ""),
            "planner_experience_injection": str(planner_experience_injection or "off"),
            "planner_experience_max_tokens": int(planner_experience_max_tokens or 0),
            "max_rounds": max_rounds,
            "timeout_sec": timeout_sec,
            "pack_validation": pack_validation,
            "metrics": _compute_metrics([]),
            "results": [],
        }
        print(
            f"[GF-batch] FAIL: hardpack incomplete "
            f"({pack_validation['missing_mutated_model_count']}/{pack_validation['total_cases']} missing)",
            file=sys.stderr,
        )
        if out_path:
            Path(out_path).write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(f"[GF-batch] Results written to {out_path}", file=sys.stderr)
        return summary

    total = len(cases)
    results = []

    print(f"[GF-batch] Running {total} cases | backend={planner_backend} | "
          f"max_rounds={max_rounds} | timeout={timeout_sec}s", file=sys.stderr)
    if extra_model_loads:
        print(f"[GF-batch] Extra model loads: {extra_model_loads}", file=sys.stderr)

    for i, case in enumerate(cases, 1):
        mid = case.get("mutation_id", f"case_{i}")
        print(f"[GF-batch] [{i}/{total}] {mid} ...", end=" ", file=sys.stderr, flush=True)
        r = _run_one_case(case, pack_path, docker_image, planner_backend, max_rounds, timeout_sec,
                          extra_model_loads=extra_model_loads,
                          experience_replay=str(experience_replay or "off"),
                          experience_source=str(experience_source or ""),
                          planner_experience_injection=str(planner_experience_injection or "off"),
                          planner_experience_max_tokens=int(planner_experience_max_tokens or 0))
        results.append(r)
        status_str = "OK" if r["success"] else f"FAIL({r.get('error') or r.get('executor_status')})"
        print(f"{status_str} ({r['elapsed_sec']:.1f}s)", file=sys.stderr)

    metrics = _compute_metrics(results)
    print(
        f"[GF-batch] Done: {metrics['success']}/{metrics['total']} = "
        f"{metrics['repair_rate']:.1%}",
        file=sys.stderr,
    )

    summary = {
        "schema_version": "agent_modelica_gf_hardpack_runner_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "pack_path": pack_path,
        "planner_backend": planner_backend,
        "experience_replay": str(experience_replay or "off"),
        "experience_source": str(experience_source or ""),
        "planner_experience_injection": str(planner_experience_injection or "off"),
        "planner_experience_max_tokens": int(planner_experience_max_tokens or 0),
        "max_rounds": max_rounds,
        "timeout_sec": timeout_sec,
        "pack_validation": pack_validation,
        "metrics": metrics,
        "results": results,
    }

    if out_path:
        Path(out_path).write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"[GF-batch] Results written to {out_path}", file=sys.stderr)

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="GateForge hardpack batch runner v1")
    parser.add_argument("--pack", required=True, help="Path to hardpack JSON")
    parser.add_argument(
        "--planner-backend",
        default="gemini",
        choices=["auto", "gemini", "openai", "rule"],
    )
    parser.add_argument("--docker-image", default="openmodelica/openmodelica:v1.26.1-minimal")
    parser.add_argument("--max-rounds", type=int, default=8)
    parser.add_argument("--timeout-sec", type=int, default=300)
    parser.add_argument("--max-cases", type=int, default=0, help="Cap cases (0 = all)")
    parser.add_argument("--experience-replay", choices=["on", "off"], default="off")
    parser.add_argument("--experience-source", default="")
    parser.add_argument("--planner-experience-injection", choices=["on", "off"], default="off")
    parser.add_argument("--planner-experience-max-tokens", type=int, default=400)
    parser.add_argument("--out", default="", help="Output JSON path")
    parser.add_argument(
        "--allow-missing-files",
        action="store_true",
        help="Continue even when the hardpack references missing mutated model files",
    )
    args = parser.parse_args()

    summary = run_batch(
        pack_path=args.pack,
        docker_image=args.docker_image,
        planner_backend=args.planner_backend,
        max_rounds=args.max_rounds,
        timeout_sec=args.timeout_sec,
        max_cases=args.max_cases,
        out_path=args.out,
        allow_missing_files=args.allow_missing_files,
        experience_replay=str(args.experience_replay or "off"),
        experience_source=str(args.experience_source or ""),
        planner_experience_injection=str(args.planner_experience_injection or "off"),
        planner_experience_max_tokens=int(args.planner_experience_max_tokens or 0),
    )
    print(json.dumps({
        "status": summary.get("status", "OK"),
        "repair_rate": summary["metrics"]["repair_rate"],
        "success": summary["metrics"]["success"],
        "total": summary["metrics"]["total"],
        "error": summary.get("error"),
    }))
    if summary.get("status") == "FAIL":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
