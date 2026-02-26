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


def _write_json(path: str, payload: dict) -> None:
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Anchor Benchmark Artifact v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- anchor_ready: `{payload.get('anchor_ready')}`",
        f"- anchor_score: `{payload.get('anchor_score')}`",
        f"- baseline_id: `{payload.get('baseline_id')}`",
        f"- reproducible_command: `{payload.get('reproducible_command')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build externally shareable anchor benchmark artifact")
    parser.add_argument("--failure-baseline-pack-summary", required=True)
    parser.add_argument("--failure-distribution-quality-gate", required=True)
    parser.add_argument("--external-proof-score", required=True)
    parser.add_argument("--reproducible-command", default="bash scripts/demo_dataset_failure_baseline_pack_v1.sh")
    parser.add_argument("--out", default="artifacts/dataset_anchor_benchmark_artifact_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    baseline = _load_json(args.failure_baseline_pack_summary)
    gate = _load_json(args.failure_distribution_quality_gate)
    proof = _load_json(args.external_proof_score)

    reasons: list[str] = []
    if not baseline:
        reasons.append("baseline_summary_missing")
    if not gate:
        reasons.append("quality_gate_missing")
    if not proof:
        reasons.append("external_proof_score_missing")

    baseline_status = str(baseline.get("status") or "UNKNOWN")
    gate_result = str(gate.get("gate_result") or gate.get("status") or "UNKNOWN")
    proof_score = _to_float(proof.get("proof_score", 0.0))

    score = 0.0
    score += 35.0 if baseline_status == "PASS" else 20.0 if baseline_status == "NEEDS_REVIEW" else 0.0
    score += 35.0 if gate_result == "PASS" else 18.0 if gate_result == "NEEDS_REVIEW" else 0.0
    score += min(30.0, max(0.0, proof_score * 0.3))
    anchor_score = round(score, 2)

    anchor_ready = anchor_score >= 70.0 and not reasons

    status = "PASS" if anchor_ready else "NEEDS_REVIEW"
    if reasons:
        status = "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "anchor_ready": anchor_ready,
        "anchor_score": anchor_score,
        "baseline_id": str(baseline.get("baseline_id") or "unknown"),
        "total_selected_cases": int(baseline.get("total_selected_cases") or 0),
        "gate_result": gate_result,
        "proof_score": proof_score,
        "reproducible_command": args.reproducible_command,
        "reasons": sorted(set(reasons)),
        "sources": {
            "failure_baseline_pack_summary": args.failure_baseline_pack_summary,
            "failure_distribution_quality_gate": args.failure_distribution_quality_gate,
            "external_proof_score": args.external_proof_score,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "anchor_ready": anchor_ready, "anchor_score": anchor_score}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
