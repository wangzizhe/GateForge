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
        "# GateForge Failure Balance Backfill Plan v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- total_actions: `{payload.get('total_actions')}`",
        f"- p0_actions: `{payload.get('p0_actions')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plan failure-type backfill actions from balance guard output")
    parser.add_argument("--mutation-failure-type-balance-guard-summary", required=True)
    parser.add_argument("--min-target-share-per-type", type=float, default=0.15)
    parser.add_argument("--out", default="artifacts/dataset_failure_balance_backfill_plan_v1/summary.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    guard = _load_json(args.mutation_failure_type_balance_guard_summary)
    reasons: list[str] = []
    if not guard:
        reasons.append("mutation_failure_type_balance_guard_summary_missing")

    dist = guard.get("expected_distribution") if isinstance(guard.get("expected_distribution"), dict) else {}
    total = sum(max(0, _to_int(v)) for v in dist.values())
    min_share = float(args.min_target_share_per_type)

    actions: list[dict] = []
    for failure_type, count_raw in dist.items():
        count = max(0, _to_int(count_raw))
        share = (count / total) if total > 0 else 0.0
        target_count = int(round(total * min_share))
        gap = max(0, target_count - count)
        if gap <= 0:
            continue
        priority = "P1"
        if share < (min_share * 0.5):
            priority = "P0"
        actions.append(
            {
                "action_id": f"failure_balance.{failure_type}",
                "priority": priority,
                "failure_type": failure_type,
                "current_count": count,
                "current_share": round(share, 4),
                "target_count": target_count,
                "target_share": round(min_share, 4),
                "gap_count": gap,
                "reason": "failure_type_underrepresented",
            }
        )

    actions.sort(key=lambda a: (str(a.get("priority") or "P9"), -_to_int(a.get("gap_count", 0)), str(a.get("failure_type") or "")))

    alerts: list[str] = []
    if actions:
        alerts.append("failure_balance_backfill_actions_generated")

    status = "PASS"
    if reasons:
        status = "FAIL"
    elif actions:
        status = "NEEDS_REVIEW"

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "total_actions": len(actions),
        "p0_actions": len([a for a in actions if str(a.get("priority") or "") == "P0"]),
        "actions": actions,
        "alerts": alerts,
        "reasons": sorted(set(reasons)),
        "sources": {
            "mutation_failure_type_balance_guard_summary": args.mutation_failure_type_balance_guard_summary,
        },
    }
    _write_json(args.out, payload)
    _write_markdown(args.report_out or _default_md_path(args.out), payload)
    print(json.dumps({"status": status, "total_actions": len(actions), "p0_actions": payload["p0_actions"]}))
    if status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
