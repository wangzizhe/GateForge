from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_release_preflight_v0_1_3_evidence_v1"


def _load_json(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _status_ok(value: str) -> bool:
    return str(value or "").strip().upper() == "PASS"


def _robustness_status(baseline: dict, deterministic: dict) -> tuple[str, list[str], dict]:
    reasons: list[str] = []
    baseline_pct = float(
        baseline.get("all_scenarios_pass_pct")
        or baseline.get("contract_pass_pct")
        or baseline.get("success_at_k_pct")
        or 0.0
    )
    deterministic_pct = float(
        deterministic.get("all_scenarios_pass_pct")
        or deterministic.get("contract_pass_pct")
        or deterministic.get("success_at_k_pct")
        or 0.0
    )
    delta_pp = round(deterministic_pct - baseline_pct, 2)
    if not baseline:
        reasons.append("robustness_baseline_summary_missing")
    if not deterministic:
        reasons.append("robustness_deterministic_summary_missing")
    if deterministic_pct < 100.0:
        reasons.append("robustness_deterministic_not_saturated")
    if delta_pp <= 0.0:
        reasons.append("robustness_no_uplift")
    status = "PASS" if not reasons else "FAIL"
    details = {
        "baseline_pct": baseline_pct,
        "deterministic_pct": deterministic_pct,
        "delta_pp": delta_pp,
    }
    return status, reasons, details


def _multistep_status(summary: dict) -> tuple[str, list[str], dict]:
    reasons: list[str] = []
    unlock_pct = float(summary.get("stage_2_unlock_pct") or 0.0)
    focus_pct = float(summary.get("stage_2_focus_pct") or 0.0)
    revisit_count = int(summary.get("stage_1_revisit_after_unlock_count") or 0)
    resolution_count = int(summary.get("stage_2_resolution_count") or 0)
    total_tasks = int(summary.get("total_tasks") or 0)
    resolution_pct = round((resolution_count / total_tasks) * 100.0, 2) if total_tasks > 0 else 0.0
    effective_control_pct = max(focus_pct, resolution_pct)
    scenario_fail_breakdown = summary.get("scenario_fail_breakdown") if isinstance(summary.get("scenario_fail_breakdown"), dict) else {}
    infra_count = int(scenario_fail_breakdown.get("infra") or 0)
    drift_count = int(scenario_fail_breakdown.get("llm_patch_drift") or 0)
    if not summary:
        reasons.append("multistep_baseline_summary_missing")
    if unlock_pct < 50.0:
        reasons.append("multistep_stage_2_unlock_below_threshold")
    if effective_control_pct < 50.0:
        reasons.append("multistep_stage_2_control_below_threshold")
    if revisit_count > 0:
        reasons.append("multistep_stage_1_revisit_after_unlock_present")
    if infra_count > 1:
        reasons.append("multistep_infra_noise_too_high")
    if drift_count > 1:
        reasons.append("multistep_patch_drift_too_high")
    status = "PASS" if not reasons else "FAIL"
    details = {
        "stage_2_unlock_pct": unlock_pct,
        "stage_2_focus_pct": focus_pct,
        "stage_2_resolution_pct": resolution_pct,
        "effective_stage_2_control_pct": effective_control_pct,
        "stage_1_revisit_after_unlock_count": revisit_count,
        "stage_2_resolution_count": resolution_count,
        "infra_count": infra_count,
        "llm_patch_drift_count": drift_count,
    }
    return status, reasons, details


def main() -> None:
    parser = argparse.ArgumentParser(description="Augment release preflight summary with v0.1.3 evidence checks")
    parser.add_argument("--summary", required=True)
    parser.add_argument("--robustness-baseline-summary", required=True)
    parser.add_argument("--robustness-deterministic-summary", required=True)
    parser.add_argument("--multistep-baseline-summary", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()

    out_path = str(args.out or args.summary)
    summary = _load_json(args.summary)
    robustness_baseline = _load_json(args.robustness_baseline_summary)
    robustness_deterministic = _load_json(args.robustness_deterministic_summary)
    multistep_baseline = _load_json(args.multistep_baseline_summary)

    robustness_status, robustness_reasons, robustness_details = _robustness_status(
        robustness_baseline,
        robustness_deterministic,
    )
    multistep_status, multistep_reasons, multistep_details = _multistep_status(multistep_baseline)

    payload = dict(summary)
    payload["schema_version"] = SCHEMA_VERSION
    payload["generated_at_utc"] = datetime.now(timezone.utc).isoformat()
    payload["v013_source_blind_robustness_status"] = robustness_status
    payload["v013_source_blind_multistep_status"] = multistep_status
    payload["v013_multistep_stage_2_unlock_pct"] = float(multistep_details["stage_2_unlock_pct"])
    payload["v013_multistep_stage_2_focus_pct"] = float(multistep_details["stage_2_focus_pct"])
    payload["v013_source_blind_robustness"] = {
        **robustness_details,
        "reasons": robustness_reasons,
        "baseline_summary_path": str(args.robustness_baseline_summary),
        "deterministic_summary_path": str(args.robustness_deterministic_summary),
    }
    payload["v013_source_blind_multistep"] = {
        **multistep_details,
        "reasons": multistep_reasons,
        "baseline_summary_path": str(args.multistep_baseline_summary),
    }

    reasons = [str(x) for x in payload.get("reasons") or [] if isinstance(x, str)]
    if robustness_status != "PASS":
        reasons.append("v013_source_blind_robustness_not_pass")
    if multistep_status != "PASS":
        reasons.append("v013_source_blind_multistep_not_pass")
    payload["reasons"] = reasons

    status = str(payload.get("status") or "PASS").strip().upper() or "PASS"
    if not _status_ok(robustness_status) or not _status_ok(multistep_status):
        status = "FAIL"
    payload["status"] = status

    _write_json(out_path, payload)
    print(json.dumps(payload))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
