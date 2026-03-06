from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_learning_asset_readiness_v1 import build_readiness_summary


def _load_json(path: str) -> dict:
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    checks = payload.get("checks") if isinstance(payload.get("checks"), dict) else {}
    lines = [
        "# GateForge Agent Modelica Learning Preflight v1",
        "",
        f"- status: `{payload.get('status')}`",
        "",
        "## Checks",
        "",
    ]
    for key in sorted(checks.keys()):
        lines.append(f"- {key}: `{checks[key]}`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _path_exists(path: str) -> bool:
    return bool(str(path).strip()) and Path(path).exists()


def _hardpack_has_cases(hardpack_payload: dict) -> bool:
    cases = hardpack_payload.get("cases") if isinstance(hardpack_payload.get("cases"), list) else []
    return len([x for x in cases if isinstance(x, dict)]) > 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Preflight gate before large-scale learning run")
    parser.add_argument("--profile", default="benchmarks/agent_modelica_mvp_repair_v1.json")
    parser.add_argument("--core-manifest", default="")
    parser.add_argument("--small-manifest", default="")
    parser.add_argument("--failure-signature-schema", default="schemas/failure_signature_v1.schema.json")
    parser.add_argument("--repair-operator-schema", default="schemas/repair_operator_v1.schema.json")
    parser.add_argument("--repair-memory-schema", default="schemas/repair_memory_v1.schema.json")
    parser.add_argument("--data-quality-policy", default="policies/agent_learning/data_quality_gate_v1.json")
    parser.add_argument("--replay-eval-policy", default="policies/agent_learning/replay_eval_v1.json")
    parser.add_argument("--promotion-policy", default="policies/agent_learning/promotion_v1.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_learning_preflight_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    profile = _load_json(args.profile)
    hardpack_path = (
        profile.get("taskset", {}).get("hardpack_path")
        if isinstance(profile.get("taskset"), dict)
        else ""
    )
    hardpack = _load_json(str(hardpack_path)) if _path_exists(str(hardpack_path)) else {}
    privacy = profile.get("privacy") if isinstance(profile.get("privacy"), dict) else {}
    memory_path = str(privacy.get("repair_history_path") or "data/private_failure_corpus/agent_modelica_repair_memory_v1.json")

    memory_payload = _load_json(memory_path)
    data_quality_policy = _load_json(args.data_quality_policy)
    replay_eval_policy = _load_json(args.replay_eval_policy)
    promotion_policy = _load_json(args.promotion_policy)
    readiness = build_readiness_summary(
        memory_payload=memory_payload,
        data_quality_policy=data_quality_policy,
        replay_eval_policy=replay_eval_policy,
        promotion_policy=promotion_policy,
        schema_files_exist=all(
            _path_exists(x)
            for x in (
                args.failure_signature_schema,
                args.repair_operator_schema,
                args.repair_memory_schema,
            )
        ),
    )

    checks = {
        "profile_exists": "PASS" if _path_exists(args.profile) else "FAIL",
        "hardpack_exists": "PASS" if _path_exists(str(hardpack_path)) else "FAIL",
        "hardpack_has_cases": "PASS" if _hardpack_has_cases(hardpack) else "FAIL",
        "core_manifest_exists": "PASS" if (_path_exists(args.core_manifest) or not str(args.core_manifest).strip()) else "FAIL",
        "small_manifest_exists": "PASS" if (_path_exists(args.small_manifest) or not str(args.small_manifest).strip()) else "FAIL",
        "learning_asset_readiness_pass": "PASS" if str(readiness.get("status")) == "PASS" else "FAIL",
    }

    reasons: list[str] = []
    for key, value in checks.items():
        if value != "PASS":
            reasons.append(key)

    status = "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL"
    payload = {
        "schema_version": "agent_modelica_learning_preflight_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "checks": checks,
        "reasons": reasons,
        "inputs": {
            "profile": args.profile,
            "core_manifest": args.core_manifest,
            "small_manifest": args.small_manifest,
            "hardpack_path": hardpack_path,
            "memory_path": memory_path,
            "data_quality_policy": args.data_quality_policy,
            "replay_eval_policy": args.replay_eval_policy,
            "promotion_policy": args.promotion_policy,
            "failure_signature_schema": args.failure_signature_schema,
            "repair_operator_schema": args.repair_operator_schema,
            "repair_memory_schema": args.repair_memory_schema,
        },
        "learning_asset_readiness": {
            "status": readiness.get("status"),
            "checks": readiness.get("checks"),
            "metrics": readiness.get("metrics"),
            "reasons": readiness.get("reasons"),
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "checks": checks}))
    if status != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
