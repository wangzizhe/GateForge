from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_track_b_attribution_proxy_v0_3_2"
DEFAULT_SOURCE_PATH = "artifacts/benchmark_track_b/gf_results_v0_2_0.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_b_attribution_proxy_v0_3_2"


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


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _success(row: dict) -> bool:
    if bool(row.get("success")):
        return True
    if str(row.get("executor_status") or "").strip().upper() == "PASS":
        return True
    return bool(row.get("check_model_pass") and row.get("simulate_pass"))


def build_proxy_results(source_payload: dict) -> list[dict]:
    rows = source_payload.get("results") if isinstance(source_payload.get("results"), list) else []
    proxy_rows: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        succeeded = _success(row)
        proxy_rows.append(
            {
                "mutation_id": str(row.get("mutation_id") or ""),
                "task_id": str(row.get("mutation_id") or ""),
                "expected_failure_type": str(row.get("expected_failure_type") or ""),
                "target_scale": str(row.get("target_scale") or ""),
                "success": succeeded,
                "executor_status": "PASS" if succeeded else str(row.get("executor_status") or ""),
                "resolution_path": "deterministic_rule_only" if succeeded else "unresolved",
                "dominant_stage_subtype": "",
                "planner_invoked": False,
                "planner_used": False,
                "planner_decisive": False,
                "replay_used": False,
                "proxy_mode": "legacy_track_b_conservative_no_attempt_level_provenance",
            }
        )
    return proxy_rows


def _render_markdown(summary: dict) -> str:
    lines = [
        "# Track B Attribution Proxy v0.3.2",
        "",
        f"- status: `{summary.get('status')}`",
        f"- source_path: `{summary.get('source_path')}`",
        f"- total_tasks: `{summary.get('total_tasks')}`",
        f"- success_count: `{summary.get('success_count')}`",
        f"- success_at_k_pct: `{summary.get('success_at_k_pct')}`",
        f"- resolution_path_distribution: `{json.dumps(summary.get('resolution_path_distribution') or {}, sort_keys=True)}`",
    ]
    notes = summary.get("notes") if isinstance(summary.get("notes"), list) else []
    if notes:
        lines.append(f"- notes: `{'; '.join(str(note) for note in notes)}`")
    return "\n".join(lines).strip() + "\n"


def run_proxy(*, source_path: str = DEFAULT_SOURCE_PATH, out_dir: str = DEFAULT_OUT_DIR) -> dict:
    payload = _load_json(source_path)
    proxy_rows = build_proxy_results(payload)
    total_tasks = len(proxy_rows)
    success_count = len([row for row in proxy_rows if bool(row.get("success"))])
    success_paths: dict[str, int] = {}
    for row in proxy_rows:
        path = str(row.get("resolution_path") or "").strip()
        if not path:
            continue
        success_paths[path] = int(success_paths.get(path) or 0) + 1
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if total_tasks > 0 else "MISSING_SOURCE",
        "source_path": str(source_path),
        "total_tasks": total_tasks,
        "success_count": success_count,
        "success_at_k_pct": _ratio(success_count, total_tasks),
        "resolution_path_distribution": dict(sorted(success_paths.items())),
        "dominant_stage_subtype_distribution": {},
        "planner_invoked_rate_pct": 0.0,
        "planner_used_rate_pct": 0.0,
        "planner_decisive_rate_pct": 0.0,
        "replay_used_rate_pct": 0.0,
        "notes": [
            "conservative attribution proxy built from legacy Track B authority results",
            "no attempt-level provenance is available, so planner and replay usage are treated as unobserved",
        ],
    }
    out_root = Path(out_dir)
    proxy_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "source_path": str(source_path),
        "notes": list(summary.get("notes") or []),
        "results": proxy_rows,
    }
    _write_json(out_root / "proxy_results.json", proxy_payload)
    _write_json(out_root / "summary.json", summary)
    _write_text(out_root / "summary.md", _render_markdown(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a conservative Track B attribution proxy from legacy authority results")
    parser.add_argument("--source-path", default=DEFAULT_SOURCE_PATH)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = run_proxy(source_path=str(args.source_path), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "success_count": payload.get("success_count")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
