from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    lines = [
        "# GateForge Agent Modelica Learning Asset Readiness v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_rows: `{metrics.get('total_rows')}`",
        f"- missing_required_ratio: `{metrics.get('missing_required_ratio')}`",
        f"- duplicate_fingerprint_ratio: `{metrics.get('duplicate_fingerprint_ratio')}`",
        f"- holdout_overlap_count: `{metrics.get('holdout_overlap_count')}`",
        "",
        "## Checks",
        "",
    ]
    for key in sorted(checks.keys()):
        lines.append(f"- {key}: `{checks[key]}`")
    reasons = payload.get("reasons") if isinstance(payload.get("reasons"), list) else []
    lines.append("")
    lines.append("## Reasons")
    lines.append("")
    if reasons:
        lines.extend([f"- `{str(x)}`" for x in reasons])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _as_rows(memory_payload: dict) -> list[dict]:
    rows = memory_payload.get("rows") if isinstance(memory_payload.get("rows"), list) else []
    return [x for x in rows if isinstance(x, dict)]


def _norm(value: object) -> str:
    return str(value or "").strip()


def _row_missing_required(row: dict, required_fields: list[str]) -> bool:
    for field in required_fields:
        value = row.get(field)
        if isinstance(value, list):
            if not value:
                return True
            continue
        if isinstance(value, bool):
            continue
        if value is None:
            return True
        if isinstance(value, (int, float)):
            continue
        if not str(value).strip():
            return True
    return False


def _check_policy_keys(payload: dict, required_keys: tuple[str, ...]) -> bool:
    return all(key in payload for key in required_keys)


