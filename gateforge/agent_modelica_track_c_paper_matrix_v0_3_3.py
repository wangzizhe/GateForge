from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_track_c_paper_matrix_v0_3_3"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_paper_matrix_v0_3_3"
AUTH_SESSION_REASON_HINTS = ("auth", "login", "session")


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


def _ratio(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((part / total) * 100.0, 2)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return round(float(ordered[mid]), 2)
    return round((float(ordered[mid - 1]) + float(ordered[mid])) / 2.0, 2)


def _record_rows(bundle: dict) -> list[dict]:
    rows = bundle.get("records") if isinstance(bundle.get("records"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def _is_auth_session_failure(row: dict) -> bool:
    reason = _norm(row.get("infra_failure_reason")).lower()
    output_text = _norm(row.get("output_text")).lower()
    if reason and any(hint in reason for hint in AUTH_SESSION_REASON_HINTS):
        return True
    return "not logged in" in output_text or "/login" in output_text or "session" in output_text


def _bundle_run_row(path: str | Path) -> dict:
    bundle = _load_json(path)
    summary = bundle.get("summary") if isinstance(bundle.get("summary"), dict) else {}
    rows = _record_rows(bundle)
    provider_name = _norm(bundle.get("provider_name"))
    infra_failure_count = len([row for row in rows if bool(row.get("infra_failure"))])
    auth_session_failure_count = len([row for row in rows if _is_auth_session_failure(row)])
    shared_tool_plane_reached = any(int(row.get("omc_tool_call_count") or 0) > 0 for row in rows)
    clean_run = bool(rows) and infra_failure_count == 0 and auth_session_failure_count == 0
    if provider_name != "gateforge":
        clean_run = clean_run and shared_tool_plane_reached
    valid_rows = [row for row in rows if not bool(row.get("infra_failure"))]
    infra_normalized_success_rate_pct = _ratio(len([row for row in valid_rows if bool(row.get("success"))]), len(valid_rows))
    return {
        "provider_name": provider_name,
        "arm_id": _norm(bundle.get("arm_id")),
        "model_id": _norm(bundle.get("model_id")),
        "bundle_path": str(Path(path).resolve()) if Path(path).exists() else str(path),
        "record_count": len(rows),
        "success_rate_pct": float(summary.get("success_rate_pct") or 0.0),
        "infra_normalized_success_rate_pct": infra_normalized_success_rate_pct,
        "avg_wall_clock_sec": float(summary.get("avg_wall_clock_sec") or 0.0),
        "avg_omc_tool_call_count": float(summary.get("avg_omc_tool_call_count") or 0.0),
        "infra_failure_count": infra_failure_count,
        "auth_session_failure_count": auth_session_failure_count,
        "clean_run": bool(clean_run),
        "shared_tool_plane_reached": bool(shared_tool_plane_reached),
    }


def summarize_paper_matrix(
    *,
    bundle_paths: list[str],
    out_dir: str = DEFAULT_OUT_DIR,
    primary_provider: str = "claude",
    primary_min_clean_runs: int = 3,
    supplementary_min_clean_runs: int = 1,
) -> dict:
    run_rows = [_bundle_run_row(path) for path in bundle_paths if _load_json(path)]
    by_provider: dict[str, list[dict]] = {}
    for row in run_rows:
        by_provider.setdefault(_norm(row.get("provider_name")), []).append(row)

    provider_rows: list[dict] = []
    for provider_name, rows in sorted(by_provider.items()):
        clean_rows = [row for row in rows if bool(row.get("clean_run"))]
        total_records = sum(int(row.get("record_count") or 0) for row in rows)
        total_infra_failures = sum(int(row.get("infra_failure_count") or 0) for row in rows)
        total_auth_failures = sum(int(row.get("auth_session_failure_count") or 0) for row in rows)
        required_clean_runs = int(primary_min_clean_runs if provider_name == _norm(primary_provider) else supplementary_min_clean_runs)
        infra_failure_rate_pct = _ratio(total_infra_failures, total_records)
        auth_failure_rate_pct = _ratio(total_auth_failures, total_records)
        main_table_eligible = len(clean_rows) >= required_clean_runs and infra_failure_rate_pct < 10.0
        provider_rows.append(
            {
                "provider_name": provider_name,
                "run_count": len(rows),
                "clean_run_count": len(clean_rows),
                "required_clean_runs": required_clean_runs,
                "median_infra_normalized_success_rate_pct": _median([float(row.get("infra_normalized_success_rate_pct") or 0.0) for row in clean_rows]),
                "median_avg_wall_clock_sec": _median([float(row.get("avg_wall_clock_sec") or 0.0) for row in clean_rows]),
                "median_avg_omc_tool_call_count": _median([float(row.get("avg_omc_tool_call_count") or 0.0) for row in clean_rows]),
                "infra_failure_rate_pct": infra_failure_rate_pct,
                "auth_session_failure_rate_pct": auth_failure_rate_pct,
                "main_table_eligible": bool(main_table_eligible),
            }
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if run_rows else "FAIL",
        "bundle_paths": [str(Path(path).resolve()) if Path(path).exists() else str(path) for path in bundle_paths],
        "run_rows": run_rows,
        "provider_rows": provider_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_json(out_root / "provider_rows.json", {"rows": provider_rows})
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize a paper-usable Track C matrix for v0.3.3.")
    parser.add_argument("--bundle", action="append", default=[])
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--primary-provider", default="claude")
    parser.add_argument("--primary-min-clean-runs", type=int, default=3)
    parser.add_argument("--supplementary-min-clean-runs", type=int, default=1)
    args = parser.parse_args()
    payload = summarize_paper_matrix(
        bundle_paths=[str(x) for x in (args.bundle or []) if str(x).strip()],
        out_dir=str(args.out_dir),
        primary_provider=str(args.primary_provider),
        primary_min_clean_runs=int(args.primary_min_clean_runs),
        supplementary_min_clean_runs=int(args.supplementary_min_clean_runs),
    )
    print(json.dumps({"status": payload.get("status"), "provider_count": len(payload.get("provider_rows") or [])}))


if __name__ == "__main__":
    main()
