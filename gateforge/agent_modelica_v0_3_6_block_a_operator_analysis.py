from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median


SCHEMA_VERSION = "agent_modelica_v0_3_6_block_a_operator_analysis"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_6_block_a_operator_analysis"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _task_rows(payload: dict) -> list[dict]:
    rows = payload.get("tasks")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    return []


def build_block_a_operator_analysis(
    *,
    refreshed_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    payload = _load_json(refreshed_summary_path)
    rows = _task_rows(payload)

    by_operator: dict[str, list[dict]] = {}
    for row in rows:
        operator = _norm(row.get("hidden_base_operator")) or "unknown_operator"
        by_operator.setdefault(operator, []).append(row)

    operator_rows: list[dict] = []
    for operator, items in sorted(by_operator.items()):
        total = len(items)
        planner_invoked_count = sum(1 for row in items if row.get("planner_invoked") is True)
        deterministic_only_count = sum(1 for row in items if _norm(row.get("resolution_path")) == "deterministic_rule_only")
        success_count = sum(1 for row in items if _norm(row.get("resolution_path")) in {"rule_then_llm", "llm_planner_assisted", "deterministic_rule_only"})
        rounds = [int(row.get("rounds_used") or 0) for row in items if int(row.get("rounds_used") or 0) > 0]
        rule_then_llm_count = sum(1 for row in items if _norm(row.get("resolution_path")) == "rule_then_llm")
        planner_invoked_pct = round(100.0 * planner_invoked_count / total, 1) if total else 0.0
        deterministic_only_pct = round(100.0 * deterministic_only_count / total, 1) if total else 0.0
        success_rate_pct = round(100.0 * success_count / total, 1) if total else 0.0
        rule_then_llm_pct = round(100.0 * rule_then_llm_count / total, 1) if total else 0.0
        median_rounds = float(median(rounds)) if rounds else 0.0
        operator_rows.append(
            {
                "hidden_base_operator": operator,
                "task_count": total,
                "planner_invoked_count": planner_invoked_count,
                "planner_invoked_pct": planner_invoked_pct,
                "deterministic_only_count": deterministic_only_count,
                "deterministic_only_pct": deterministic_only_pct,
                "success_rate_pct": success_rate_pct,
                "rule_then_llm_count": rule_then_llm_count,
                "rule_then_llm_pct": rule_then_llm_pct,
                "median_rounds_used": median_rounds,
                "promising_harder_direction": bool(
                    planner_invoked_pct >= 70.0
                    and deterministic_only_pct <= 30.0
                    and rule_then_llm_pct >= 50.0
                ),
            }
        )

    recommended = ""
    if operator_rows:
        top = max(
            operator_rows,
            key=lambda row: (
                int(bool(row.get("promising_harder_direction"))),
                float(row.get("planner_invoked_pct") or 0.0),
                -float(row.get("deterministic_only_pct") or 0.0),
                float(row.get("rule_then_llm_pct") or 0.0),
                float(row.get("median_rounds_used") or 0.0),
            ),
        )
        recommended = _norm(top.get("hidden_base_operator"))

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if operator_rows else "EMPTY",
        "refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
        "operator_rows": operator_rows,
        "recommended_operator": recommended,
        "recommended_action": (
            f"Expand `{recommended}` and stop spending Block A budget on weaker operators in the current lane."
            if recommended
            else "No operator recommendation available."
        ),
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", summary)
    _write_text(out_root / "summary.md", render_markdown(summary))
    return summary


def render_markdown(summary: dict) -> str:
    lines = [
        "# v0.3.6 Block A Operator Analysis",
        "",
        f"- status: `{summary.get('status')}`",
        f"- recommended_operator: `{summary.get('recommended_operator')}`",
        f"- recommended_action: `{summary.get('recommended_action')}`",
        "",
    ]
    for row in summary.get("operator_rows") or []:
        if not isinstance(row, dict):
            continue
        lines.extend(
            [
                f"## {row.get('hidden_base_operator')}",
                "",
                f"- task_count: `{row.get('task_count')}`",
                f"- planner_invoked_pct: `{row.get('planner_invoked_pct')}`",
                f"- deterministic_only_pct: `{row.get('deterministic_only_pct')}`",
                f"- rule_then_llm_pct: `{row.get('rule_then_llm_pct')}`",
                f"- median_rounds_used: `{row.get('median_rounds_used')}`",
                f"- promising_harder_direction: `{row.get('promising_harder_direction')}`",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize v0.3.6 Block A outcomes by hidden-base operator.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_block_a_operator_analysis(
        refreshed_summary_path=str(args.refreshed_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "recommended_operator": payload.get("recommended_operator")}))


if __name__ == "__main__":
    main()
