from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_10_0_candidate_validator import evaluate_candidate_rows
from .agent_modelica_v0_10_2_common import (
    DEFAULT_SOURCE_ADMISSION_OUT_DIR,
    MIN_NEW_REAL_SOURCE_MAINLINE_YIELD,
    SCHEMA_PREFIX,
    now_utc,
    write_json,
    write_text,
)


SOURCE_DISCOVERY_SPECS = [
    {
        "source_id": "open_source_issue_archive_ibpsa",
        "source_type": "repository_issue_workflow",
        "source_origin_class": "real_origin",
        "expected_real_origin_distance": "medium",
        "source_collection_method": "local_issue_reference_extraction",
        "source_provenance_description": "IBPSA issue-linked maintenance traces from local media and fluid example models, centered on media consistency and package compatibility followups.",
        "workflow_family_coverage_estimate": [
            "media_record_maintenance",
            "fluid_package_compatibility_maintenance",
        ],
        "estimated_mainline_real_origin_yield": 2,
        "proxy_leakage_risk_note": "Medium because the tasks are normalized from issue-linked library maintenance traces rather than imported from prior GateForge scaffolding.",
        "candidate_rows": [
            {
                "task_id": "v102_ibpsa_media_restore_record_consistency",
                "source_id": "open_source_issue_archive_ibpsa",
                "source_record_id": "ibpsa_media_record_consistency",
                "family_id": "media_record_maintenance",
                "workflow_task_template_id": "restore_media_record_consistency",
                "complexity_tier": "complex",
                "real_origin_authenticity_audit": {
                    "source_provenance": "IBPSA issue-linked media-model maintenance trace extracted from local source comments and examples",
                    "source_origin_class": "real_origin",
                    "real_origin_distance": "medium",
                    "workflow_legitimacy_pass": True,
                    "real_origin_authenticity_pass": True,
                    "real_origin_authenticity_audit_pass": True,
                },
                "anti_proxy_leakage_audit": {
                    "proxy_leakage_risk_present": True,
                    "proxy_leakage_risk_level": "medium",
                    "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "The task is anchored in external library maintenance traces and does not depend on any v0.8 or v0.9 workflow framing.",
                    "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                    "anti_proxy_leakage_audit_pass": True,
                },
            },
            {
                "task_id": "v102_ibpsa_fluid_restore_package_compatibility",
                "source_id": "open_source_issue_archive_ibpsa",
                "source_record_id": "ibpsa_fluid_package_compatibility",
                "family_id": "fluid_package_compatibility_maintenance",
                "workflow_task_template_id": "restore_fluid_package_compatibility",
                "complexity_tier": "medium",
                "real_origin_authenticity_audit": {
                    "source_provenance": "IBPSA issue-linked fluid package compatibility trace extracted from local package examples",
                    "source_origin_class": "real_origin",
                    "real_origin_distance": "near",
                    "workflow_legitimacy_pass": True,
                    "real_origin_authenticity_pass": True,
                    "real_origin_authenticity_audit_pass": True,
                },
                "anti_proxy_leakage_audit": {
                    "proxy_leakage_risk_present": False,
                    "proxy_leakage_risk_level": "low",
                    "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "This task remains a direct library-maintenance demand with native provenance.",
                    "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                    "anti_proxy_leakage_audit_pass": True,
                },
            },
        ],
    },
    {
        "source_id": "semi_real_origin_review_digest",
        "source_type": "maintenance_record_digest",
        "source_origin_class": "semi_real_origin",
        "expected_real_origin_distance": "medium",
        "source_collection_method": "local_comment_digest",
        "source_provenance_description": "Semi-structured review digest built from local maintenance notes that suggest plausible follow-up work but do not preserve one-to-one upstream provenance.",
        "workflow_family_coverage_estimate": ["review_followup_only"],
        "estimated_mainline_real_origin_yield": 0,
        "proxy_leakage_risk_note": "Admissible only as side bucket because the upstream signal is aggregated rather than directly traceable to one real-origin demand.",
        "candidate_rows": [
            {
                "task_id": "v102_semi_review_followup_digest",
                "source_id": "semi_real_origin_review_digest",
                "source_record_id": "semi_review_followup_01",
                "family_id": "review_followup_only",
                "workflow_task_template_id": "review_followup_only",
                "complexity_tier": "medium",
                "real_origin_authenticity_audit": {
                    "source_provenance": "Aggregated review digest from local maintenance notes",
                    "source_origin_class": "semi_real_origin",
                    "real_origin_distance": "medium",
                    "workflow_legitimacy_pass": True,
                    "real_origin_authenticity_pass": True,
                    "real_origin_authenticity_audit_pass": True,
                },
                "anti_proxy_leakage_audit": {
                    "proxy_leakage_risk_present": True,
                    "proxy_leakage_risk_level": "medium",
                    "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "The task is not proxy-like, but its provenance remains aggregated and therefore side-bucket only.",
                    "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": False,
                    "anti_proxy_leakage_audit_pass": True,
                },
            }
        ],
    },
    {
        "source_id": "proxy_repackaged_v10_digest",
        "source_type": "workflow_proximal_proxy_archive",
        "source_origin_class": "workflow_proximal_proxy",
        "expected_real_origin_distance": "far",
        "source_collection_method": "proxy_digest",
        "source_provenance_description": "Digest that explicitly repackages earlier GateForge real-origin expansion artifacts as if they were fresh mainline tasks.",
        "workflow_family_coverage_estimate": ["proxy_reference_only"],
        "estimated_mainline_real_origin_yield": 0,
        "proxy_leakage_risk_note": "High because the source is defined entirely in terms of prior GateForge scaffolding.",
        "candidate_rows": [
            {
                "task_id": "v102_proxy_repackaged_real_origin_row",
                "source_id": "proxy_repackaged_v10_digest",
                "source_record_id": "proxy_v10_digest_01",
                "family_id": "proxy_reference_only",
                "workflow_task_template_id": "proxy_reference_only",
                "complexity_tier": "medium",
                "real_origin_authenticity_audit": {
                    "source_provenance": "Digest row built directly from prior v0.10 expansion artifacts",
                    "source_origin_class": "workflow_proximal_proxy",
                    "real_origin_distance": "far",
                    "workflow_legitimacy_pass": True,
                    "real_origin_authenticity_pass": False,
                    "real_origin_authenticity_audit_pass": False,
                },
                "anti_proxy_leakage_audit": {
                    "proxy_leakage_risk_present": True,
                    "proxy_leakage_risk_level": "high",
                    "why_this_task_is_or_is_not_just_a_repackaged_workflow_proximal_task": "This source is only a repackaged GateForge artifact and exists to prove proxy rejection.",
                    "task_definition_depends_on_known_v0_8_or_v0_9_scaffolding": True,
                    "anti_proxy_leakage_audit_pass": False,
                },
            }
        ],
    },
]


