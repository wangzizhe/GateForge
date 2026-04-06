from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_1_case_classification import build_v051_case_classification
from .agent_modelica_v0_5_1_common import (
    DEFAULT_CLASSIFICATION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_READINESS_OUT_DIR,
    DEFAULT_V050_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_boundary_readiness"


def build_v051_boundary_readiness(
    *,
    v0_5_0_closeout_path: str = str(DEFAULT_V050_CLOSEOUT_PATH),
    case_classification_path: str = str(DEFAULT_CLASSIFICATION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_READINESS_OUT_DIR),
) -> dict:
    if not Path(case_classification_path).exists():
        build_v051_case_classification(v0_5_0_closeout_path=v0_5_0_closeout_path, out_dir=str(Path(case_classification_path).parent))

    classification = load_json(case_classification_path)
    bucket_counts = classification.get("bucket_case_count_table") if isinstance(classification.get("bucket_case_count_table"), dict) else {}
    total_count = sum(int(v or 0) for v in bucket_counts.values())
    unclassified = int(classification.get("unclassified_case_count") or 0)
    bounded_uncovered_count = int(bucket_counts.get("bounded_uncovered_subtype_candidate") or 0)
    spillover_count = int(bucket_counts.get("topology_or_open_world_spillover") or 0)
    policy_limited_count = int(bucket_counts.get("dispatch_or_policy_limited") or 0)
    covered_count = int(bucket_counts.get("covered_success") or 0) + int(bucket_counts.get("covered_but_fragile") or 0)

    boundary_map_ready = (
        unclassified == 0
        and (bounded_uncovered_count > 0 or spillover_count > 0)
        and policy_limited_count != bounded_uncovered_count
    )
    partial_ready = (
        not boundary_map_ready
        and unclassified <= 2
        and (bounded_uncovered_count > 0 or spillover_count > 0 or policy_limited_count > 0)
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if boundary_map_ready or partial_ready else "FAIL",
        "case_classification_path": str(Path(case_classification_path).resolve()),
        "boundary_map_ready": boundary_map_ready,
        "covered_region_stable": covered_count > 0,
        "bounded_uncovered_signal_present": bounded_uncovered_count > 0,
        "open_world_spillover_signal_present": spillover_count > 0,
        "policy_limited_region_present": policy_limited_count > 0,
        "unclassified_case_count": unclassified,
        "total_case_count": total_count,
        "bounded_uncovered_case_share_pct": round((100.0 * bounded_uncovered_count / total_count), 1) if total_count else 0.0,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.1 Boundary Readiness",
                "",
                f"- boundary_map_ready: `{boundary_map_ready}`",
                f"- bounded_uncovered_signal_present: `{payload.get('bounded_uncovered_signal_present')}`",
                f"- open_world_spillover_signal_present: `{payload.get('open_world_spillover_signal_present')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.1 boundary-map readiness adjudication.")
    parser.add_argument("--v0-5-0-closeout", default=str(DEFAULT_V050_CLOSEOUT_PATH))
    parser.add_argument("--case-classification", default=str(DEFAULT_CLASSIFICATION_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_READINESS_OUT_DIR))
    args = parser.parse_args()
    payload = build_v051_boundary_readiness(
        v0_5_0_closeout_path=str(args.v0_5_0_closeout),
        case_classification_path=str(args.case_classification),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "boundary_map_ready": payload.get("boundary_map_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
