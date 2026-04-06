from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_0_common import (
    DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR,
    DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR,
    DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR,
    LEGACY_BUCKET_MAPPING_RATE_MIN,
    SCHEMA_PREFIX,
    SPILLOVER_PARTIAL_MAX,
    SPILLOVER_READY_MAX,
    TASK_COUNT_MIN,
    UNCLASSIFIED_PENDING_MAX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v070_substrate_admission(
    *,
    substrate_path: str = str(DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR / "summary.json"),
    audit_path: str = str(DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR),
) -> dict:
    substrate = load_json(substrate_path)
    audit = load_json(audit_path)

    task_count = int(substrate["task_count"])
    weaker = bool(substrate["weaker_curation_confirmed"])
    mapping = float(audit["legacy_bucket_mapping_rate_pct"])
    dispatch = str(audit["dispatch_cleanliness_level"])
    spillover = float(audit["spillover_share_pct"])
    unclassified = int(audit["unclassified_pending_taxonomy_count"])

    invalid = any(
        [
            not weaker,
            task_count < TASK_COUNT_MIN,
            mapping < LEGACY_BUCKET_MAPPING_RATE_MIN,
            dispatch == "failed",
            spillover > SPILLOVER_PARTIAL_MAX,
            unclassified > UNCLASSIFIED_PENDING_MAX,
        ]
    )
    ready = all(
        [
            weaker,
            task_count >= TASK_COUNT_MIN,
            mapping >= LEGACY_BUCKET_MAPPING_RATE_MIN,
            dispatch == "promoted",
            spillover <= SPILLOVER_READY_MAX,
            unclassified <= UNCLASSIFIED_PENDING_MAX,
        ]
    )
    if invalid:
        admission = "invalid"
    elif ready:
        admission = "ready"
    else:
        admission = "partial"

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_substrate_admission",
        "generated_at_utc": now_utc(),
        "status": "PASS" if admission in {"ready", "partial"} else "FAIL",
        "substrate_admission_status": admission,
        "weaker_curation_confirmed": weaker,
        "legacy_bucket_mapping_rate_pct": mapping,
        "dispatch_cleanliness_level": dispatch,
        "spillover_share_pct": spillover,
        "unclassified_pending_taxonomy_count": unclassified,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.0 Substrate Admission",
                "",
                f"- substrate_admission_status: `{admission}`",
                f"- weaker_curation_confirmed: `{weaker}`",
                f"- legacy_bucket_mapping_rate_pct: `{mapping}`",
                f"- dispatch_cleanliness_level: `{dispatch}`",
                f"- spillover_share_pct: `{spillover}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.0 substrate admission summary.")
    parser.add_argument(
        "--substrate-path",
        default=str(DEFAULT_OPEN_WORLD_ADJACENT_SUBSTRATE_OUT_DIR / "summary.json"),
    )
    parser.add_argument(
        "--audit-path",
        default=str(DEFAULT_LEGACY_BUCKET_AUDIT_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_SUBSTRATE_ADMISSION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v070_substrate_admission(
        substrate_path=str(args.substrate_path),
        audit_path=str(args.audit_path),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