def build_readiness_summary(
    *,
    memory_payload: dict,
    data_quality_policy: dict,
    replay_eval_policy: dict,
    promotion_policy: dict,
    schema_files_exist: bool,
) -> dict:
    reasons: list[str] = []
    checks: dict[str, str] = {}
    rows = _as_rows(memory_payload)
    total_rows = len(rows)

    required_fields = [str(x) for x in (data_quality_policy.get("required_row_fields") or []) if isinstance(x, str)]
    if not required_fields:
        required_fields = [
            "fingerprint",
            "task_id",
            "failure_type",
            "used_strategy",
            "action_trace",
            "error_signature",
            "success",
        ]

    missing_required = sum(1 for row in rows if _row_missing_required(row, required_fields))
    missing_required_ratio = (missing_required / total_rows) if total_rows > 0 else 1.0

    fps = [_norm(row.get("fingerprint")) for row in rows if _norm(row.get("fingerprint"))]
    duplicate_fingerprint_count = max(0, len(fps) - len(set(fps)))
    duplicate_ratio = (duplicate_fingerprint_count / total_rows) if total_rows > 0 else 0.0

    min_total_rows = int(data_quality_policy.get("min_total_rows", 0) or 0)
    max_missing_ratio = float(data_quality_policy.get("max_missing_required_ratio", 1.0) or 1.0)
    max_duplicate_ratio = float(data_quality_policy.get("max_duplicate_fingerprint_ratio", 1.0) or 1.0)
    min_success_per_failure = int(data_quality_policy.get("min_success_rows_per_failure_type", 0) or 0)
    target_failure_types = [
        str(x).strip().lower()
        for x in (data_quality_policy.get("target_failure_types") or [])
        if isinstance(x, str) and str(x).strip()
    ]

    success_counts: dict[str, int] = {}
    for row in rows:
        ftype = _norm(row.get("failure_type")).lower()
        if not ftype:
            continue
        if bool(row.get("success")):
            success_counts[ftype] = success_counts.get(ftype, 0) + 1

    if target_failure_types:
        success_coverage_ok = all(success_counts.get(ft, 0) >= min_success_per_failure for ft in target_failure_types)
    else:
        success_coverage_ok = True

    require_non_overlap = bool(data_quality_policy.get("require_non_overlap_holdout", False))
    split_field = _norm(data_quality_policy.get("split_field")) or "split"
    train_values = {str(x).strip().lower() for x in (data_quality_policy.get("train_values") or ["train"]) if str(x).strip()}
    holdout_values = {
        str(x).strip().lower() for x in (data_quality_policy.get("holdout_values") or ["holdout"]) if str(x).strip()
    }
    train_signatures: set[str] = set()
    holdout_signatures: set[str] = set()
    for row in rows:
        signature = _norm(row.get("error_signature")).lower()
        split = _norm(row.get(split_field)).lower()
        if not signature:
            continue
        if split in train_values:
            train_signatures.add(signature)
        if split in holdout_values:
            holdout_signatures.add(signature)
    holdout_overlap = sorted(train_signatures.intersection(holdout_signatures))
    holdout_overlap_count = len(holdout_overlap)
    holdout_presence_ok = (not require_non_overlap) or bool(holdout_signatures)

    checks["schema_files_exist"] = "PASS" if schema_files_exist else "FAIL"
    checks["policy_keys_replay_eval_v1"] = (
        "PASS"
        if _check_policy_keys(
            replay_eval_policy,
            ("frozen_pack_path", "holdout_pack_path", "primary_metrics", "hard_regression_caps"),
        )
        else "FAIL"
    )
    checks["policy_keys_promotion_v1"] = (
        "PASS"
        if _check_policy_keys(
            promotion_policy,
            (
                "min_success_count_per_failure_type",
                "min_success_rate_gain_pct",
                "max_regression_increase",
                "max_physics_fail_increase",
            ),
        )
        else "FAIL"
    )
    checks["min_total_rows"] = "PASS" if total_rows >= min_total_rows else "FAIL"
    checks["max_missing_required_ratio"] = "PASS" if missing_required_ratio <= max_missing_ratio else "FAIL"
    checks["max_duplicate_fingerprint_ratio"] = "PASS" if duplicate_ratio <= max_duplicate_ratio else "FAIL"
    checks["min_success_rows_per_failure_type"] = "PASS" if success_coverage_ok else "FAIL"
    checks["holdout_presence"] = "PASS" if holdout_presence_ok else "FAIL"
    checks["non_overlap_holdout"] = "PASS" if holdout_overlap_count == 0 else "FAIL"

    if checks["schema_files_exist"] == "FAIL":
        reasons.append("schema_file_missing")
    if checks["policy_keys_replay_eval_v1"] == "FAIL":
        reasons.append("replay_eval_policy_missing_required_keys")
    if checks["policy_keys_promotion_v1"] == "FAIL":
        reasons.append("promotion_policy_missing_required_keys")
    if checks["min_total_rows"] == "FAIL":
        reasons.append("insufficient_rows_for_learning")
    if checks["max_missing_required_ratio"] == "FAIL":
        reasons.append("too_many_rows_missing_required_fields")
    if checks["max_duplicate_fingerprint_ratio"] == "FAIL":
        reasons.append("duplicate_fingerprint_ratio_too_high")
    if checks["min_success_rows_per_failure_type"] == "FAIL":
        reasons.append("insufficient_success_coverage_for_target_failure_types")
    if checks["holdout_presence"] == "FAIL":
        reasons.append("holdout_split_missing")
    if checks["non_overlap_holdout"] == "FAIL":
        reasons.append("holdout_signature_overlap_detected")

    status = "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL"
    return {
        "schema_version": "agent_modelica_learning_asset_readiness_v1",
        "status": status,
        "checks": checks,
        "metrics": {
            "total_rows": total_rows,
            "missing_required_rows": missing_required,
            "missing_required_ratio": round(missing_required_ratio, 4),
            "duplicate_fingerprint_count": duplicate_fingerprint_count,
            "duplicate_fingerprint_ratio": round(duplicate_ratio, 4),
            "holdout_signature_count": len(holdout_signatures),
            "train_signature_count": len(train_signatures),
            "holdout_overlap_count": holdout_overlap_count,
            "success_count_by_failure_type": success_counts,
        },
        "policy_snapshot": {
            "data_quality_gate_v1": data_quality_policy,
            "replay_eval_v1": replay_eval_policy,
            "promotion_v1": promotion_policy,
        },
        "reasons": reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate whether learning assets are ready before large-scale model training")
    parser.add_argument("--memory", default="data/private_failure_corpus/agent_modelica_repair_memory_v1.json")
    parser.add_argument("--failure-signature-schema", default="schemas/failure_signature_v1.schema.json")
    parser.add_argument("--repair-operator-schema", default="schemas/repair_operator_v1.schema.json")
    parser.add_argument("--repair-memory-schema", default="schemas/repair_memory_v1.schema.json")
    parser.add_argument("--data-quality-policy", default="policies/agent_learning/data_quality_gate_v1.json")
    parser.add_argument("--replay-eval-policy", default="policies/agent_learning/replay_eval_v1.json")
    parser.add_argument("--promotion-policy", default="policies/agent_learning/promotion_v1.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_learning_asset_readiness_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    schema_paths = [
        Path(args.failure_signature_schema),
        Path(args.repair_operator_schema),
        Path(args.repair_memory_schema),
    ]
    schema_files_exist = all(path.exists() for path in schema_paths)

    try:
        memory_payload = _load_json(args.memory)
        data_quality_policy = _load_json(args.data_quality_policy)
        replay_eval_policy = _load_json(args.replay_eval_policy)
        promotion_policy = _load_json(args.promotion_policy)
    except Exception as exc:
        payload = {
            "schema_version": "agent_modelica_learning_asset_readiness_v1",
            "status": "FAIL",
            "checks": {},
            "metrics": {},
            "reasons": [f"input_load_error:{exc}"],
            "inputs": {
                "memory": args.memory,
                "failure_signature_schema": args.failure_signature_schema,
                "repair_operator_schema": args.repair_operator_schema,
                "repair_memory_schema": args.repair_memory_schema,
                "data_quality_policy": args.data_quality_policy,
                "replay_eval_policy": args.replay_eval_policy,
                "promotion_policy": args.promotion_policy,
            },
        }
        _write_json(args.out, payload)
        report_out = args.report_out or _default_md_path(args.out)
        _write_markdown(report_out, payload)
        print(json.dumps({"status": "FAIL", "reason": payload["reasons"][0]}))
        raise SystemExit(1)

    payload = build_readiness_summary(
        memory_payload=memory_payload,
        data_quality_policy=data_quality_policy,
        replay_eval_policy=replay_eval_policy,
        promotion_policy=promotion_policy,
        schema_files_exist=schema_files_exist,
    )
    payload["inputs"] = {
        "memory": args.memory,
        "failure_signature_schema": args.failure_signature_schema,
        "repair_operator_schema": args.repair_operator_schema,
        "repair_memory_schema": args.repair_memory_schema,
        "data_quality_policy": args.data_quality_policy,
        "replay_eval_policy": args.replay_eval_policy,
        "promotion_policy": args.promotion_policy,
    }
    _write_json(args.out, payload)
    report_out = args.report_out or _default_md_path(args.out)
    _write_markdown(report_out, payload)
    print(json.dumps({"status": payload.get("status"), "checks": payload.get("checks", {})}))
    if str(payload.get("status")) != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
