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


def _status(payload: dict) -> str:
    return str(payload.get("status") or "UNKNOWN")


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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge External Anchor Release Gate v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- gate_decision: `{payload.get('gate_decision')}`",
        f"- release_readiness_score: `{payload.get('release_readiness_score')}`",
        f"- blocker_count: `{payload.get('blocker_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Decide external anchor release readiness from governance evidence and contracts")
    parser.add_argument("--anchor-public-release-summary", required=True)
    parser.add_argument("--moat-public-scoreboard-summary", required=True)
    parser.add_argument("--large-model-benchmark-pack-summary", required=True)
    parser.add_argument("--modelica-library-provenance-guard-summary", required=True)
    parser.add_argument("--optional-ci-contract-summary", required=True)
    parser.add_argument("--out", default="artifacts/dataset_external_anchor_release_gate_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    anchor = _load_json(args.anchor_public_release_summary)
    scoreboard = _load_json(args.moat_public_scoreboard_summary)
    pack = _load_json(args.large_model_benchmark_pack_summary)
    provenance = _load_json(args.modelica_library_provenance_guard_summary)
    contract = _load_json(args.optional_ci_contract_summary)

    reasons: list[str] = []
    if not anchor:
        reasons.append("anchor_public_release_summary_missing")
    if not scoreboard:
        reasons.append("moat_public_scoreboard_summary_missing")
    if not pack:
        reasons.append("large_model_benchmark_pack_summary_missing")
    if not provenance:
        reasons.append("modelica_library_provenance_guard_summary_missing")
    if not contract:
        reasons.append("optional_ci_contract_summary_missing")

    anchor_status = _status(anchor)
    scoreboard_status = _status(scoreboard)
    pack_status = _status(pack)
    provenance_status = _status(provenance)
    contract_status = _status(contract)

    anchor_score = _to_float(anchor.get("public_release_score", 0.0))
    moat_score = _to_float(scoreboard.get("moat_public_score", 0.0))
    pack_score = _to_float(pack.get("pack_readiness_score", 0.0))
    provenance_completeness = _to_float(provenance.get("provenance_completeness_pct", 0.0))
    unknown_license_ratio = _to_float(provenance.get("unknown_license_ratio_pct", 100.0))
    contract_fail_count = _to_int(contract.get("fail_count", 0))

    blockers: list[str] = []
    if contract_status != "PASS" or contract_fail_count > 0:
        blockers.append("optional_ci_contract_not_pass")
    if anchor_status == "FAIL":
        blockers.append("anchor_public_release_failed")
    if scoreboard_status == "FAIL":
        blockers.append("moat_public_scoreboard_failed")
    if pack_status == "FAIL":
        blockers.append("large_model_benchmark_pack_failed")
    if provenance_status == "FAIL":
        blockers.append("provenance_guard_failed")
    if moat_score < 60.0:
        blockers.append("moat_public_score_too_low")
    if pack_score < 65.0:
        blockers.append("large_benchmark_pack_readiness_too_low")
    if unknown_license_ratio > 25.0:
        blockers.append("unknown_license_ratio_too_high")

    warnings: list[str] = []
    if anchor_status == "NEEDS_REVIEW":
        warnings.append("anchor_public_release_needs_review")
    if scoreboard_status == "NEEDS_REVIEW":
        warnings.append("moat_public_scoreboard_needs_review")
    if pack_status == "NEEDS_REVIEW":
        warnings.append("large_model_benchmark_pack_needs_review")
    if provenance_status == "NEEDS_REVIEW":
        warnings.append("provenance_guard_needs_review")
    if moat_score < 78.0:
        warnings.append("moat_public_score_below_target")
    if anchor_score < 78.0:
        warnings.append("anchor_public_release_score_below_target")
    if pack_score < 78.0:
        warnings.append("large_model_benchmark_pack_score_below_target")
    if provenance_completeness < 95.0:
        warnings.append("provenance_completeness_below_target")

    release_readiness_score = round(
        max(
            0.0,
            min(
                100.0,
                (anchor_score * 0.3)
                + (moat_score * 0.3)
                + (pack_score * 0.2)
                + (provenance_completeness * 0.15)
                + (10.0 if contract_status == "PASS" and contract_fail_count == 0 else 0.0)
                - (unknown_license_ratio * 0.15)
                - (contract_fail_count * 3.0),
            ),
        ),
        2,
    )

    gate_decision = "ALLOW"
    if blockers:
        gate_decision = "BLOCK"
    elif warnings:
        gate_decision = "NEEDS_REVIEW"

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif gate_decision == "BLOCK":
        status = "FAIL"
    elif gate_decision == "NEEDS_REVIEW":
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "gate_decision": gate_decision,
        "release_readiness_score": release_readiness_score,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "blockers": blockers,
        "warnings": warnings,
        "signals": {
            "anchor_status": anchor_status,
            "anchor_public_release_score": anchor_score,
            "moat_public_scoreboard_status": scoreboard_status,
            "moat_public_score": moat_score,
            "large_model_benchmark_pack_status": pack_status,
            "large_model_benchmark_pack_readiness_score": pack_score,
            "provenance_guard_status": provenance_status,
            "provenance_completeness_pct": provenance_completeness,
            "unknown_license_ratio_pct": unknown_license_ratio,
            "optional_ci_contract_status": contract_status,
            "optional_ci_contract_fail_count": contract_fail_count,
        },
        "reasons": sorted(set(reasons)),
        "sources": {
            "anchor_public_release_summary": args.anchor_public_release_summary,
            "moat_public_scoreboard_summary": args.moat_public_scoreboard_summary,
            "large_model_benchmark_pack_summary": args.large_model_benchmark_pack_summary,
            "modelica_library_provenance_guard_summary": args.modelica_library_provenance_guard_summary,
            "optional_ci_contract_summary": args.optional_ci_contract_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(
        json.dumps(
            {"status": status, "gate_decision": gate_decision, "release_readiness_score": release_readiness_score}
        )
    )
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
