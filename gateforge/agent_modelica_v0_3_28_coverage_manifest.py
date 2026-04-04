from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_28_common import (
    DEFAULT_MANIFEST_OUT_DIR,
    DUAL_RECHECK_SPECS,
    SCHEMA_PREFIX,
    SINGLE_MISMATCH_SPECS,
    build_v0328_source_specs,
    norm,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_coverage_manifest"


def _count_by(rows: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = norm(row.get(key))
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def build_v0328_coverage_manifest(*, out_dir: str = str(DEFAULT_MANIFEST_OUT_DIR)) -> dict:
    sources = build_v0328_source_specs()
    single_rows = [dict(row) for row in SINGLE_MISMATCH_SPECS]
    dual_rows = [dict(row) for row in DUAL_RECHECK_SPECS]
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if len(single_rows) >= 28 and len(dual_rows) >= 16 else "FAIL",
        "source_count": len(sources),
        "single_task_count": len(single_rows),
        "dual_sidecar_task_count": len(dual_rows),
        "source_tier_counts": _count_by(sources, "complexity_tier"),
        "single_family_mix": _count_by(single_rows, "component_family"),
        "single_patch_type_counts": _count_by(single_rows, "patch_type"),
        "single_tier_counts": _count_by(single_rows, "complexity_tier"),
        "dual_family_mix": _count_by(dual_rows, "component_family"),
        "dual_tier_counts": _count_by(dual_rows, "complexity_tier"),
        "dual_placement_kind_counts": _count_by(dual_rows, "placement_kind"),
        "frozen_single_task_ids": [norm(row.get("task_id")) for row in single_rows],
        "frozen_dual_task_ids": [norm(row.get("task_id")) for row in dual_rows],
    }
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "summary": summary,
        "sources": sources,
        "single_task_specs": single_rows,
        "dual_task_specs": dual_rows,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", summary)
    write_json(out_root / "manifest.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.28 Coverage Manifest",
                "",
                f"- status: `{summary.get('status')}`",
                f"- source_count: `{summary.get('source_count')}`",
                f"- single_task_count: `{summary.get('single_task_count')}`",
                f"- dual_sidecar_task_count: `{summary.get('dual_sidecar_task_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.28 widened neighbor-component local-interface discovery manifest.")
    parser.add_argument("--out-dir", default=str(DEFAULT_MANIFEST_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0328_coverage_manifest(out_dir=str(args.out_dir))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    print(
        json.dumps(
            {
                "status": summary.get("status"),
                "single_task_count": summary.get("single_task_count"),
                "dual_sidecar_task_count": summary.get("dual_sidecar_task_count"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
