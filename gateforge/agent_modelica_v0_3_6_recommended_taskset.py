from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_6_recommended_taskset"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_6_recommended_taskset"


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


def build_recommended_taskset(
    *,
    refreshed_summary_path: str,
    operator_analysis_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    refreshed = _load_json(refreshed_summary_path)
    operator_analysis = _load_json(operator_analysis_summary_path)
    rows = refreshed.get("tasks") if isinstance(refreshed.get("tasks"), list) else []
    tasks = [row for row in rows if isinstance(row, dict)]
    recommended_operator = _norm(operator_analysis.get("recommended_operator"))

    selected = [
        row for row in tasks
        if _norm(row.get("hidden_base_operator")) == recommended_operator
    ] if recommended_operator else []

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if selected else "EMPTY",
        "recommended_operator": recommended_operator,
        "refreshed_summary_path": str(Path(refreshed_summary_path).resolve()) if Path(refreshed_summary_path).exists() else str(refreshed_summary_path),
        "operator_analysis_summary_path": str(Path(operator_analysis_summary_path).resolve()) if Path(operator_analysis_summary_path).exists() else str(operator_analysis_summary_path),
        "task_count": len(selected),
        "task_ids": [str(row.get("task_id") or "") for row in selected],
        "tasks": selected,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "taskset.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    lines = [
        "# v0.3.6 Recommended Taskset",
        "",
        f"- status: `{payload.get('status')}`",
        f"- recommended_operator: `{payload.get('recommended_operator')}`",
        f"- task_count: `{payload.get('task_count')}`",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the recommended next-step v0.3.6 taskset from operator analysis.")
    parser.add_argument("--refreshed-summary", required=True)
    parser.add_argument("--operator-analysis-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_recommended_taskset(
        refreshed_summary_path=str(args.refreshed_summary),
        operator_analysis_summary_path=str(args.operator_analysis_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "recommended_operator": payload.get("recommended_operator"), "task_count": payload.get("task_count")}))


if __name__ == "__main__":
    main()
