from __future__ import annotations

import argparse
import json
from pathlib import Path

INVARIANT_REASON_PREFIX = "physical_invariant_"
DEFAULT_ALLOWED_FILES = ("examples/openmodelica/MinimalProbe.mo",)
DEFAULT_CONFIDENCE_MIN = 0.8
INVARIANT_REPAIR_PROFILE_DIR = Path("policies/invariant_repair")
DEFAULT_INVARIANT_REPAIR_PROFILE = "default"


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, summary: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Invariant Repair Plan",
        "",
        f"- source_path: `{summary.get('source_path')}`",
        f"- source_kind: `{summary.get('source_kind')}`",
        f"- source_proposal_id: `{summary.get('source_proposal_id')}`",
        f"- invariant_repair_detected: `{summary.get('invariant_repair_detected')}`",
        f"- invariant_repair_applied: `{summary.get('invariant_repair_applied')}`",
        f"- planner_change_plan_confidence_min: `{summary.get('planner_change_plan_confidence_min')}`",
        f"- planner_change_plan_allowed_files: `{','.join(summary.get('planner_change_plan_allowed_files', []))}`",
        "",
        "## Goal",
        "",
        f"- `{summary.get('goal')}`",
        "",
        "## Invariant Reasons",
        "",
    ]
    reasons = summary.get("invariant_reasons", [])
    if reasons:
        lines.extend([f"- `{r}`" for r in reasons])
    else:
        lines.append("- `none`")
    lines.extend(["", "## Context Keys", ""])
    context = summary.get("context_json", {})
    if isinstance(context, dict):
        lines.extend([f"- `{k}`" for k in sorted(context.keys())])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def collect_reasons(payload: dict) -> list[str]:
    for key in ("policy_reasons", "fail_reasons", "reasons"):
        value = payload.get(key)
        if isinstance(value, list):
            return [str(v) for v in value if isinstance(v, str)]
    return []


def resolve_invariant_repair_profile_path(profile: str | None, profile_path: str | None) -> str:
    if profile and profile_path:
        raise ValueError("Use either --profile or --profile-path, not both")
    if profile_path:
        return profile_path
    name = profile or DEFAULT_INVARIANT_REPAIR_PROFILE
    filename = name if name.endswith(".json") else f"{name}.json"
    resolved = INVARIANT_REPAIR_PROFILE_DIR / filename
    if not resolved.exists():
        raise ValueError(f"Invariant repair profile not found: {resolved}")
    return str(resolved)


def load_profile(path: str) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected profile JSON object: {path}")
    return payload


def source_kind(payload: dict) -> str:
    if "policy_decision" in payload and "fail_reasons" in payload:
        return "run_summary"
    if "decision" in payload and "reasons" in payload:
        return "regression"
    return "unknown"


def _extract_invariants(payload: dict) -> list[dict]:
    physical = payload.get("physical_invariants")
    if isinstance(physical, list):
        return [item for item in physical if isinstance(item, dict)]
    checker_cfg = payload.get("checker_config")
    if isinstance(checker_cfg, dict):
        inv_cfg = checker_cfg.get("invariant_guard")
        if isinstance(inv_cfg, dict):
            inv = inv_cfg.get("invariants")
            if isinstance(inv, list):
                return [item for item in inv if isinstance(item, dict)]
    return []


