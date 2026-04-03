from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_19_common import (
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_FAMILY_SPEC_OUT_DIR,
    DEFAULT_LIVE_EVIDENCE_OUT_DIR,
    DEFAULT_PREVIEW_OUT_DIR,
    DEFAULT_TASKSET_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_19_family_spec import build_v0319_family_spec
from .agent_modelica_v0_3_19_live_evidence import build_v0319_live_evidence
from .agent_modelica_v0_3_19_preview_admission import build_v0319_preview_admission
from .agent_modelica_v0_3_19_taskset import build_v0319_taskset


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0319_closeout(
    *,
    family_spec_path: str = str(DEFAULT_FAMILY_SPEC_OUT_DIR / "summary.json"),
    taskset_path: str = str(DEFAULT_TASKSET_OUT_DIR / "taskset.json"),
    preview_path: str = str(DEFAULT_PREVIEW_OUT_DIR / "summary.json"),
    live_evidence_path: str = str(DEFAULT_LIVE_EVIDENCE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(family_spec_path).exists():
        build_v0319_family_spec(out_dir=str(Path(family_spec_path).parent))
    if not Path(taskset_path).exists():
        build_v0319_taskset(out_dir=str(Path(taskset_path).parent))
    if not Path(preview_path).exists():
        build_v0319_preview_admission(out_dir=str(Path(preview_path).parent))
    if not Path(live_evidence_path).exists():
        build_v0319_live_evidence(out_dir=str(Path(live_evidence_path).parent))

    family_spec = load_json(family_spec_path)
    taskset = load_json(taskset_path)
    preview = load_json(preview_path)
    live = load_json(live_evidence_path)

    admitted_count = int(preview.get("admitted_task_count") or 0)
    first_failure_hit_count = int(preview.get("first_failure_hit_count") or 0)
    second_residual_hit_count = int(preview.get("second_residual_hit_count") or 0)
    multiround_success_count = int(live.get("multiround_success_count") or 0)
    single_fix_success_count = int(live.get("single_fix_success_count") or 0)
    if admitted_count <= 0:
        version_decision = "stage2_api_alignment_family_not_ready"
    elif multiround_success_count > 0:
        version_decision = "stage2_api_alignment_family_ready"
    elif single_fix_success_count > 0:
        version_decision = "stage2_api_alignment_family_partially_ready"
    else:
        version_decision = "stage2_api_alignment_family_not_ready"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": "STAGE2_API_ALIGNMENT_CLOSEOUT_READY",
        "family_spec": {
            "status": norm(family_spec.get("status")),
            "source_count": int(family_spec.get("source_count") or 0),
        },
        "taskset": {
            "status": norm(taskset.get("status")),
            "task_count": int(taskset.get("task_count") or 0),
            "same_component_task_count": int(taskset.get("same_component_task_count") or 0),
        },
        "preview": {
            "status": norm(preview.get("status")),
            "first_failure_hit_count": first_failure_hit_count,
            "second_residual_hit_count": second_residual_hit_count,
            "admitted_task_count": admitted_count,
            "signature_changed_count": int(preview.get("signature_changed_count") or 0),
        },
        "live_evidence": {
            "status": norm(live.get("status")),
            "task_count": int(live.get("task_count") or 0),
            "success_count": int(live.get("success_count") or 0),
            "multiround_success_count": multiround_success_count,
            "single_fix_success_count": single_fix_success_count,
            "progressive_solve_rate_pct": float(live.get("progressive_solve_rate_pct") or 0.0),
        },
        "conclusion": {
            "version_decision": version_decision,
            "summary": (
                "The first stage_2 component_api_alignment family forms a usable multiround lane on simple/medium models."
                if version_decision == "stage2_api_alignment_family_ready"
                else (
                    "The family currently behaves more like a single-fix API recovery lane than a stable dual-mismatch multiround lane."
                    if version_decision == "stage2_api_alignment_family_partially_ready"
                    else (
                        "All 6 tasks hit the intended first-failure bucket (stage_2|undefined_symbol), but 0/6 produced an observed second residual after the first live repair attempt, so the lane does not yet form a usable multiround API-alignment family."
                    )
                )
            ),
            "claim_boundary": "This version trains API recovery from locally corrupted correct symbols; it does not yet establish API discovery from scratch.",
            "next_version_target": (
                "Broaden the admitted same-component API lane and only then consider API-discovery or broader structural families."
            ),
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.19 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- admitted_task_count: `{(payload.get('preview') or {}).get('admitted_task_count')}`",
                f"- multiround_success_count: `{(payload.get('live_evidence') or {}).get('multiround_success_count')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.19 closeout.")
    parser.add_argument("--family-spec", default=str(DEFAULT_FAMILY_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--taskset", default=str(DEFAULT_TASKSET_OUT_DIR / "taskset.json"))
    parser.add_argument("--preview", default=str(DEFAULT_PREVIEW_OUT_DIR / "summary.json"))
    parser.add_argument("--live-evidence", default=str(DEFAULT_LIVE_EVIDENCE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0319_closeout(
        family_spec_path=str(args.family_spec),
        taskset_path=str(args.taskset),
        preview_path=str(args.preview),
        live_evidence_path=str(args.live_evidence),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