def _inspect_source(spec: dict) -> dict:
    candidate_rows = list(spec.get("candidate_rows") or [])
    evaluations = evaluate_candidate_rows(candidate_rows)
    admitted_candidates = [row for row, verdict in zip(candidate_rows, evaluations) if verdict.get("admitted")]
    mainline_candidates = [verdict for verdict in evaluations if verdict.get("mainline_counted")]

    provenance_present = bool(str(spec.get("source_provenance_description") or "").strip())
    source_origin_class = str(spec.get("source_origin_class") or "")
    source_admission_pass = False
    rejection_reason = ""
    if not provenance_present:
        rejection_reason = "source_provenance_missing"
    elif source_origin_class == "workflow_proximal_proxy":
        rejection_reason = "source_is_workflow_proximal_proxy"
    elif source_origin_class == "real_origin":
        source_admission_pass = len(mainline_candidates) >= MIN_NEW_REAL_SOURCE_MAINLINE_YIELD
        if not source_admission_pass:
            rejection_reason = "source_yield_below_real_origin_growth_floor"
    elif source_origin_class == "semi_real_origin":
        source_admission_pass = len(admitted_candidates) >= 1
        if not source_admission_pass:
            rejection_reason = "semi_real_source_failed_side_bucket_admission"
    else:
        rejection_reason = "unknown_source_origin_class"

    return {
        "source_id": spec["source_id"],
        "source_type": spec["source_type"],
        "source_origin_class": source_origin_class,
        "expected_real_origin_distance": spec["expected_real_origin_distance"],
        "source_collection_method": spec["source_collection_method"],
        "source_provenance_description": spec["source_provenance_description"],
        "workflow_family_coverage_estimate": list(spec.get("workflow_family_coverage_estimate") or []),
        "estimated_mainline_real_origin_yield": int(spec.get("estimated_mainline_real_origin_yield") or 0),
        "proxy_leakage_risk_note": spec["proxy_leakage_risk_note"],
        "governance_passing_candidate_count": len(admitted_candidates),
        "mainline_real_origin_candidate_count": len(mainline_candidates),
        "source_admission_pass": source_admission_pass,
        "source_rejection_reason": rejection_reason,
        "candidate_rows": candidate_rows,
        "candidate_row_evaluations": evaluations,
    }


