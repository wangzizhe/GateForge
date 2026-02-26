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


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge External Proof Score",
        "",
        f"- status: `{payload.get('status')}`",
        f"- proof_score: `{payload.get('proof_score')}`",
        f"- release_ready: `{payload.get('release_ready')}`",
        f"- confidence_band: `{payload.get('confidence_band')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute external proof score from release manifest and moat forecast")
    parser.add_argument("--evidence-release-manifest", required=True)
    parser.add_argument("--moat-execution-forecast", required=True)
    parser.add_argument("--governance-decision-proofbook", default=None)
    parser.add_argument("--out", default="artifacts/dataset_external_proof_score/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    manifest = _load_json(args.evidence_release_manifest)
    forecast = _load_json(args.moat_execution_forecast)
    proofbook = _load_json(args.governance_decision_proofbook)

    reasons: list[str] = []
    if not manifest:
        reasons.append("manifest_missing")
    if not forecast:
        reasons.append("forecast_missing")

    artifact_count = len(manifest.get("artifacts") or []) if isinstance(manifest.get("artifacts"), list) else 0
    release_ready = bool(manifest.get("release_ready", False))

    projected_moat = _to_float(forecast.get("projected_moat_score_30d", 0.0))
    decision = str(proofbook.get("decision") or "")

    score = 30.0
    score += min(25.0, artifact_count * 6.0)
    score += 20.0 if release_ready else 6.0
    score += min(20.0, projected_moat * 0.25)
    if decision == "PROMOTE":
        score += 8.0
    elif decision == "PROMOTE_WITH_GUARDS":
        score += 4.0

    proof_score = round(_clamp(score), 2)

    confidence_band = "low"
    if proof_score >= 75:
        confidence_band = "high"
    elif proof_score >= 55:
        confidence_band = "medium"

    status = "PASS" if proof_score >= 70 else "NEEDS_REVIEW"
    if reasons:
        status = "FAIL"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "proof_score": proof_score,
        "release_ready": release_ready,
        "confidence_band": confidence_band,
        "artifact_count": artifact_count,
        "projected_moat_score_30d": projected_moat,
        "reasons": sorted(set(reasons)),
        "sources": {
            "evidence_release_manifest": args.evidence_release_manifest,
            "moat_execution_forecast": args.moat_execution_forecast,
            "governance_decision_proofbook": args.governance_decision_proofbook,
        },
    }

    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "proof_score": proof_score, "confidence_band": confidence_band}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
