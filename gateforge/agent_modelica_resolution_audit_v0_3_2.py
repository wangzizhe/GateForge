from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_resolution_audit_v0_3_2"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_resolution_audit_v0_3_2"
DEFAULT_LANES = (
    {
        "lane_id": "track_a",
        "label": "Track A",
        "source_path": "artifacts/agent_modelica_planner_sensitive_pack_builder_v1/gf_results_track_a_v0_2_5.json",
    },
    {
        "lane_id": "track_b",
        "label": "Track B",
        "source_path": "artifacts/agent_modelica_track_b_attribution_proxy_v0_3_2/summary.json",
    },
    {
        "lane_id": "harder_holdout",
        "label": "Harder Holdout",
        "source_path": "artifacts/agent_modelica_harder_holdout_ablation_v0_3_1/baseline/gf_results.json",
    },
    {
        "lane_id": "planner_sensitive",
        "label": "Planner-Sensitive Lane",
        "source_path": "artifacts/agent_modelica_planner_sensitive_attribution_repair_v0_3_2/summary_baseline.json",
    },
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _norm(value: object) -> str:
    return str(value or "").strip()


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _counts_to_pct(counts: dict[str, int], total: int) -> dict[str, float]:
    return {key: _ratio(int(value or 0), total) for key, value in sorted(counts.items())}


def _results_rows(payload: dict) -> list[dict]:
    rows = payload.get("results")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _payload_notes(payload: dict, summary: dict | None = None) -> list[str]:
    notes: list[str] = []
    source_rows = payload.get("notes")
    if isinstance(source_rows, list):
        notes.extend(str(row).strip() for row in source_rows if str(row).strip())
    source_summary = summary if isinstance(summary, dict) else {}
    summary_rows = source_summary.get("notes")
    if isinstance(summary_rows, list):
        notes.extend(str(row).strip() for row in summary_rows if str(row).strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for note in notes:
        if note in seen:
            continue
        deduped.append(note)
        seen.add(note)
    return deduped


def _top_level_summary(payload: dict) -> dict:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return summary
    return payload


def summarize_lane_payload(*, lane_id: str, label: str, source_path: str, payload: dict) -> dict:
    rows = _results_rows(payload)
    if rows:
        total_tasks = len(rows)
        success_count = len([row for row in rows if bool(row.get("success"))])
        failure_count = total_tasks - success_count
        success_rows = [row for row in rows if bool(row.get("success"))]
        success_path_counts: dict[str, int] = {}
        all_path_counts: dict[str, int] = {}
        stage_counts: dict[str, int] = {}
        planner_invoked_count = 0
        planner_used_count = 0
        planner_decisive_count = 0
        replay_used_count = 0
        attribution_available = False
        for row in rows:
            path = _norm(row.get("resolution_path"))
            stage = _norm(row.get("dominant_stage_subtype"))
            if path:
                attribution_available = True
                all_path_counts[path] = int(all_path_counts.get(path) or 0) + 1
            if stage:
                stage_counts[stage] = int(stage_counts.get(stage) or 0) + 1
            if bool(row.get("planner_invoked")):
                planner_invoked_count += 1
            if bool(row.get("planner_used")):
                planner_used_count += 1
            if bool(row.get("planner_decisive")):
                planner_decisive_count += 1
            if bool(row.get("replay_used")):
                replay_used_count += 1
        for row in success_rows:
            path = _norm(row.get("resolution_path"))
            if path:
                success_path_counts[path] = int(success_path_counts.get(path) or 0) + 1
        notes = _payload_notes(payload)
        status = "PASS"
        if not attribution_available:
            status = "NEEDS_ATTRIBUTION_RERUN"
            notes.append("resolution_path missing from lane artifact")
        return {
            "lane_id": lane_id,
            "label": label,
            "source_path": source_path,
            "status": status,
            "artifact_type": "gf_results",
            "task_count": total_tasks,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate_pct": _ratio(success_count, total_tasks),
            "attribution_available": attribution_available,
            "success_resolution_path_counts": dict(sorted(success_path_counts.items())),
            "success_resolution_path_pct": _counts_to_pct(success_path_counts, success_count),
            "all_resolution_path_counts": dict(sorted(all_path_counts.items())),
            "dominant_stage_subtype_distribution": dict(sorted(stage_counts.items())),
            "planner_invoked_rate_pct": _ratio(planner_invoked_count, total_tasks),
            "planner_used_rate_pct": _ratio(planner_used_count, total_tasks),
            "planner_decisive_rate_pct": _ratio(planner_decisive_count, total_tasks),
            "replay_used_rate_pct": _ratio(replay_used_count, total_tasks),
            "notes": notes,
        }

    summary = _top_level_summary(payload)
    resolution_counts = summary.get("resolution_path_distribution")
    if isinstance(resolution_counts, dict):
        total_tasks = int(summary.get("total_tasks") or summary.get("total_records") or 0)
        success_count = int(
            summary.get("success_count")
            or round((float(summary.get("success_at_k_pct") or 0.0) / 100.0) * total_tasks)
        )
        failure_count = max(total_tasks - success_count, 0)
        notes = _payload_notes(payload, summary)
        unresolved_count = int(resolution_counts.get("unresolved") or 0)
        if success_count > 0 and unresolved_count >= success_count:
            notes.append("successful lane still reports unresolved resolution paths; inspect attribution fidelity")
        return {
            "lane_id": lane_id,
            "label": label,
            "source_path": source_path,
            "status": "PASS",
            "artifact_type": "summary",
            "task_count": total_tasks,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate_pct": float(summary.get("success_at_k_pct") or 0.0),
            "attribution_available": True,
            "success_resolution_path_counts": dict(sorted((str(k), int(v or 0)) for k, v in resolution_counts.items())),
            "success_resolution_path_pct": _counts_to_pct(
                {str(k): int(v or 0) for k, v in resolution_counts.items()},
                total_tasks,
            ),
            "all_resolution_path_counts": dict(sorted((str(k), int(v or 0)) for k, v in resolution_counts.items())),
            "dominant_stage_subtype_distribution": dict(
                sorted((str(k), int(v or 0)) for k, v in (summary.get("dominant_stage_subtype_distribution") or {}).items())
            ),
            "planner_invoked_rate_pct": float(summary.get("planner_invoked_rate_pct") or 0.0),
            "planner_used_rate_pct": float(summary.get("planner_used_rate_pct") or 0.0),
            "planner_decisive_rate_pct": float(summary.get("planner_decisive_rate_pct") or 0.0),
            "replay_used_rate_pct": float(summary.get("replay_used_rate_pct") or 0.0),
            "notes": notes,
        }

    return {
        "lane_id": lane_id,
        "label": label,
        "source_path": source_path,
        "status": "MISSING_OR_UNSUPPORTED",
        "artifact_type": "unknown",
        "task_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "success_rate_pct": 0.0,
        "attribution_available": False,
        "success_resolution_path_counts": {},
        "success_resolution_path_pct": {},
        "all_resolution_path_counts": {},
        "dominant_stage_subtype_distribution": {},
        "planner_invoked_rate_pct": 0.0,
        "planner_used_rate_pct": 0.0,
        "planner_decisive_rate_pct": 0.0,
        "replay_used_rate_pct": 0.0,
        "notes": ["artifact missing or unsupported"],
    }


def build_overall_interpretation(lanes: list[dict]) -> dict:
    deterministic_dominated: list[str] = []
    attribution_gaps: list[str] = []
    planner_observed: list[str] = []
    unresolved_success_anomalies: list[str] = []
    for lane in lanes:
        if not isinstance(lane, dict):
            continue
        lane_id = _norm(lane.get("lane_id"))
        if _norm(lane.get("status")) == "NEEDS_ATTRIBUTION_RERUN":
            attribution_gaps.append(lane_id)
        success_pct = lane.get("success_resolution_path_pct") if isinstance(lane.get("success_resolution_path_pct"), dict) else {}
        deterministic_pct = float(success_pct.get("deterministic_rule_only") or 0.0)
        if deterministic_pct >= 80.0:
            deterministic_dominated.append(lane_id)
        if float(lane.get("planner_invoked_rate_pct") or 0.0) > 0.0:
            planner_observed.append(lane_id)
        notes = lane.get("notes") if isinstance(lane.get("notes"), list) else []
        if any("unresolved resolution paths" in str(note) for note in notes):
            unresolved_success_anomalies.append(lane_id)
    overall_status = "PASS"
    if attribution_gaps:
        overall_status = "NEEDS_RERUN"
    return {
        "status": overall_status,
        "deterministic_dominated_lanes": deterministic_dominated,
        "attribution_gap_lanes": attribution_gaps,
        "planner_observed_lanes": planner_observed,
        "unresolved_success_anomaly_lanes": unresolved_success_anomalies,
    }


def render_markdown(payload: dict) -> str:
    lines = [
        "# Agent Modelica Resolution Audit v0.3.2",
        "",
        f"- status: `{_norm((payload.get('overall') or {}).get('status'))}`",
        f"- generated_at_utc: `{_norm(payload.get('generated_at_utc'))}`",
        "",
        "## Overall",
        "",
    ]
    overall = payload.get("overall") if isinstance(payload.get("overall"), dict) else {}
    lines.append(f"- deterministic_dominated_lanes: `{', '.join(overall.get('deterministic_dominated_lanes') or [])}`")
    lines.append(f"- attribution_gap_lanes: `{', '.join(overall.get('attribution_gap_lanes') or [])}`")
    lines.append(f"- planner_observed_lanes: `{', '.join(overall.get('planner_observed_lanes') or [])}`")
    lines.append(f"- unresolved_success_anomaly_lanes: `{', '.join(overall.get('unresolved_success_anomaly_lanes') or [])}`")
    lines.append("")
    lines.append("## Lanes")
    lines.append("")
    for lane in payload.get("lanes") or []:
        if not isinstance(lane, dict):
            continue
        lines.append(f"### {lane.get('label')}")
        lines.append("")
        lines.append(f"- lane_id: `{lane.get('lane_id')}`")
        lines.append(f"- status: `{lane.get('status')}`")
        lines.append(f"- source_path: `{lane.get('source_path')}`")
        lines.append(f"- task_count: `{lane.get('task_count')}`, success_count: `{lane.get('success_count')}`, success_rate_pct: `{lane.get('success_rate_pct')}`")
        lines.append(f"- planner_invoked_rate_pct: `{lane.get('planner_invoked_rate_pct')}`, planner_decisive_rate_pct: `{lane.get('planner_decisive_rate_pct')}`, replay_used_rate_pct: `{lane.get('replay_used_rate_pct')}`")
        lines.append(f"- success_resolution_path_counts: `{json.dumps(lane.get('success_resolution_path_counts') or {}, sort_keys=True)}`")
        notes = lane.get("notes") if isinstance(lane.get("notes"), list) else []
        if notes:
            lines.append(f"- notes: `{'; '.join(str(note) for note in notes)}`")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def run_resolution_audit(*, out_dir: str = DEFAULT_OUT_DIR, lane_overrides: list[dict] | None = None) -> dict:
    lanes_config = lane_overrides if lane_overrides is not None else list(DEFAULT_LANES)
    lane_rows: list[dict] = []
    for lane in lanes_config:
        lane_id = _norm(lane.get("lane_id"))
        label = _norm(lane.get("label") or lane_id)
        source_path = _norm(lane.get("source_path"))
        payload = _load_json(source_path)
        lane_rows.append(
            summarize_lane_payload(
                lane_id=lane_id,
                label=label,
                source_path=source_path,
                payload=payload,
            )
        )
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "lanes": lane_rows,
        "overall": build_overall_interpretation(lane_rows),
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", result)
    _write_text(out_root / "summary.md", render_markdown(result))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a v0.3.2 resolution-path audit across authority lanes")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = run_resolution_audit(out_dir=str(args.out_dir))
    print(json.dumps(payload.get("overall") or {}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