def build_v102_candidate_source_admission(
    *,
    out_dir: str = str(DEFAULT_SOURCE_ADMISSION_OUT_DIR),
) -> dict:
    out_root = Path(out_dir)
    inspected = [_inspect_source(spec) for spec in SOURCE_DISCOVERY_SPECS]
    admitted = [row for row in inspected if row.get("source_admission_pass")]
    rejected = [row for row in inspected if not row.get("source_admission_pass")]
    admitted_real_sources = [row for row in admitted if row.get("source_origin_class") == "real_origin"]
    admitted_semi_real_sources = [row for row in admitted if row.get("source_origin_class") == "semi_real_origin"]

    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_candidate_source_admission",
        "generated_at_utc": now_utc(),
        "status": "PASS" if admitted_real_sources else "FAIL",
        "candidate_source_intake_table": inspected,
        "real_origin_source_expansion_ledger": {
            "inspected_source_count": len(inspected),
            "admitted_source_count": len(admitted),
            "admitted_real_origin_source_count": len(admitted_real_sources),
            "admitted_semi_real_source_count": len(admitted_semi_real_sources),
            "rejected_source_count": len(rejected),
        },
        "newly_admitted_source_registry": [
            {
                "source_id": row["source_id"],
                "source_type": row["source_type"],
                "source_origin_class": row["source_origin_class"],
                "expected_real_origin_distance": row["expected_real_origin_distance"],
                "source_provenance_description": row["source_provenance_description"],
                "source_collection_method": row["source_collection_method"],
                "workflow_family_coverage_estimate": row["workflow_family_coverage_estimate"],
                "estimated_mainline_real_origin_yield": row["estimated_mainline_real_origin_yield"],
                "governance_passing_candidate_count": row["governance_passing_candidate_count"],
                "mainline_real_origin_candidate_count": row["mainline_real_origin_candidate_count"],
            }
            for row in admitted
        ],
        "source_admission_decision_table": [
            {
                "source_id": row["source_id"],
                "source_origin_class": row["source_origin_class"],
                "source_admission_pass": row["source_admission_pass"],
                "source_rejection_reason": row["source_rejection_reason"],
                "mainline_real_origin_candidate_count": row["mainline_real_origin_candidate_count"],
            }
            for row in inspected
        ],
    }
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.10.2 Candidate Source Admission",
                "",
                f"- admitted_real_origin_source_count: `{len(admitted_real_sources)}`",
                f"- admitted_semi_real_source_count: `{len(admitted_semi_real_sources)}`",
                f"- rejected_source_count: `{len(rejected)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.10.2 candidate source admission artifact.")
    parser.add_argument("--out-dir", default=str(DEFAULT_SOURCE_ADMISSION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v102_candidate_source_admission(out_dir=str(args.out_dir))
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "admitted_real_origin_source_count": payload["real_origin_source_expansion_ledger"][
                    "admitted_real_origin_source_count"
                ],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
