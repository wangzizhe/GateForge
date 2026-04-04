from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_24_common import (
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    SCHEMA_PREFIX,
    build_surface_index_payload,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_surface_index"


def build_v0324_surface_index(*, out_dir: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR)) -> dict:
    payload = build_surface_index_payload()
    records = payload.get("surface_records") if isinstance(payload.get("surface_records"), dict) else {}
    export_failures = payload.get("export_failures") if isinstance(payload.get("export_failures"), list) else []
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if records else "FAIL",
        "source_mode": payload.get("source_mode"),
        "omc_backend": payload.get("omc_backend"),
        "docker_image": payload.get("docker_image"),
        "modelica_version": payload.get("modelica_version"),
        "surface_record_count": len(records),
        "surface_export_total_count": int(payload.get("surface_export_total_count") or 0),
        "surface_export_success_count": int(payload.get("surface_export_success_count") or 0),
        "surface_export_success_rate_pct": float(payload.get("surface_export_success_rate_pct") or 0.0),
        "fixture_fallback_rate_pct": float(payload.get("fixture_fallback_rate_pct") or 0.0),
        "export_failure_count": len(export_failures),
    }
    full_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "summary": summary,
        "surface_records": records,
        "export_failures": export_failures,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "surface_index.json", full_payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.24 Surface Index",
                "",
                f"- status: `{summary.get('status')}`",
                f"- source_mode: `{summary.get('source_mode')}`",
                f"- surface_export_success_rate_pct: `{summary.get('surface_export_success_rate_pct')}`",
                f"- export_failure_count: `{summary.get('export_failure_count')}`",
                "",
            ]
        ),
    )
    return full_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.24 authoritative local interface surface index.")
    parser.add_argument("--out-dir", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0324_surface_index(out_dir=str(args.out_dir))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "surface_export_success_rate_pct": summary.get("surface_export_success_rate_pct")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
