from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def _load_json(path: str) -> dict:
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


def _write_markdown(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Agent Modelica Strategy Promote v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- promoted_count: `{payload.get('promoted_count')}`",
        f"- decision: `{payload.get('decision')}`",
        f"- promotion_allowed: `{payload.get('promotion_allowed')}`",
        "",
    ]
    reasons = payload.get("gate_reasons") if isinstance(payload.get("gate_reasons"), list) else []
    lines.extend(["## Gate Reasons", ""])
    if reasons:
        lines.extend([f"- `{r}`" for r in reasons])
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _score(row: dict) -> float:
    return (
        float(row.get("delta_pass_rate_pct", 0.0) or 0.0) * 10.0
        - float(row.get("delta_avg_elapsed_sec", 0.0) or 0.0)
        + float(row.get("count", 0) or 0.0)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote top repair strategies from A/B summary")
    parser.add_argument("--ab-summary", required=True)
    parser.add_argument("--treatment-playbook", required=True)
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument("--enforce-safety-gate", action="store_true", default=True)
    parser.add_argument("--no-enforce-safety-gate", dest="enforce_safety_gate", action="store_false")
    parser.add_argument("--out", default="artifacts/agent_modelica_strategy_promote_v1/promoted_playbook.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    ab = _load_json(args.ab_summary)
    treatment = _load_json(args.treatment_playbook)
    per_failure = ab.get("per_failure_type") if isinstance(ab.get("per_failure_type"), dict) else {}
    playbook = treatment.get("playbook") if isinstance(treatment.get("playbook"), list) else []
    playbook = [x for x in playbook if isinstance(x, dict)]

    ranked_failures = sorted(
        [
            {
                "failure_type": ftype,
                **(row if isinstance(row, dict) else {}),
                "score": _score(row if isinstance(row, dict) else {}),
            }
            for ftype, row in per_failure.items()
            if isinstance(ftype, str)
        ],
        key=lambda x: (-float(x.get("score", 0.0)), x.get("failure_type", "")),
    )
    top_failures = [x.get("failure_type") for x in ranked_failures[: max(1, int(args.top_k))]]

    promoted_entries: list[dict] = []
    for ftype in top_failures:
        candidates = [x for x in playbook if str(x.get("failure_type") or "") == ftype]
        if not candidates:
            continue
        best = sorted(candidates, key=lambda x: (-int(x.get("priority", 0) or 0), str(x.get("strategy_id") or "")))[0]
        promoted_entries.append(best)

    gate_reasons: list[str] = []
    decision = str(ab.get("decision") or "UNKNOWN")
    delta = ab.get("delta") if isinstance(ab.get("delta"), dict) else {}
    delta_reg = float(delta.get("regression_count", 0.0) or 0.0)
    delta_phy = float(delta.get("physics_fail_count", 0.0) or 0.0)
    if decision != "PROMOTE_TREATMENT":
        gate_reasons.append(f"decision_not_promote:{decision}")
    if delta_reg > 0.0:
        gate_reasons.append("regression_count_increased")
    if delta_phy > 0.0:
        gate_reasons.append("physics_fail_count_increased")

    promotion_allowed = True
    if bool(args.enforce_safety_gate) and gate_reasons:
        promotion_allowed = False

    if not promotion_allowed:
        # Keep full treatment playbook as stable fallback when gate is closed.
        promoted_entries = list(playbook)
    elif not promoted_entries:
        promoted_entries = sorted(playbook, key=lambda x: (-int(x.get("priority", 0) or 0), str(x.get("strategy_id") or "")))[:2]

    payload = {
        "schema_version": "agent_modelica_repair_playbook_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "decision": decision,
        "promotion_allowed": promotion_allowed,
        "gate_reasons": gate_reasons,
        "promoted_count": len(promoted_entries),
        "playbook": promoted_entries,
        "sources": {
            "ab_summary": args.ab_summary,
            "treatment_playbook": args.treatment_playbook,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": payload.get("status"), "promoted_count": payload.get("promoted_count")}))


if __name__ == "__main__":
    main()
