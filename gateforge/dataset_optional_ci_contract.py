from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


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
    lines = [
        "# GateForge Dataset Optional CI Contract",
        "",
        f"- status: `{payload.get('status')}`",
        f"- required_summary_count: `{payload.get('required_summary_count')}`",
        f"- pass_count: `{payload.get('pass_count')}`",
        f"- fail_count: `{payload.get('fail_count')}`",
        "",
        "## Checks",
        "",
    ]
    for check in payload.get("checks", []):
        lines.append(
            f"- `{check.get('name')}` status=`{check.get('status')}` path=`{check.get('path')}` missing_keys=`{','.join(check.get('missing_keys') or []) or 'none'}`"
        )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _validate_required_summary(root: Path, name: str, rel_path: str, required_keys: list[str]) -> dict:
    path = root / rel_path
    if not path.exists():
        return {
            "name": name,
            "path": str(path),
            "status": "FAIL",
            "reason": "missing_file",
            "missing_keys": required_keys,
        }
    payload = _load_json(path)
    missing = [k for k in required_keys if k not in payload]
    return {
        "name": name,
        "path": str(path),
        "status": "PASS" if not missing else "FAIL",
        "reason": "ok" if not missing else "missing_required_keys",
        "missing_keys": missing,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate dataset optional CI artifact contract")
    parser.add_argument("--artifacts-root", default="artifacts")
    parser.add_argument("--out", default="artifacts/dataset_optional_ci_contract/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    root = Path(args.artifacts_root)
    required = [
        ("dataset_pipeline_demo", "dataset_pipeline_demo/summary.json", ["bundle_status", "result_flags"]),
        (
            "dataset_artifacts_pipeline_demo",
            "dataset_artifacts_pipeline_demo/summary.json",
            ["bundle_status", "quality_gate_status"],
        ),
        ("dataset_history_demo", "dataset_history_demo/summary.json", ["bundle_status"]),
        ("dataset_governance_demo", "dataset_governance_demo/summary.json", ["bundle_status"]),
        ("dataset_policy_lifecycle_demo", "dataset_policy_lifecycle_demo/summary.json", ["bundle_status"]),
        ("dataset_governance_history_demo", "dataset_governance_history_demo/summary.json", ["bundle_status"]),
        ("dataset_strategy_autotune_demo", "dataset_strategy_autotune_demo/summary.json", ["bundle_status"]),
        ("dataset_strategy_autotune_apply_demo", "dataset_strategy_autotune_apply_demo/summary.json", ["bundle_status"]),
        (
            "dataset_strategy_autotune_apply_history_demo",
            "dataset_strategy_autotune_apply_history_demo/summary.json",
            ["bundle_status"],
        ),
        (
            "dataset_governance_snapshot_demo",
            "dataset_governance_snapshot_demo/demo_summary.json",
            ["bundle_status", "promotion_effectiveness_history_trend_status"],
        ),
        (
            "dataset_governance_snapshot_trend_demo",
            "dataset_governance_snapshot_trend_demo/demo_summary.json",
            ["bundle_status", "status_transition"],
        ),
        (
            "dataset_promotion_candidate_demo",
            "dataset_promotion_candidate_demo/summary.json",
            ["bundle_status", "decision"],
        ),
        (
            "dataset_promotion_candidate_apply_demo",
            "dataset_promotion_candidate_apply_demo/summary.json",
            ["bundle_status"],
        ),
        (
            "dataset_promotion_candidate_history_demo",
            "dataset_promotion_candidate_history_demo/summary.json",
            ["bundle_status"],
        ),
        (
            "dataset_promotion_candidate_apply_history_demo",
            "dataset_promotion_candidate_apply_history_demo/summary.json",
            ["bundle_status"],
        ),
        (
            "dataset_promotion_effectiveness_demo",
            "dataset_promotion_effectiveness_demo/summary.json",
            ["bundle_status", "effectiveness_decision"],
        ),
        (
            "dataset_promotion_effectiveness_history_demo",
            "dataset_promotion_effectiveness_history_demo/summary.json",
            ["bundle_status", "trend_status"],
        ),
        (
            "dataset_policy_autotune_history_demo",
            "dataset_policy_autotune_history_demo/summary.json",
            ["bundle_status"],
        ),
    ]
    checks = [_validate_required_summary(root, name, rel_path, keys) for name, rel_path, keys in required]
    pass_count = len([x for x in checks if x.get("status") == "PASS"])
    fail_count = len(checks) - pass_count
    payload = {
        "status": "PASS" if fail_count == 0 else "FAIL",
        "artifacts_root": str(root),
        "required_summary_count": len(required),
        "pass_count": pass_count,
        "fail_count": fail_count,
        "checks": checks,
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "fail_count": fail_count}))
    if payload["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
