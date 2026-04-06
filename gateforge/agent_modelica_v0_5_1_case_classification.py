from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_1_boundary_taxonomy import build_v051_boundary_taxonomy
from .agent_modelica_v0_5_1_common import (
    BOUNDARY_BUCKET_ORDER,
    DEFAULT_CLASSIFICATION_OUT_DIR,
    DEFAULT_TAXONOMY_OUT_DIR,
    DEFAULT_V050_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_1_frozen_slice_integrity import build_v051_frozen_slice_integrity
from .agent_modelica_v0_5_1_common import DEFAULT_INTEGRITY_OUT_DIR


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_case_classification"


def _classify_case(row: dict) -> dict[str, str]:
    slice_class = str(row.get("slice_class") or "")
    qualitative_bucket = str(row.get("qualitative_bucket") or "")
    family_id = str(row.get("family_id") or "")
    task_id = str(row.get("task_id") or "")
    dispatch_clean = "clean"

    if dispatch_clean == "dirty":
        return {
            "assigned_boundary_bucket": "dispatch_or_policy_limited",
            "classification_reason": "Dispatch attribution is dirty, so this case cannot be used as curriculum boundary evidence.",
            "family_envelope_status": "unknown_due_to_dirty_dispatch",
            "dispatch_clean_or_not": dispatch_clean,
        }

    if slice_class == "already-covered":
        return {
            "assigned_boundary_bucket": "covered_success",
            "classification_reason": "Case remains inside an already-supported family envelope and still reads as covered under widened real pressure.",
            "family_envelope_status": "inside_declared_envelope",
            "dispatch_clean_or_not": dispatch_clean,
        }

    if slice_class == "boundary-adjacent":
        if qualitative_bucket == "medium_cluster_boundary_pressure":
            return {
                "assigned_boundary_bucket": "bounded_uncovered_subtype_candidate",
                "classification_reason": "Case is still bounded and local, but it now presses beyond the declared medium-redeclare envelope.",
                "family_envelope_status": "outside_declared_but_bounded",
                "dispatch_clean_or_not": dispatch_clean,
            }
        return {
            "assigned_boundary_bucket": "covered_but_fragile",
            "classification_reason": "Case stays near a supported envelope but shows widened real pressure at the edge of that envelope.",
            "family_envelope_status": "inside_declared_envelope",
            "dispatch_clean_or_not": dispatch_clean,
        }

    if slice_class == "undeclared-but-bounded-candidate":
        return {
            "assigned_boundary_bucket": "bounded_uncovered_subtype_candidate",
            "classification_reason": "Case is outside the declared family envelope yet remains bounded and locally interpretable.",
            "family_envelope_status": "outside_declared_but_bounded",
            "dispatch_clean_or_not": dispatch_clean,
        }

    if "topology" in task_id or "open_world" in task_id or qualitative_bucket == "open_world_spillover":
        return {
            "assigned_boundary_bucket": "topology_or_open_world_spillover",
            "classification_reason": "Case clearly exceeds the bounded local repair regime.",
            "family_envelope_status": "beyond_bounded_local_regime",
            "dispatch_clean_or_not": dispatch_clean,
        }

    return {
        "assigned_boundary_bucket": "boundary_ambiguous",
        "classification_reason": "Case does not yet have a stable envelope interpretation.",
        "family_envelope_status": "boundary_ambiguous",
        "dispatch_clean_or_not": dispatch_clean,
    }


def build_v051_case_classification(
    *,
    v0_5_0_closeout_path: str = str(DEFAULT_V050_CLOSEOUT_PATH),
    frozen_slice_integrity_path: str = str(DEFAULT_INTEGRITY_OUT_DIR / "summary.json"),
    boundary_taxonomy_path: str = str(DEFAULT_TAXONOMY_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLASSIFICATION_OUT_DIR),
) -> dict:
    if not Path(frozen_slice_integrity_path).exists():
        build_v051_frozen_slice_integrity(v0_5_0_closeout_path=v0_5_0_closeout_path, out_dir=str(Path(frozen_slice_integrity_path).parent))
    if not Path(boundary_taxonomy_path).exists():
        build_v051_boundary_taxonomy(out_dir=str(Path(boundary_taxonomy_path).parent))

    closeout = load_json(v0_5_0_closeout_path)
    integrity = load_json(frozen_slice_integrity_path)
    taxonomy = load_json(boundary_taxonomy_path)
    candidate_pack = closeout.get("candidate_pack") if isinstance(closeout.get("candidate_pack"), dict) else {}
    rows = candidate_pack.get("task_rows") if isinstance(candidate_pack.get("task_rows"), list) else []

    classified_rows = []
    bucket_case_count_table = {bucket: 0 for bucket in BOUNDARY_BUCKET_ORDER}
    covered_case_count = 0
    boundary_case_count = 0
    unclassified_case_count = 0

    for row in rows:
        if not isinstance(row, dict):
            continue
        decision = _classify_case(row)
        enriched = dict(row)
        enriched.update(decision)
        classified_rows.append(enriched)
        bucket = decision["assigned_boundary_bucket"]
        bucket_case_count_table[bucket] = int(bucket_case_count_table.get(bucket) or 0) + 1
        if bucket in {"covered_success", "covered_but_fragile"}:
            covered_case_count += 1
        elif bucket == "boundary_ambiguous":
            unclassified_case_count += 1
        else:
            boundary_case_count += 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if bool(integrity.get("frozen_slice_integrity_ok")) else "FAIL",
        "v0_5_0_closeout_path": str(Path(v0_5_0_closeout_path).resolve()),
        "frozen_slice_integrity_path": str(Path(frozen_slice_integrity_path).resolve()),
        "boundary_taxonomy_path": str(Path(boundary_taxonomy_path).resolve()),
        "bucket_definition_table": taxonomy.get("bucket_definition_table"),
        "bucket_case_count_table": bucket_case_count_table,
        "covered_vs_boundary_case_split": {
            "covered_region_case_count": covered_case_count,
            "boundary_region_case_count": boundary_case_count,
        },
        "unclassified_case_count": unclassified_case_count,
        "case_rows": classified_rows,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_json(out_root / "case_rows.json", {"case_rows": classified_rows})
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.1 Case Classification",
                "",
                f"- unclassified_case_count: `{unclassified_case_count}`",
                f"- covered_region_case_count: `{covered_case_count}`",
                f"- boundary_region_case_count: `{boundary_case_count}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.1 case-level boundary classification audit.")
    parser.add_argument("--v0-5-0-closeout", default=str(DEFAULT_V050_CLOSEOUT_PATH))
    parser.add_argument("--frozen-slice-integrity", default=str(DEFAULT_INTEGRITY_OUT_DIR / "summary.json"))
    parser.add_argument("--boundary-taxonomy", default=str(DEFAULT_TAXONOMY_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLASSIFICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v051_case_classification(
        v0_5_0_closeout_path=str(args.v0_5_0_closeout),
        frozen_slice_integrity_path=str(args.frozen_slice_integrity),
        boundary_taxonomy_path=str(args.boundary_taxonomy),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "unclassified_case_count": payload.get("unclassified_case_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
