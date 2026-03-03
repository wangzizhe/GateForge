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


def _to_float(v: object) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    return 0.0


def _to_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    return 0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _gate(observed: float, threshold: float, *, mode: str = "min") -> str:
    if mode == "max":
        return "PASS" if observed <= threshold else "FAIL"
    return "PASS" if observed >= threshold else "FAIL"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Large Model Authenticity Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- large_model_authenticity_score: `{payload.get('large_model_authenticity_score')}`",
        f"- failed_gate_count: `{payload.get('failed_gate_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate large-model authenticity using executable-truth + depth + provenance signals")
    parser.add_argument("--large-model-executable-truth-summary", required=True)
    parser.add_argument("--mutation-effective-depth-summary", required=True)
    parser.add_argument("--mutation-source-provenance-summary", required=True)
    parser.add_argument("--mutation-authentic-scale-score-summary", default=None)
    parser.add_argument("--min-large-model-count", type=int, default=1)
    parser.add_argument("--min-large-executable-real-rate-pct", type=float, default=70.0)
    parser.add_argument("--min-large-effective-depth-ratio-pct", type=float, default=40.0)
    parser.add_argument("--min-source-registry-match-ratio-pct", type=float, default=80.0)
    parser.add_argument("--min-large-model-authenticity-score", type=float, default=65.0)
    parser.add_argument("--out", default="artifacts/dataset_large_model_authenticity_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    large_truth = _load_json(args.large_model_executable_truth_summary)
    depth = _load_json(args.mutation_effective_depth_summary)
    source = _load_json(args.mutation_source_provenance_summary)
    authentic_scale = _load_json(args.mutation_authentic_scale_score_summary)

    reasons: list[str] = []
    if not large_truth:
        reasons.append("large_model_executable_truth_summary_missing")
    if not depth:
        reasons.append("mutation_effective_depth_summary_missing")
    if not source:
        reasons.append("mutation_source_provenance_summary_missing")

    large_model_count = _to_int(large_truth.get("large_model_count", 0))
    large_executable_real_rate_pct = _clamp(_to_float(large_truth.get("large_executable_real_rate_pct", 0.0)), 0.0, 100.0)
    large_effective_depth_ratio_pct = _clamp(_to_float(depth.get("large_models_meeting_effective_depth_ratio_pct", 0.0)), 0.0, 100.0)
    source_registry_match_ratio_pct = _clamp(_to_float(source.get("registry_match_ratio_pct", 0.0)), 0.0, 100.0)
    global_authentic_scale_score = _clamp(_to_float(authentic_scale.get("authentic_scale_score", 0.0)), 0.0, 100.0)

    large_model_authenticity_score = round(
        large_executable_real_rate_pct * 0.50
        + large_effective_depth_ratio_pct * 0.30
        + source_registry_match_ratio_pct * 0.15
        + global_authentic_scale_score * 0.05,
        2,
    )

    gates = {
        "large_model_count": {
            "critical": True,
            "mode": "min",
            "threshold": int(args.min_large_model_count),
            "observed": large_model_count,
            "status": _gate(float(large_model_count), float(args.min_large_model_count), mode="min"),
        },
        "large_executable_real_rate_pct": {
            "critical": True,
            "mode": "min",
            "threshold": float(args.min_large_executable_real_rate_pct),
            "observed": round(large_executable_real_rate_pct, 2),
            "status": _gate(large_executable_real_rate_pct, float(args.min_large_executable_real_rate_pct), mode="min"),
        },
        "large_effective_depth_ratio_pct": {
            "critical": False,
            "mode": "min",
            "threshold": float(args.min_large_effective_depth_ratio_pct),
            "observed": round(large_effective_depth_ratio_pct, 2),
            "status": _gate(large_effective_depth_ratio_pct, float(args.min_large_effective_depth_ratio_pct), mode="min"),
        },
        "source_registry_match_ratio_pct": {
            "critical": False,
            "mode": "min",
            "threshold": float(args.min_source_registry_match_ratio_pct),
            "observed": round(source_registry_match_ratio_pct, 2),
            "status": _gate(source_registry_match_ratio_pct, float(args.min_source_registry_match_ratio_pct), mode="min"),
        },
        "large_model_authenticity_score": {
            "critical": False,
            "mode": "min",
            "threshold": float(args.min_large_model_authenticity_score),
            "observed": large_model_authenticity_score,
            "status": _gate(large_model_authenticity_score, float(args.min_large_model_authenticity_score), mode="min"),
        },
    }
    if authentic_scale:
        gates["global_authentic_scale_score"] = {
            "critical": False,
            "mode": "min",
            "threshold": 60.0,
            "observed": round(global_authentic_scale_score, 2),
            "status": _gate(global_authentic_scale_score, 60.0, mode="min"),
        }

    failed_gates = [name for name, gate in gates.items() if str(gate.get("status") or "") == "FAIL"]
    critical_failed_gates = [name for name, gate in gates.items() if bool(gate.get("critical")) and str(gate.get("status") or "") == "FAIL"]

    alerts: list[str] = []
    if str(large_truth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("large_model_executable_truth_not_pass")
    if str(depth.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("mutation_effective_depth_not_pass")
    if str(source.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("mutation_source_provenance_not_pass")
    if authentic_scale and str(authentic_scale.get("status") or "") in {"NEEDS_REVIEW", "FAIL"}:
        alerts.append("mutation_authentic_scale_score_not_pass")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif critical_failed_gates:
        status = "FAIL"
    elif failed_gates or alerts:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "large_model_authenticity_score": large_model_authenticity_score,
        "failed_gate_count": len(failed_gates),
        "critical_failed_gate_count": len(critical_failed_gates),
        "failed_gates": failed_gates,
        "critical_failed_gates": critical_failed_gates,
        "gates": gates,
        "signals": {
            "large_model_count": large_model_count,
            "large_executable_real_rate_pct": round(large_executable_real_rate_pct, 2),
            "large_effective_depth_ratio_pct": round(large_effective_depth_ratio_pct, 2),
            "source_registry_match_ratio_pct": round(source_registry_match_ratio_pct, 2),
            "global_authentic_scale_score": round(global_authentic_scale_score, 2) if authentic_scale else None,
        },
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "large_model_executable_truth_summary": args.large_model_executable_truth_summary,
            "mutation_effective_depth_summary": args.mutation_effective_depth_summary,
            "mutation_source_provenance_summary": args.mutation_source_provenance_summary,
            "mutation_authentic_scale_score_summary": args.mutation_authentic_scale_score_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {
                "status": status,
                "large_model_authenticity_score": large_model_authenticity_score,
                "failed_gate_count": len(failed_gates),
            }
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