def build_invariant_repair_plan(
    source: dict,
    *,
    allowed_files: list[str] | None = None,
    confidence_min: float = DEFAULT_CONFIDENCE_MIN,
    profile_name: str = DEFAULT_INVARIANT_REPAIR_PROFILE,
    profile_version: str | None = None,
    risk_level_remap: dict | None = None,
) -> dict:
    reasons = collect_reasons(source)
    invariant_reasons = [r for r in reasons if r.startswith(INVARIANT_REASON_PREFIX)]
    detected = bool(invariant_reasons)
    invariants = _extract_invariants(source)
    allowed = list(allowed_files) if allowed_files else list(DEFAULT_ALLOWED_FILES)
    src_risk = str(source.get("risk_level") or "low").lower()
    remap = risk_level_remap or {"high": "medium"}
    planned_risk = str(remap.get(src_risk, src_risk))
    goal = (
        "Repair physical invariant violations and rerun governance gate. "
        "Keep change-set narrow and deterministic."
    )
    context_json = {
        "risk_level": planned_risk,
        "change_summary": (
            "Invariant-guided repair for reasons: "
            + (",".join(invariant_reasons) if invariant_reasons else "none")
        ),
        "checkers": ["invariant_guard"],
    }
    if invariants:
        context_json["physical_invariants"] = invariants
        context_json["checker_config"] = {"invariant_guard": {"invariants": invariants}}

    return {
        "profile_name": profile_name,
        "profile_version": profile_version,
        "source_kind": source_kind(source),
        "source_proposal_id": source.get("proposal_id"),
        "source_status": source.get("status") or source.get("decision"),
        "invariant_repair_detected": detected,
        "invariant_repair_applied": detected,
        "invariant_reasons": invariant_reasons,
        "invariant_reason_count": len(invariant_reasons),
        "source_reason_count": len(reasons),
        "goal": goal,
        "context_json": context_json,
        "planner_change_plan_confidence_min": float(confidence_min),
        "planner_change_plan_allowed_files": allowed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build invariant-repair plan from failed run/regression summary")
    parser.add_argument("--source", required=True, help="Path to failed run/regression summary JSON")
    parser.add_argument("--profile", default=DEFAULT_INVARIANT_REPAIR_PROFILE, help="Invariant repair profile name")
    parser.add_argument("--profile-path", default=None, help="Explicit invariant repair profile JSON path")
    parser.add_argument("--allowed-file", action="append", default=None, help="Allowed file whitelist (repeatable)")
    parser.add_argument(
        "--confidence-min",
        type=float,
        default=None,
        help="Planner min confidence override for invariant repair plan",
    )
    parser.add_argument("--out", default="artifacts/invariant_repair/plan.json", help="Output plan JSON path")
    parser.add_argument("--report", default=None, help="Output markdown report path")
    args = parser.parse_args()

    source = json.loads(Path(args.source).read_text(encoding="utf-8"))
    if not isinstance(source, dict):
        raise SystemExit("source must be a JSON object")

    profile_path = resolve_invariant_repair_profile_path(args.profile, args.profile_path)
    profile_payload = load_profile(profile_path)
    allowed_files = args.allowed_file
    if allowed_files is None:
        cfg_files = profile_payload.get("allowed_files")
        if isinstance(cfg_files, list):
            allowed_files = [str(item) for item in cfg_files if isinstance(item, str)]
    resolved_confidence = args.confidence_min
    if resolved_confidence is None:
        cfg_conf = profile_payload.get("planner_change_plan_confidence_min")
        if isinstance(cfg_conf, (int, float)):
            resolved_confidence = float(cfg_conf)
    if resolved_confidence is None:
        resolved_confidence = DEFAULT_CONFIDENCE_MIN

    plan = build_invariant_repair_plan(
        source,
        allowed_files=allowed_files,
        confidence_min=float(resolved_confidence),
        profile_name=str(profile_payload.get("name") or args.profile),
        profile_version=str(profile_payload.get("version")) if profile_payload.get("version") is not None else None,
        risk_level_remap=profile_payload.get("risk_level_remap")
        if isinstance(profile_payload.get("risk_level_remap"), dict)
        else None,
    )
    summary = {"source_path": args.source, "profile_path": profile_path, **plan}
    _write_json(args.out, summary)
    _write_markdown(args.report or _default_md_path(args.out), summary)
    print(
        json.dumps(
            {
                "invariant_repair_detected": summary["invariant_repair_detected"],
                "invariant_reason_count": summary["invariant_reason_count"],
            }
        )
    )


if __name__ == "__main__":
    main()
