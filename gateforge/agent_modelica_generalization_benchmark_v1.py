"""Generalization-First Benchmark for the GateForge Modelica Agent.

Compares *bare-LLM* single-shot repair (agent_modelica_bare_llm_baseline_v1)
against GateForge full-agent repair on the same hardpack task set, using OMC
as the shared ground-truth validator.

Design (Generalization-First Benchmark Pattern):
- In-distribution track: hardpack cases (MSL-based open-source mutants).
- GateForge results: supplied as pre-computed JSON from an L5 eval run.
- Bare-LLM results: computed here via the baseline runner.
- Verdict: GATEFORGE_ADVANTAGE when agent repair_rate exceeds bare LLM by ≥5pp.

Skill: Trajectory-Grounded Benchmark Pattern
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_bare_llm_baseline_v1 import extract_model_name, run_bare_repair
from .agent_modelica_gf_hardpack_runner_v1 import (
    resolve_case_path,
    validate_hardpack_cases,
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_VERSION = "agent_modelica_generalization_benchmark_v1"

# Minimum repair-rate advantage (percentage points) for GATEFORGE_ADVANTAGE.
_ADVANTAGE_THRESHOLD = 0.05


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def load_hardpack_cases(pack_path: str, max_cases: int = 0) -> list[dict]:
    """Load cases from a hardpack JSON file.

    Returns a list of case dicts.  Each dict contains at minimum:
    ``mutation_id``, ``target_scale``, ``expected_failure_type``,
    ``mutated_model_path``.  Returns ``[]`` when the file is missing.
    """
    p = Path(str(pack_path or ""))
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    cases: list[dict] = []
    if isinstance(data, dict):
        raw = data.get("cases", [])
        if isinstance(raw, list):
            cases = [c for c in raw if isinstance(c, dict)]
    elif isinstance(data, list):
        cases = [c for c in data if isinstance(c, dict)]
    if max_cases and max_cases > 0:
        cases = cases[:max_cases]
    return cases


def load_hardpack_extra_model_loads(pack_path: str) -> list[str]:
    """Return the ``library_load_models`` list from a hardpack JSON (empty if absent)."""
    p = Path(str(pack_path or ""))
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    return [str(m) for m in data.get("library_load_models", []) if str(m or "").strip()]


def compute_metrics(results: list[dict]) -> dict:
    """Compute aggregate repair metrics from a list of repair result dicts.

    Input dicts must have at minimum a ``success`` boolean field.
    Optional fields ``expected_failure_type`` and ``target_scale`` are used
    for per-dimension breakdowns.
    """
    if not results:
        return {
            "total": 0,
            "success": 0,
            "failure": 0,
            "repair_rate": 0.0,
            "by_failure_type": {},
            "by_scale": {},
        }

    total = len(results)
    n_success = sum(1 for r in results if r.get("success"))
    repair_rate = round(n_success / total, 4) if total else 0.0

    by_type: dict[str, dict] = {}
    by_scale: dict[str, dict] = {}

    for r in results:
        ft = str(r.get("expected_failure_type") or r.get("failure_type") or "unknown")
        sc = str(r.get("target_scale") or r.get("scale") or "unknown")
        ok = bool(r.get("success"))

        by_type.setdefault(ft, {"total": 0, "success": 0})
        by_type[ft]["total"] += 1
        if ok:
            by_type[ft]["success"] += 1

        by_scale.setdefault(sc, {"total": 0, "success": 0})
        by_scale[sc]["total"] += 1
        if ok:
            by_scale[sc]["success"] += 1

    for bucket in list(by_type.values()) + list(by_scale.values()):
        t = bucket["total"]
        bucket["repair_rate"] = round(bucket["success"] / t, 4) if t else 0.0

    return {
        "total": total,
        "success": n_success,
        "failure": total - n_success,
        "repair_rate": repair_rate,
        "by_failure_type": by_type,
        "by_scale": by_scale,
    }


def verdict(bare_repair_rate: float, gf_repair_rate: float | None) -> str:
    """Return a comparison verdict.

    Values:
    - ``GATEFORGE_ADVANTAGE``: agent repair_rate ≥ bare + 5pp.
    - ``INCONCLUSIVE``: difference is within ±5pp.
    - ``BARE_LLM_BETTER``: bare LLM repair_rate ≥ agent + 5pp.
    - ``BARE_LLM_ONLY``: no GateForge results provided yet (collecting baseline).
    """
    if gf_repair_rate is None:
        return "BARE_LLM_ONLY"
    diff = float(gf_repair_rate) - float(bare_repair_rate)
    if diff >= _ADVANTAGE_THRESHOLD:
        return "GATEFORGE_ADVANTAGE"
    if diff <= -_ADVANTAGE_THRESHOLD:
        return "BARE_LLM_BETTER"
    return "INCONCLUSIVE"


def render_markdown(summary: dict) -> str:
    """Render a benchmark summary dict as a GitHub-flavoured Markdown report."""
    v = str(summary.get("verdict", ""))
    status = str(summary.get("status", ""))
    bm: dict = summary.get("bare_llm_metrics") or {}
    gfm: dict | None = summary.get("gateforge_metrics")

    lines: list[str] = [
        f"# {SCHEMA_VERSION}",
        "",
        f"- generated_at_utc: `{summary.get('generated_at_utc', '')}`",
        f"- status: `{status}`",
        f"- verdict: `{v}`",
        "",
        "## Bare-LLM Baseline",
        "",
        f"| metric | value |",
        f"|--------|-------|",
        f"| total | {bm.get('total', 0)} |",
        f"| success | {bm.get('success', 0)} |",
        f"| failure | {bm.get('failure', 0)} |",
        f"| repair_rate | {bm.get('repair_rate', 0.0):.1%} |",
        "",
    ]

    if gfm:
        lines += [
            "## GateForge Agent",
            "",
            "| metric | value |",
            "|--------|-------|",
            f"| total | {gfm.get('total', 0)} |",
            f"| success | {gfm.get('success', 0)} |",
            f"| repair_rate | {gfm.get('repair_rate', 0.0):.1%} |",
            "",
        ]

    by_type: dict = bm.get("by_failure_type") or {}
    if by_type:
        lines += [
            "## Bare-LLM by Failure Type",
            "",
            "| failure_type | total | success | repair_rate |",
            "|---|---|---|---|",
        ]
        for ft, d in sorted(by_type.items()):
            lines.append(
                f"| {ft} | {d['total']} | {d['success']} | {d['repair_rate']:.1%} |"
            )
        lines.append("")

    by_scale: dict = bm.get("by_scale") or {}
    if by_scale:
        lines += [
            "## Bare-LLM by Scale",
            "",
            "| scale | total | success | repair_rate |",
            "|---|---|---|---|",
        ]
        for sc, d in sorted(by_scale.items()):
            lines.append(
                f"| {sc} | {d['total']} | {d['success']} | {d['repair_rate']:.1%} |"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def _load_json_safe(path: str) -> dict:
    p = Path(str(path or ""))
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: str, data: object) -> None:
    p = Path(str(path or ""))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Batch benchmark runner
# ---------------------------------------------------------------------------


def run_benchmark(
    *,
    pack_path: str,
    backend: str = "auto",
    out: str = "artifacts/generalization_benchmark/summary.json",
    max_cases: int = 0,
    docker_image: str = "",
    timeout_sec: int = 120,
    gateforge_results_path: str = "",
) -> dict:
    """Run bare-LLM repair on all hardpack cases and produce a comparison report.

    Args:
        pack_path: Path to a hardpack JSON file (e.g. benchmarks/agent_modelica_hardpack_v1.json).
        backend: LLM backend name ("auto", "gemini", "openai", or "rule").
        out: Output path for the JSON summary.
        max_cases: Cap the number of cases (0 = all).
        docker_image: Docker image for OMC (falls back to env var).
        timeout_sec: Per-task timeout in seconds.
        gateforge_results_path: Optional pre-computed GateForge results JSON.

    Returns:
        Summary dict (also written to *out*).
    """
    cases = load_hardpack_cases(pack_path, max_cases=max_cases)
    extra_model_loads = load_hardpack_extra_model_loads(pack_path)
    if not cases:
        summary: dict = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "verdict": "NO_CASES",
            "error": f"no_cases_loaded_from:{pack_path}",
        }
        _write_json(out, summary)
        return summary

    pack_validation = validate_hardpack_cases(pack_path, cases)
    if not pack_validation["is_complete"]:
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "verdict": "PACK_INCOMPLETE",
            "error": (
                "hardpack_incomplete:"
                f"{pack_validation['missing_mutated_model_count']}_missing_mutated_models"
            ),
            "pack_validation": pack_validation,
            "sources": {
                "pack_path": str(pack_path),
                "gateforge_results_path": gateforge_results_path,
            },
        }
        _write_json(out, summary)
        md_path = str(Path(out).with_suffix(".md"))
        Path(md_path).parent.mkdir(parents=True, exist_ok=True)
        Path(md_path).write_text(render_markdown(summary), encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "verdict": "PACK_INCOMPLETE",
                    "missing_mutated_model_count": pack_validation["missing_mutated_model_count"],
                    "total_cases": pack_validation["total_cases"],
                }
            )
        )
        return summary

    bare_results: list[dict] = []
    total = len(cases)
    print(
        f"[Bare-batch] Running {total} cases | backend={backend} | timeout={timeout_sec}s",
        file=sys.stderr,
    )
    if extra_model_loads:
        print(f"[Bare-batch] Extra model loads: {extra_model_loads}", file=sys.stderr)

    for idx, case in enumerate(cases, 1):
        mutated_path = resolve_case_path(pack_path, case, "mutated_model_path")

        base_entry = {
            "mutation_id": str(case.get("mutation_id", "") or ""),
            "target_scale": str(case.get("target_scale", "") or ""),
            "expected_failure_type": str(case.get("expected_failure_type", "") or ""),
        }
        mutation_id = base_entry["mutation_id"] or f"case_{idx}"
        print(
            f"[Bare-batch] [{idx}/{total}] {mutation_id} ...",
            end=" ",
            file=sys.stderr,
            flush=True,
        )

        if not mutated_path.exists():
            print("FAIL(missing_file) (0.0s)", file=sys.stderr)
            bare_results.append(
                {**base_entry, "success": False, "error": f"model_file_not_found:{mutated_path}"}
            )
            continue

        model_text = mutated_path.read_text(encoding="utf-8")
        model_name = extract_model_name(model_text)

        t0 = time.time()
        result = run_bare_repair(
            model_text=model_text,
            model_name=model_name,
            backend=backend,
            docker_image=docker_image,
            timeout_sec=timeout_sec,
            extra_model_loads=extra_model_loads or None,
        )
        elapsed = round(time.time() - t0, 2)
        if result.get("success"):
            status_str = "OK"
        else:
            error = str(result.get("error", "") or "failed")
            status_str = f"FAIL({error})"
        print(f"{status_str} ({elapsed:.1f}s)", file=sys.stderr)
        bare_results.append({**base_entry, **result})

    bare_metrics = compute_metrics(bare_results)
    print(
        f"[Bare-batch] Done: {bare_metrics['success']}/{bare_metrics['total']} = "
        f"{bare_metrics['repair_rate']:.1%}",
        file=sys.stderr,
    )

    # Load optional pre-computed GateForge results
    gf_metrics: dict | None = None
    if gateforge_results_path:
        gf_data = _load_json_safe(gateforge_results_path)
        if gf_data:
            gf_metrics = (
                gf_data.get("metrics")
                if isinstance(gf_data.get("metrics"), dict)
                else gf_data
            )

    bare_rate = bare_metrics["repair_rate"]
    gf_rate: float | None = None
    if isinstance(gf_metrics, dict) and "repair_rate" in gf_metrics:
        try:
            gf_rate = float(gf_metrics["repair_rate"])
        except Exception:
            gf_rate = None

    v = verdict(bare_rate, gf_rate)
    if v == "GATEFORGE_ADVANTAGE":
        status = "PASS"
    elif v == "BARE_LLM_ONLY":
        status = "PASS"  # baseline-collection run; no comparison yet
    elif v == "INCONCLUSIVE":
        status = "NEEDS_REVIEW"
    else:
        status = "FAIL"

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "verdict": v,
        "bare_llm_metrics": bare_metrics,
        "gateforge_metrics": gf_metrics,
        "bare_llm_results": bare_results,
        "pack_validation": pack_validation,
        "sources": {
            "pack_path": str(pack_path),
            "gateforge_results_path": gateforge_results_path,
        },
    }

    _write_json(out, summary)
    md_path = str(Path(out).with_suffix(".md"))
    Path(md_path).parent.mkdir(parents=True, exist_ok=True)
    Path(md_path).write_text(render_markdown(summary), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": status,
                "verdict": v,
                "bare_repair_rate": bare_rate,
                "gateforge_repair_rate": gf_rate,
                "total_cases": bare_metrics["total"],
            }
        )
    )
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GateForge Generalization-First Benchmark v1"
    )
    parser.add_argument("--pack", required=True, help="Path to hardpack JSON")
    parser.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "gemini", "openai", "rule"],
        help="LLM backend",
    )
    parser.add_argument(
        "--gateforge-results",
        default="",
        help="Pre-computed GateForge results JSON (optional)",
    )
    parser.add_argument("--docker-image", default="")
    parser.add_argument("--timeout-sec", type=int, default=120)
    parser.add_argument("--max-cases", type=int, default=0, help="Cap cases (0 = all)")
    parser.add_argument(
        "--out",
        default="artifacts/generalization_benchmark/summary.json",
    )
    args = parser.parse_args()

    run_benchmark(
        pack_path=args.pack,
        backend=args.backend,
        out=args.out,
        max_cases=args.max_cases,
        docker_image=args.docker_image,
        timeout_sec=args.timeout_sec,
        gateforge_results_path=args.gateforge_results,
    )


if __name__ == "__main__":
    main()
