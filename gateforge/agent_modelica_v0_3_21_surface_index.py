from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_21_common import (
    DEFAULT_SURFACE_INDEX_OUT_DIR,
    SCHEMA_PREFIX,
    build_surface_index_payload,
    now_utc,
    norm,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_surface_index"


def build_v0321_surface_index(
    *,
    out_dir: str = str(DEFAULT_SURFACE_INDEX_OUT_DIR),
    use_fixture_only: bool = False,
) -> dict:
    payload = build_surface_index_payload(use_fixture_only=use_fixture_only)
    class_candidates = payload.get("class_path_candidates") if isinstance(payload.get("class_path_candidates"), dict) else {}
    parameter_records = payload.get("parameter_surface_records") if isinstance(payload.get("parameter_surface_records"), dict) else {}
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if class_candidates and parameter_records else "FAIL",
        "source_mode": norm(payload.get("source_mode")),
        "omc_backend": norm(payload.get("omc_backend")),
        "docker_image": norm(payload.get("docker_image")),
        "modelica_version": norm(payload.get("modelica_version")),
        "class_surface_key_count": len(class_candidates),
        "parameter_surface_key_count": len(parameter_records),
        "class_surface_total_candidate_count": sum(len(value or []) for value in class_candidates.values()),
        "parameter_surface_total_candidate_count": sum(len(value or []) for value in parameter_records.values()),
    }
    full_payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "summary": summary,
        "class_path_candidates": class_candidates,
        "parameter_surface_records": parameter_records,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "surface_index.json", full_payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.21 Surface Index",
                "",
                f"- status: `{summary.get('status')}`",
                f"- source_mode: `{summary.get('source_mode')}`",
                f"- modelica_version: `{summary.get('modelica_version')}`",
                f"- class_surface_key_count: `{summary.get('class_surface_key_count')}`",
                f"- parameter_surface_key_count: `{summary.get('parameter_surface_key_count')}`",
                "",
            ]
        ),
    )
    return full_payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.21 authoritative local surface index.")
    parser.add_argument("--out-dir", default=str(DEFAULT_SURFACE_INDEX_OUT_DIR))
    parser.add_argument("--fixture-only", action="store_true")
    args = parser.parse_args()
    payload = build_v0321_surface_index(out_dir=str(args.out_dir), use_fixture_only=bool(args.fixture_only))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(json.dumps({"status": summary.get("status"), "source_mode": summary.get("source_mode"), "modelica_version": summary.get("modelica_version")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
