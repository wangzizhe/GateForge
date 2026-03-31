from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_claude_stability_gate_v0_3_3"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_claude_stability_gate_v0_3_3"
AUTH_SESSION_REASON_HINTS = ("auth", "login", "session")
RUN_INDEX_PATTERN = re.compile(r"run(\d+)", re.IGNORECASE)


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


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _parse_run_index(path: str | Path, fallback: int) -> int:
    match = RUN_INDEX_PATTERN.search(str(path))
    if not match:
        return fallback
    try:
        return int(match.group(1))
    except Exception:
        return fallback


def _record_rows(bundle: dict) -> list[dict]:
    rows = bundle.get("records") if isinstance(bundle.get("records"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def _is_auth_session_failure(row: dict) -> bool:
    reason = _norm(row.get("infra_failure_reason")).lower()
    output_text = _norm(row.get("output_text")).lower()
    if reason and any(hint in reason for hint in AUTH_SESSION_REASON_HINTS):
        return True
    return "not logged in" in output_text or "/login" in output_text or "session" in output_text


def summarize_claude_stability(
    *,
    bundle_paths: list[str],
    out_dir: str = DEFAULT_OUT_DIR,
    min_clean_runs: int = 3,
    consecutive_failure_limit: int = 3,
    recent_window: int = 5,
    recent_failure_rate_limit_pct: float = 40.0,
    working_days_elapsed: int = 0,
    working_days_limit: int = 3,
) -> dict:
    run_rows: list[dict] = []
    for idx, path in enumerate(bundle_paths, start=1):
        bundle = _load_json(path)
        rows = _record_rows(bundle)
        summary = bundle.get("summary") if isinstance(bundle.get("summary"), dict) else {}
        auth_fail_count = len([row for row in rows if _is_auth_session_failure(row)])
        infra_fail_count = len([row for row in rows if bool(row.get("infra_failure"))])
        shared_tool_plane_reached = any(int(row.get("omc_tool_call_count") or 0) > 0 for row in rows)
        clean_run = bool(rows) and infra_fail_count == 0 and auth_fail_count == 0 and shared_tool_plane_reached
        run_rows.append(
            {
                "run_index": _parse_run_index(path, idx),
                "bundle_path": str(Path(path).resolve()) if Path(path).exists() else str(path),
                "record_count": len(rows),
                "success_rate_pct": float(summary.get("success_rate_pct") or 0.0),
                "infra_failure_count": infra_fail_count,
                "auth_session_failure_count": auth_fail_count,
                "shared_tool_plane_reached": bool(shared_tool_plane_reached),
                "clean_run": bool(clean_run),
            }
        )
    run_rows.sort(key=lambda row: int(row.get("run_index") or 0))
    clean_runs = [row for row in run_rows if bool(row.get("clean_run"))]
    recent_rows = run_rows[-int(recent_window) :] if recent_window > 0 else list(run_rows)
    recent_failures = [row for row in recent_rows if int(row.get("auth_session_failure_count") or 0) > 0]
    consecutive = 0
    max_consecutive = 0
    for row in run_rows:
        if int(row.get("auth_session_failure_count") or 0) > 0:
            consecutive += 1
            max_consecutive = max(max_consecutive, consecutive)
        else:
            consecutive = 0
    conditions = {
        "min_clean_runs_met": len(clean_runs) >= int(min_clean_runs),
        "consecutive_failure_limit_hit": max_consecutive >= int(consecutive_failure_limit),
        "recent_failure_rate_limit_hit": _ratio(len(recent_failures), len(recent_rows)) >= float(recent_failure_rate_limit_pct) if recent_rows else False,
        "working_days_limit_hit_without_clean_runs": int(working_days_elapsed) >= int(working_days_limit) and len(clean_runs) < int(min_clean_runs),
    }
    switch_required = any(bool(v) for k, v in conditions.items() if k != "min_clean_runs_met")
    status = "STABLE"
    if switch_required:
        status = "API_DIRECT_SWITCH_REQUIRED"
    elif not conditions["min_clean_runs_met"]:
        status = "PROVISIONAL"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if run_rows else "FAIL",
        "classification": status,
        "bundle_paths": [row["bundle_path"] for row in run_rows],
        "run_rows": run_rows,
        "metrics": {
            "total_run_count": len(run_rows),
            "clean_run_count": len(clean_runs),
            "recent_window": int(recent_window),
            "recent_auth_session_failure_rate_pct": _ratio(len(recent_failures), len(recent_rows)),
            "max_consecutive_auth_session_failures": max_consecutive,
            "working_days_elapsed": int(working_days_elapsed),
        },
        "conditions": conditions,
        "switch_required": bool(switch_required),
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# Claude Stability Gate v0.3.3",
                "",
                f"- classification: `{payload['classification']}`",
                f"- clean_run_count: `{payload['metrics']['clean_run_count']}`",
                f"- total_run_count: `{payload['metrics']['total_run_count']}`",
                f"- recent_auth_session_failure_rate_pct: `{payload['metrics']['recent_auth_session_failure_rate_pct']}`",
                f"- max_consecutive_auth_session_failures: `{payload['metrics']['max_consecutive_auth_session_failures']}`",
                f"- switch_required: `{payload['switch_required']}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize Claude repeated-run stability for v0.3.3.")
    parser.add_argument("--bundle", action="append", default=[])
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-clean-runs", type=int, default=3)
    parser.add_argument("--consecutive-failure-limit", type=int, default=3)
    parser.add_argument("--recent-window", type=int, default=5)
    parser.add_argument("--recent-failure-rate-limit-pct", type=float, default=40.0)
    parser.add_argument("--working-days-elapsed", type=int, default=0)
    parser.add_argument("--working-days-limit", type=int, default=3)
    args = parser.parse_args()
    payload = summarize_claude_stability(
        bundle_paths=[str(x) for x in (args.bundle or []) if str(x).strip()],
        out_dir=str(args.out_dir),
        min_clean_runs=int(args.min_clean_runs),
        consecutive_failure_limit=int(args.consecutive_failure_limit),
        recent_window=int(args.recent_window),
        recent_failure_rate_limit_pct=float(args.recent_failure_rate_limit_pct),
        working_days_elapsed=int(args.working_days_elapsed),
        working_days_limit=int(args.working_days_limit),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))


if __name__ == "__main__":
    main()
