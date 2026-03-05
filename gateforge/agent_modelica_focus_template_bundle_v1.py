from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_patch_template_engine_v1 import build_patch_template

DEFAULT_STAGE_BY_FAILURE = {
    "model_check_error": "check",
    "simulate_error": "simulate",
    "semantic_regression": "simulate",
}


def _safe_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


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
        "# GateForge Agent Modelica Focus Template Bundle v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- template_count: `{payload.get('template_count')}`",
        "",
        "## Templates",
        "",
    ]
    rows = payload.get("templates") if isinstance(payload.get("templates"), list) else []
    if rows:
        for row in rows:
            lines.append(
                f"- `{row.get('rank')}` `{row.get('failure_type')}` gate=`{row.get('gate_break_reason')}` "
                f"template=`{row.get('template_id')}` actions=`{row.get('actions_count')}`"
            )
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def _parse_stage_map(raw: str) -> dict[str, str]:
    out = dict(DEFAULT_STAGE_BY_FAILURE)
    text = str(raw or "").strip()
    if not text:
        return out
    for part in text.split(","):
        item = str(part).strip()
        if not item or ":" not in item:
            continue
        key, value = item.split(":", 1)
        ftype = str(key).strip().lower()
        stage = str(value).strip().lower()
        if ftype and stage:
            out[ftype] = stage
    return out


def _strategy_signal_maps(strategy_ab_summary_payload: dict) -> tuple[dict[str, float], dict[str, float]]:
    root = (
        strategy_ab_summary_payload.get("strategy_signal_by_failure_type")
        if isinstance(strategy_ab_summary_payload.get("strategy_signal_by_failure_type"), dict)
        else {}
    )
    treatment = root.get("treatment") if isinstance(root.get("treatment"), dict) else {}
    delta = root.get("delta_score") if isinstance(root.get("delta_score"), dict) else {}

    treatment_score_by_failure: dict[str, float] = {}
    delta_score_by_failure: dict[str, float] = {}
    for key, value in treatment.items():
        if not isinstance(value, dict):
            continue
        ftype = str(key or "").strip()
        if not ftype:
            continue
        treatment_score_by_failure[ftype] = _safe_float(value.get("score"), 0.0)
    for key, value in delta.items():
        ftype = str(key or "").strip()
        if not ftype:
            continue
        delta_score_by_failure[ftype] = _safe_float(value, 0.0)
    return treatment_score_by_failure, delta_score_by_failure


def _queue_rows(queue_payload: dict) -> list[dict]:
    rows = queue_payload.get("queue") if isinstance(queue_payload.get("queue"), list) else []
    if not rows:
        rows = queue_payload.get("targets") if isinstance(queue_payload.get("targets"), list) else []
    rows = [x for x in rows if isinstance(x, dict)]
    rows = sorted(
        rows,
        key=lambda x: (
            int(x.get("rank", 999999) or 999999),
            -_safe_float(x.get("priority_score"), 0.0),
            str(x.get("failure_type") or ""),
        ),
    )
    return rows


def build_focus_template_bundle(
    queue_payload: dict,
    *,
    top_k: int = 2,
    expected_stage_by_failure: dict[str, str] | None = None,
    strategy_signal_treatment_by_failure: dict[str, float] | None = None,
    strategy_signal_delta_by_failure: dict[str, float] | None = None,
) -> dict:
    stage_map = expected_stage_by_failure or dict(DEFAULT_STAGE_BY_FAILURE)
    treatment_map = strategy_signal_treatment_by_failure or {}
    delta_map = strategy_signal_delta_by_failure or {}
    rows = _queue_rows(queue_payload)
    selected = rows[: max(1, int(top_k))]
    templates: list[dict] = []
    for idx, row in enumerate(selected, start=1):
        failure_type = str(row.get("failure_type") or "unknown").strip().lower()
        expected_stage = str(stage_map.get(failure_type, "unknown") or "unknown").strip().lower()
        gate = str(row.get("gate_break_reason") or "unknown_fail").strip().lower()
        template = build_patch_template(
            failure_type=failure_type,
            expected_stage=expected_stage,
            focus_queue_payload=queue_payload,
        )
        actions = [str(x) for x in (template.get("actions") or []) if isinstance(x, str)]
        directives = [x for x in (template.get("edit_directives") or []) if isinstance(x, dict)]
        templates.append(
            {
                "rank": int(row.get("rank") or idx),
                "failure_type": failure_type,
                "gate_break_reason": gate,
                "priority_score": _safe_float(row.get("priority_score"), 0.0),
                "expected_stage": expected_stage,
                "template_id": str(template.get("template_id") or ""),
                "actions_count": len(actions),
                "focus_actions_count": int(template.get("focus_actions_count", 0) or 0),
                "actions": actions,
                "edit_directives": directives,
                "strategy_signal_treatment_score": _safe_float(
                    row.get("strategy_signal_treatment_score"),
                    _safe_float(treatment_map.get(failure_type), 0.0),
                ),
                "strategy_signal_delta_score": _safe_float(
                    row.get("strategy_signal_delta_score"),
                    _safe_float(delta_map.get(failure_type), 0.0),
                ),
            }
        )
    return {
        "template_count": len(templates),
        "templates": templates,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build top-k targeted repair template bundle from focus queue")
    parser.add_argument("--focus-queue", required=True)
    parser.add_argument("--strategy-ab-summary", default="")
    parser.add_argument("--top-k", type=int, default=2)
    parser.add_argument(
        "--expected-stage-map",
        default="model_check_error:check,simulate_error:simulate,semantic_regression:simulate",
    )
    parser.add_argument("--out", default="artifacts/agent_modelica_focus_template_bundle_v1/bundle.json")
    parser.add_argument("--report-out", default=None)
    args = parser.parse_args()

    queue_payload = _load_json(args.focus_queue)
    strategy_ab_payload = _load_json(args.strategy_ab_summary) if str(args.strategy_ab_summary).strip() else {}
    treatment_map, delta_map = _strategy_signal_maps(strategy_ab_payload)
    payload = build_focus_template_bundle(
        queue_payload=queue_payload,
        top_k=max(1, int(args.top_k)),
        expected_stage_by_failure=_parse_stage_map(args.expected_stage_map),
        strategy_signal_treatment_by_failure=treatment_map,
        strategy_signal_delta_by_failure=delta_map,
    )
    out = {
        "schema_version": "agent_modelica_focus_template_bundle_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if int(payload.get("template_count", 0)) > 0 else "NEEDS_REVIEW",
        **payload,
        "sources": {
            "focus_queue": args.focus_queue,
            "strategy_ab_summary": args.strategy_ab_summary if str(args.strategy_ab_summary).strip() else None,
        },
    }
    _write_json(args.out, out)
    _write_markdown(args.report_out or _default_md_path(args.out), out)
    print(json.dumps({"status": out.get("status"), "template_count": out.get("template_count")}))


if __name__ == "__main__":
    main()
