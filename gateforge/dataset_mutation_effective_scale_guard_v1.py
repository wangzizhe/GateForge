from __future__ import annotations

import argparse
import json
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


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Mutation Effective Scale Guard v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- generated_mutations: `{payload.get('generated_mutations')}`",
        f"- reproducible_mutations: `{payload.get('reproducible_mutations')}`",
        f"- authenticity_multiplier: `{payload.get('authenticity_multiplier')}`",
        f"- effective_reproducible_mutations: `{payload.get('effective_reproducible_mutations')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute effective mutation scale after authenticity discounting")
    parser.add_argument("--mutation-pack-summary", required=True)
    parser.add_argument("--mutation-real-runner-summary", required=True)
    parser.add_argument("--mutation-signature-uniqueness-summary", required=True)
    parser.add_argument("--mutation-execution-authenticity-summary", required=True)
    parser.add_argument("--mutation-failure-signal-authenticity-summary", required=True)
    parser.add_argument("--min-authenticity-multiplier", type=float, default=0.01)
    parser.add_argument("--min-effective-reproducible-mutations", type=int, default=1)
    parser.add_argument("--out", default="artifacts/dataset_mutation_effective_scale_guard_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    pack = _load_json(args.mutation_pack_summary)
    realrun = _load_json(args.mutation_real_runner_summary)
    signature = _load_json(args.mutation_signature_uniqueness_summary)
    exec_auth = _load_json(args.mutation_execution_authenticity_summary)
    failure_auth = _load_json(args.mutation_failure_signal_authenticity_summary)

    reasons: list[str] = []
    if not pack:
        reasons.append("mutation_pack_summary_missing")
    if not realrun:
        reasons.append("mutation_real_runner_summary_missing")
    if not signature:
        reasons.append("mutation_signature_uniqueness_summary_missing")
    if not exec_auth:
        reasons.append("mutation_execution_authenticity_summary_missing")
    if not failure_auth:
        reasons.append("mutation_failure_signal_authenticity_summary_missing")

    generated_mutations = _to_int(pack.get("total_mutations", 0))
    reproducible_mutations = _to_int(realrun.get("executed_count", 0))

    signature_unique_ratio = _clamp01(_to_float(signature.get("unique_signature_ratio_pct", 0.0)) / 100.0)
    solver_ratio = _clamp01(_to_float(exec_auth.get("solver_command_ratio_pct", 0.0)) / 100.0)
    failure_signal_ratio = _clamp01(_to_float(failure_auth.get("failure_signal_ratio_pct", 0.0)) / 100.0)

    authenticity_multiplier = round(signature_unique_ratio * solver_ratio * failure_signal_ratio, 8)
    effective_reproducible_mutations = int(round(reproducible_mutations * authenticity_multiplier))
    effective_vs_generated_ratio_pct = round(
        (effective_reproducible_mutations / generated_mutations) * 100.0, 4
    ) if generated_mutations > 0 else 0.0

    alerts: list[str] = []
    if authenticity_multiplier < float(args.min_authenticity_multiplier):
        alerts.append("authenticity_multiplier_below_threshold")
    if effective_reproducible_mutations < int(args.min_effective_reproducible_mutations):
        alerts.append("effective_reproducible_mutations_below_threshold")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "generated_mutations": generated_mutations,
        "reproducible_mutations": reproducible_mutations,
        "signature_unique_ratio": signature_unique_ratio,
        "solver_ratio": solver_ratio,
        "failure_signal_ratio": failure_signal_ratio,
        "authenticity_multiplier": authenticity_multiplier,
        "effective_reproducible_mutations": effective_reproducible_mutations,
        "effective_vs_generated_ratio_pct": effective_vs_generated_ratio_pct,
        "thresholds": {
            "min_authenticity_multiplier": float(args.min_authenticity_multiplier),
            "min_effective_reproducible_mutations": int(args.min_effective_reproducible_mutations),
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_pack_summary": args.mutation_pack_summary,
            "mutation_real_runner_summary": args.mutation_real_runner_summary,
            "mutation_signature_uniqueness_summary": args.mutation_signature_uniqueness_summary,
            "mutation_execution_authenticity_summary": args.mutation_execution_authenticity_summary,
            "mutation_failure_signal_authenticity_summary": args.mutation_failure_signal_authenticity_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "effective_reproducible_mutations": effective_reproducible_mutations,
                "authenticity_multiplier": authenticity_multiplier,
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
