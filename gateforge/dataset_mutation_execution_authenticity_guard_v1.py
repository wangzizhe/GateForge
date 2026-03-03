from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _ratio_pct(num: int, den: int) -> float:
    if den <= 0:
        return 0.0
    return round((num / den) * 100.0, 4)


def _is_solver_command(command: str) -> bool:
    c = command.lower()
    tokens = (" omc ", "openmodelica", ".mos", "checkmodel(", "simulate(", "buildmodel(")
    cpad = f" {c} "
    return any(t in cpad or t in c for t in tokens)


def _is_probe_command(command: str) -> bool:
    c = command.lower()
    if not ("python -c" in c or "python3 -c" in c):
        return False
    indicators = ("read_text(", "path(", "p.exists()", "exists()", "model ", "end ")
    return sum(1 for x in indicators if x in c) >= 2


def _is_echo_or_print_command(command: str) -> bool:
    c = command.lower().strip()
    if c.startswith("echo ") or c.startswith("printf "):
        return True
    if ("python -c" in c or "python3 -c" in c) and ("print(" in c):
        return True
    return False


def _classify_command(command: str) -> str:
    c = str(command or "").strip()
    if not c:
        return "missing"
    if _is_solver_command(c):
        return "solver"
    if _is_probe_command(c):
        return "probe_only"
    if _is_echo_or_print_command(c):
        return "echo_or_print"
    return "other"


def _has_failure_signal(obs: dict) -> bool:
    rc = obs.get("final_return_code")
    if isinstance(rc, int) and rc != 0:
        return True
    attempts = obs.get("attempts") if isinstance(obs.get("attempts"), list) else []
    for a in attempts:
        if not isinstance(a, dict):
            continue
        if bool(a.get("timed_out")):
            return True
        stderr = str(a.get("stderr") or "").lower()
        if re.search(r"(error|failed|assert|exception|undefined|division)", stderr):
            return True
    return False


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Execution Authenticity Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_mutations: `{payload.get('total_mutations')}`",
        f"- observed_mutations: `{payload.get('observed_mutations')}`",
        f"- solver_command_ratio_pct: `{payload.get('solver_command_ratio_pct')}`",
        f"- probe_only_command_ratio_pct: `{payload.get('probe_only_command_ratio_pct')}`",
        f"- placeholder_executed_ratio_pct: `{payload.get('placeholder_executed_ratio_pct')}`",
        f"- failure_signal_ratio_pct: `{payload.get('failure_signal_ratio_pct')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit mutation execution authenticity beyond raw scale count")
    parser.add_argument("--mutation-manifest", required=True)
    parser.add_argument("--mutation-raw-observations", required=True)
    parser.add_argument("--min-solver-command-ratio-pct", type=float, default=1.0)
    parser.add_argument("--max-probe-only-command-ratio-pct", type=float, default=90.0)
    parser.add_argument("--max-placeholder-executed-ratio-pct", type=float, default=90.0)
    parser.add_argument("--min-observed-coverage-ratio-pct", type=float, default=95.0)
    parser.add_argument("--out", default="artifacts/dataset_mutation_execution_authenticity_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.mutation_manifest)
    raw = _load_json(args.mutation_raw_observations)
    reasons: list[str] = []
    if not manifest:
        reasons.append("mutation_manifest_missing")
    if not raw:
        reasons.append("mutation_raw_observations_missing")

    mutations_raw = manifest.get("mutations") if isinstance(manifest.get("mutations"), list) else []
    mutations = [r for r in mutations_raw if isinstance(r, dict)]
    observations_raw = raw.get("observations") if isinstance(raw.get("observations"), list) else []
    observations = [r for r in observations_raw if isinstance(r, dict)]

    if manifest and not mutations:
        reasons.append("mutation_manifest_empty")
    if raw and not observations:
        reasons.append("mutation_raw_observations_empty")

    by_mutation_id = {str(o.get("mutation_id") or ""): o for o in observations if str(o.get("mutation_id") or "")}

    class_counts: Counter[str] = Counter()
    observed_mutations = 0
    executed_mutations = 0
    placeholder_executed_mutations = 0
    failure_signal_mutations = 0

    for row in mutations:
        mutation_id = str(row.get("mutation_id") or "")
        command = str(row.get("repro_command") or "")
        cls = _classify_command(command)
        class_counts[cls] += 1
        obs = by_mutation_id.get(mutation_id, {})
        if obs:
            observed_mutations += 1
            if str(obs.get("execution_status") or "") == "EXECUTED":
                executed_mutations += 1
                if cls in {"probe_only", "echo_or_print"}:
                    placeholder_executed_mutations += 1
            if _has_failure_signal(obs):
                failure_signal_mutations += 1

    total_mutations = len(mutations)
    solver_command_count = _to_int(class_counts.get("solver"))
    probe_only_command_count = _to_int(class_counts.get("probe_only"))
    echo_or_print_command_count = _to_int(class_counts.get("echo_or_print"))

    solver_command_ratio_pct = _ratio_pct(solver_command_count, total_mutations)
    probe_only_command_ratio_pct = _ratio_pct(probe_only_command_count, total_mutations)
    observed_coverage_ratio_pct = _ratio_pct(observed_mutations, total_mutations)
    placeholder_executed_ratio_pct = _ratio_pct(placeholder_executed_mutations, max(1, executed_mutations))
    failure_signal_ratio_pct = _ratio_pct(failure_signal_mutations, observed_mutations)

    alerts: list[str] = []
    if solver_command_ratio_pct < float(args.min_solver_command_ratio_pct):
        alerts.append("solver_command_ratio_below_threshold")
    if probe_only_command_ratio_pct > float(args.max_probe_only_command_ratio_pct):
        alerts.append("probe_only_command_ratio_above_threshold")
    if placeholder_executed_ratio_pct > float(args.max_placeholder_executed_ratio_pct):
        alerts.append("placeholder_executed_ratio_above_threshold")
    if observed_coverage_ratio_pct < float(args.min_observed_coverage_ratio_pct):
        alerts.append("observed_coverage_ratio_below_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_mutations": total_mutations,
        "observed_mutations": observed_mutations,
        "executed_mutations": executed_mutations,
        "solver_command_count": solver_command_count,
        "probe_only_command_count": probe_only_command_count,
        "echo_or_print_command_count": echo_or_print_command_count,
        "other_command_count": _to_int(class_counts.get("other")),
        "missing_command_count": _to_int(class_counts.get("missing")),
        "solver_command_ratio_pct": solver_command_ratio_pct,
        "probe_only_command_ratio_pct": probe_only_command_ratio_pct,
        "observed_coverage_ratio_pct": observed_coverage_ratio_pct,
        "placeholder_executed_ratio_pct": placeholder_executed_ratio_pct,
        "failure_signal_ratio_pct": failure_signal_ratio_pct,
        "thresholds": {
            "min_solver_command_ratio_pct": float(args.min_solver_command_ratio_pct),
            "max_probe_only_command_ratio_pct": float(args.max_probe_only_command_ratio_pct),
            "max_placeholder_executed_ratio_pct": float(args.max_placeholder_executed_ratio_pct),
            "min_observed_coverage_ratio_pct": float(args.min_observed_coverage_ratio_pct),
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_manifest": args.mutation_manifest,
            "mutation_raw_observations": args.mutation_raw_observations,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "solver_command_ratio_pct": solver_command_ratio_pct,
                "probe_only_command_ratio_pct": probe_only_command_ratio_pct,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
