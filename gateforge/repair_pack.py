from __future__ import annotations

import argparse
import json
from pathlib import Path

REPAIR_STRATEGY_PROFILE_DIR = Path("policies/repair_strategy")
DEFAULT_REPAIR_STRATEGY_PROFILE = "default"


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _load_json(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _safe_case_name(text: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in text).strip("_")
    return cleaned or "case"


def _default_retry_for_risk(risk_level: str) -> int:
    risk = str(risk_level or "low").lower()
    if risk == "high":
        return 0
    if risk == "medium":
        return 2
    return 1


def _resolve_strategy_profile_path(profile: str | None, profile_path: str | None) -> str:
    if profile and profile_path:
        raise ValueError("Use either --strategy-profile or --strategy-profile-path, not both")
    if profile_path:
        return profile_path
    name = profile or DEFAULT_REPAIR_STRATEGY_PROFILE
    filename = name if name.endswith(".json") else f"{name}.json"
    resolved = REPAIR_STRATEGY_PROFILE_DIR / filename
    if not resolved.exists():
        raise ValueError(f"Repair strategy profile not found: {resolved}")
    return str(resolved)


def _merge_case_config(*configs: dict) -> dict:
    out: dict = {}
    for cfg in configs:
        if not isinstance(cfg, dict):
            continue
        out.update(cfg)
    return out


def _normalize_retry_budget(risk_level: str, cfg: dict) -> int:
    max_retries = cfg.get("max_retries")
    if isinstance(max_retries, int):
        return max(0, max_retries)
    by_risk = cfg.get("max_retries_by_risk", {})
    if isinstance(by_risk, dict):
        value = by_risk.get(str(risk_level).lower())
        if isinstance(value, int):
            return max(0, value)
    return _default_retry_for_risk(risk_level)


def _collect_fix_tasks(tasks_summary: dict) -> list[dict]:
    tasks = tasks_summary.get("tasks", [])
    if not isinstance(tasks, list):
        return []
    out = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if task.get("category") != "fix_plan":
            continue
        out.append(task)
    return out


def _build_cases(
    tasks_summary: dict,
    *,
    max_cases: int,
    planner_backend: str,
    policy_profile: str | None,
    strategy_profile_payload: dict,
) -> list[dict]:
    source_path = tasks_summary.get("source_path")
    if not isinstance(source_path, str) or not source_path:
        raise ValueError("tasks summary must contain source_path")

    risk_level = str(tasks_summary.get("risk_level") or "low")
    base_cfg = strategy_profile_payload.get("default_case", {})
    by_priority = strategy_profile_payload.get("priority_overrides", {})
    by_strategy = strategy_profile_payload.get("strategy_overrides", {})
    risk_policy_profile = strategy_profile_payload.get("policy_profile_by_risk", {})
    fix_tasks = _collect_fix_tasks(tasks_summary)
    cases: list[dict] = []

    for idx, task in enumerate(fix_tasks[:max_cases]):
        reason = str(task.get("reason") or f"reason_{idx+1}")
        strategy = str(task.get("recommended_strategy") or "generic_repair")
        priority = str(task.get("priority") or "P1")
        merged_cfg = _merge_case_config(
            base_cfg,
            by_priority.get(priority) if isinstance(by_priority, dict) else {},
            by_strategy.get(strategy) if isinstance(by_strategy, dict) else {},
        )
        retry_budget = _normalize_retry_budget(risk_level, merged_cfg)
        resolved_backend = str(merged_cfg.get("planner_backend") or planner_backend)
        resolved_policy_profile = (
            str(merged_cfg.get("policy_profile"))
            if isinstance(merged_cfg.get("policy_profile"), str)
            else (
                str(risk_policy_profile.get(risk_level))
                if isinstance(risk_policy_profile, dict) and isinstance(risk_policy_profile.get(risk_level), str)
                else policy_profile
            )
        )
        case_name = _safe_case_name(f"{idx+1:02d}_{strategy}")
        case = {
            "name": case_name,
            "source": source_path,
            "planner_backend": resolved_backend,
            "max_retries": retry_budget,
            "metadata": {
                "reason": reason,
                "recommended_strategy": strategy,
                "task_id": task.get("id"),
                "priority": task.get("priority"),
            },
        }
        if isinstance(merged_cfg.get("retry_confidence_min"), (int, float)):
            case["retry_confidence_min"] = float(merged_cfg["retry_confidence_min"])
        if isinstance(merged_cfg.get("retry_fallback_planner_backend"), str):
            case["retry_fallback_planner_backend"] = str(merged_cfg["retry_fallback_planner_backend"])
        if resolved_policy_profile:
            case["policy_profile"] = resolved_policy_profile
        cases.append(case)

    if not cases:
        merged_cfg = _merge_case_config(base_cfg)
        retry_budget = _normalize_retry_budget(risk_level, merged_cfg)
        resolved_backend = str(merged_cfg.get("planner_backend") or planner_backend)
        resolved_policy_profile = (
            str(merged_cfg.get("policy_profile"))
            if isinstance(merged_cfg.get("policy_profile"), str)
            else (
                str(risk_policy_profile.get(risk_level))
                if isinstance(risk_policy_profile, dict) and isinstance(risk_policy_profile.get(risk_level), str)
                else policy_profile
            )
        )
        fallback = {
            "name": "01_generic_repair",
            "source": source_path,
            "planner_backend": resolved_backend,
            "max_retries": retry_budget,
            "metadata": {
                "reason": "generic_repair",
                "recommended_strategy": "generic_repair",
            },
        }
        if isinstance(merged_cfg.get("retry_confidence_min"), (int, float)):
            fallback["retry_confidence_min"] = float(merged_cfg["retry_confidence_min"])
        if isinstance(merged_cfg.get("retry_fallback_planner_backend"), str):
            fallback["retry_fallback_planner_backend"] = str(merged_cfg["retry_fallback_planner_backend"])
        if resolved_policy_profile:
            fallback["policy_profile"] = resolved_policy_profile
        cases.append(fallback)
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate repair_batch pack from repair_tasks summary")
    parser.add_argument("--tasks-summary", required=True, help="repair_tasks summary JSON path")
    parser.add_argument("--pack-id", default="repair_pack_from_tasks_v0", help="Generated pack id")
    parser.add_argument("--planner-backend", default="rule", choices=["rule", "gemini", "openai"])
    parser.add_argument("--policy-profile", default=None, help="Optional policy profile for all generated cases")
    parser.add_argument(
        "--strategy-profile",
        default=DEFAULT_REPAIR_STRATEGY_PROFILE,
        help="Repair strategy profile name under policies/repair_strategy",
    )
    parser.add_argument(
        "--strategy-profile-path",
        default=None,
        help="Explicit repair strategy profile JSON path",
    )
    parser.add_argument("--max-cases", type=int, default=5, help="Maximum number of fix_plan tasks to convert")
    parser.add_argument(
        "--out",
        default="artifacts/repair_pack/pack_from_tasks.json",
        help="Output repair batch pack JSON path",
    )
    args = parser.parse_args()
    if args.max_cases <= 0:
        raise SystemExit("--max-cases must be > 0")

    tasks_summary = _load_json(args.tasks_summary)
    strategy_profile_path = _resolve_strategy_profile_path(args.strategy_profile, args.strategy_profile_path)
    strategy_profile_payload = _load_json(strategy_profile_path)
    cases = _build_cases(
        tasks_summary,
        max_cases=args.max_cases,
        planner_backend=args.planner_backend,
        policy_profile=args.policy_profile,
        strategy_profile_payload=strategy_profile_payload,
    )
    output = {
        "pack_id": args.pack_id,
        "generated_from": args.tasks_summary,
        "strategy_profile": args.strategy_profile,
        "strategy_profile_path": strategy_profile_path,
        "risk_level": tasks_summary.get("risk_level"),
        "policy_decision": tasks_summary.get("policy_decision"),
        "task_count": tasks_summary.get("task_count"),
        "strategy_counts": tasks_summary.get("strategy_counts", {}),
        "cases": cases,
    }
    _write_json(args.out, output)
    print(json.dumps({"pack_id": output["pack_id"], "case_count": len(cases), "out": args.out}))


if __name__ == "__main__":
    main()
