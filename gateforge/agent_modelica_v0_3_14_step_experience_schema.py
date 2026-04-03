from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_14_step_experience_common import STEP_SCHEMA_VERSION, norm, now_utc, residual_signal_cluster


SCHEMA_VERSION = "agent_modelica_v0_3_14_step_experience_schema"
REQUIRED_ATTEMPT_FIELDS = (
    "round",
    "observed_failure_type",
    "reason",
    "diagnostic_ir",
)


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _entries(manifest_payload: dict) -> list[dict]:
    rows: list[dict] = []
    for section_name in ("runtime", "initialization"):
        section = manifest_payload.get(section_name) if isinstance(manifest_payload.get(section_name), dict) else {}
        rows.extend([row for row in (section.get("experience_sources") or []) if isinstance(row, dict)])
        rows.extend([row for row in (section.get("eval_tasks") or []) if isinstance(row, dict)])
    failure_bank = manifest_payload.get("failure_bank") if isinstance(manifest_payload.get("failure_bank"), dict) else {}
    rows.extend([row for row in (failure_bank.get("runtime_failures") or []) if isinstance(row, dict)])
    rows.extend([row for row in (failure_bank.get("initialization_failures") or []) if isinstance(row, dict)])
    return rows


def build_schema_summary(*, manifest_path: str, out_dir: str) -> dict:
    manifest = _load_json(manifest_path)
    checked_rows = []
    missing_field_counts = {field: 0 for field in REQUIRED_ATTEMPT_FIELDS}
    missing_cluster_count = 0
    incompatible_count = 0
    for entry in _entries(manifest):
        detail = _load_json(entry.get("result_json_path") or "")
        attempts = detail.get("attempts") if isinstance(detail.get("attempts"), list) else []
        row_status = "PASS"
        row_missing = []
        if not attempts:
            row_status = "FAIL"
            incompatible_count += 1
            row_missing.append("attempts")
        else:
            first_attempt = next((row for row in attempts if isinstance(row, dict)), {})
            for field in REQUIRED_ATTEMPT_FIELDS:
                if field not in first_attempt:
                    missing_field_counts[field] += 1
                    row_missing.append(field)
            diagnostic = first_attempt.get("diagnostic_ir") if isinstance(first_attempt.get("diagnostic_ir"), dict) else {}
            cluster = residual_signal_cluster(
                dominant_stage_subtype=norm(diagnostic.get("dominant_stage_subtype")),
                error_subtype=norm(diagnostic.get("error_subtype")),
                observed_failure_type=norm(first_attempt.get("observed_failure_type")),
                reason=norm(first_attempt.get("reason")),
            )
            if not cluster or cluster == "unknown_residual_signal":
                missing_cluster_count += 1
                row_missing.append("residual_signal_cluster")
        if row_missing:
            row_status = "FAIL"
            incompatible_count += 1
        checked_rows.append(
            {
                "task_id": norm(entry.get("task_id")),
                "lane_name": norm(entry.get("lane_name")),
                "role": norm(entry.get("role")),
                "status": row_status,
                "missing_fields": row_missing,
                "result_json_path": norm(entry.get("result_json_path")),
            }
        )
    status = "PASS" if incompatible_count == 0 else "FAIL"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": status,
        "step_schema_version": STEP_SCHEMA_VERSION,
        "required_attempt_fields": list(REQUIRED_ATTEMPT_FIELDS),
        "checked_result_count": len(checked_rows),
        "compatible_result_count": len([row for row in checked_rows if row.get("status") == "PASS"]),
        "incompatible_result_count": incompatible_count,
        "missing_field_counts": missing_field_counts,
        "missing_residual_signal_cluster_count": missing_cluster_count,
        "results": checked_rows,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.14 Step Experience Schema",
                "",
                f"- status: `{status}`",
                f"- checked_result_count: `{payload.get('checked_result_count')}`",
                f"- compatible_result_count: `{payload.get('compatible_result_count')}`",
                f"- incompatible_result_count: `{payload.get('incompatible_result_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate v0.3.14 step schema against v0.3.13 authority traces.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    payload = build_schema_summary(manifest_path=str(args.manifest), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "compatible_result_count": payload.get("compatible_result_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
