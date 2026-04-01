from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_agent_profile_registry_v1 import get_agent_profile
from .agent_modelica_verification_contract_v1 import (
    build_verification_contract,
    write_verification_contract,
)


SCHEMA_VERSION = "agent_modelica_independent_verifier_v1"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_independent_verifier_v1"


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def verify_post_restore_evidence_flow(
    *,
    lane_summary_path: str,
    run_summary_path: str,
    promotion_summary_path: str,
    classifier_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    verifier_profile = get_agent_profile("evidence-verifier")
    lane = _load_json(lane_summary_path)
    run = _load_json(run_summary_path)
    promotion = _load_json(promotion_summary_path)
    classifier = _load_json(classifier_summary_path)

    observed = promotion.get("observed_metrics") if isinstance(promotion.get("observed_metrics"), dict) else {}
    classifier_metrics = classifier.get("metrics") if isinstance(classifier.get("metrics"), dict) else {}
    bucket_counts = classifier_metrics.get("failure_bucket_counts") if isinstance(classifier_metrics.get("failure_bucket_counts"), dict) else {}

    total = int(run.get("total") or 0)
    passed = int(run.get("passed") or 0)
    rule_then_llm_count = sum(
        1
        for row in (run.get("results") if isinstance(run.get("results"), list) else [])
        if str(row.get("resolution_path") or "") == "rule_then_llm"
    )

    checks = [
        {
            "name": "verifier_profile_is_evidence_verifier",
            "passed": verifier_profile.profile_id == "evidence-verifier",
            "details": {"profile_id": verifier_profile.profile_id},
        },
        {
            "name": "lane_is_freeze_ready",
            "passed": str(lane.get("lane_status") or "") == "FREEZE_READY",
            "details": {"lane_status": lane.get("lane_status")},
        },
        {
            "name": "promotion_status_ready",
            "passed": str(promotion.get("status") or "") == "PROMOTION_READY",
            "details": {"promotion_status": promotion.get("status")},
        },
        {
            "name": "counts_align_across_summaries",
            "passed": (
                total == int(observed.get("total_cases") or 0)
                and total == int(classifier_metrics.get("total_rows") or 0)
            ),
            "details": {
                "run_total": total,
                "promotion_total_cases": observed.get("total_cases"),
                "classifier_total_rows": classifier_metrics.get("total_rows"),
            },
        },
        {
            "name": "pass_counts_align",
            "passed": (
                passed == int(observed.get("passed_cases") or 0)
                and passed == int(bucket_counts.get("success_after_restore") or 0)
            ),
            "details": {
                "run_passed": passed,
                "promotion_passed_cases": observed.get("passed_cases"),
                "classifier_success_after_restore": bucket_counts.get("success_after_restore"),
            },
        },
        {
            "name": "rule_then_llm_count_aligns",
            "passed": rule_then_llm_count == int(observed.get("rule_then_llm_count") or 0),
            "details": {
                "run_rule_then_llm_count": rule_then_llm_count,
                "promotion_rule_then_llm_count": observed.get("rule_then_llm_count"),
            },
        },
        {
            "name": "deterministic_only_pct_aligns",
            "passed": float(run.get("deterministic_only_pct") or 0.0) == float(observed.get("deterministic_only_pct") or 0.0),
            "details": {
                "run_deterministic_only_pct": run.get("deterministic_only_pct"),
                "promotion_deterministic_only_pct": observed.get("deterministic_only_pct"),
            },
        },
    ]

    contract = build_verification_contract(
        verifier_profile_id=verifier_profile.profile_id,
        verified_flow="post_restore_v0_3_5_evidence",
        inputs={
            "lane_summary_path": str(Path(lane_summary_path).resolve()) if Path(lane_summary_path).exists() else str(lane_summary_path),
            "run_summary_path": str(Path(run_summary_path).resolve()) if Path(run_summary_path).exists() else str(run_summary_path),
            "promotion_summary_path": str(Path(promotion_summary_path).resolve()) if Path(promotion_summary_path).exists() else str(promotion_summary_path),
            "classifier_summary_path": str(Path(classifier_summary_path).resolve()) if Path(classifier_summary_path).exists() else str(classifier_summary_path),
        },
        checks=checks,
    )

    out_root = Path(out_dir)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": contract.get("status"),
        "verified_flow": contract.get("verified_flow"),
        "verifier_profile_id": contract.get("verifier_profile_id"),
        "summary": {
            "all_checks_passed": contract.get("status") == "PASS",
            "check_count": len(checks),
            "failed_checks": [item.get("name") for item in checks if not bool(item.get("passed"))],
        },
        "verification_contract": contract,
    }
    _write_json(out_root / "summary.json", payload)
    write_verification_contract(out_root / "verification_contract.json", contract)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# Independent Verifier Summary",
                "",
                f"- status: `{payload['status']}`",
                f"- verified_flow: `{payload['verified_flow']}`",
                f"- verifier_profile_id: `{payload['verifier_profile_id']}`",
                f"- check_count: `{payload['summary']['check_count']}`",
                f"- failed_checks: `{payload['summary']['failed_checks']}`",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the independent verifier over a narrow GateForge evidence flow.")
    parser.add_argument("--lane-summary", required=True)
    parser.add_argument("--run-summary", required=True)
    parser.add_argument("--promotion-summary", required=True)
    parser.add_argument("--classifier-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = verify_post_restore_evidence_flow(
        lane_summary_path=str(args.lane_summary),
        run_summary_path=str(args.run_summary),
        promotion_summary_path=str(args.promotion_summary),
        classifier_summary_path=str(args.classifier_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "failed_checks": (payload.get("summary") or {}).get("failed_checks")}))


if __name__ == "__main__":
    main()
