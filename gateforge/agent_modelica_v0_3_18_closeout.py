from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_18_stage2_characterization import build_stage2_characterization
from .agent_modelica_v0_3_18_stage2_common import (
    DEFAULT_CHARACTERIZATION_OUT_DIR,
    DEFAULT_CLOSEOUT_OUT_DIR,
    DEFAULT_DIAGNOSIS_OUT_DIR,
    DEFAULT_SAMPLE_MANIFEST_OUT_DIR,
    DEFAULT_TARGETING_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    norm,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_18_stage2_diagnosis import build_stage2_diagnosis
from .agent_modelica_v0_3_18_stage2_family_targeting import build_stage2_family_targeting
from .agent_modelica_v0_3_18_stage2_sample_manifest import build_stage2_sample_manifest


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_closeout"


def build_v0318_closeout(
    *,
    sample_manifest_path: str = str(DEFAULT_SAMPLE_MANIFEST_OUT_DIR / "manifest.json"),
    diagnosis_path: str = str(DEFAULT_DIAGNOSIS_OUT_DIR / "records.json"),
    characterization_path: str = str(DEFAULT_CHARACTERIZATION_OUT_DIR / "summary.json"),
    targeting_path: str = str(DEFAULT_TARGETING_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_CLOSEOUT_OUT_DIR),
) -> dict:
    if not Path(sample_manifest_path).exists():
        build_stage2_sample_manifest(out_dir=str(Path(sample_manifest_path).parent))
    if not Path(diagnosis_path).exists():
        build_stage2_diagnosis(sample_manifest_path=sample_manifest_path, out_dir=str(Path(diagnosis_path).parent))
    if not Path(characterization_path).exists():
        build_stage2_characterization(diagnosis_path=diagnosis_path, out_dir=str(Path(characterization_path).parent))
    if not Path(targeting_path).exists():
        build_stage2_family_targeting(characterization_path=characterization_path, out_dir=str(Path(targeting_path).parent))

    sample_manifest = load_json(sample_manifest_path)
    diagnosis = load_json(diagnosis_path)
    characterization = load_json(characterization_path)
    targeting = load_json(targeting_path)

    authority_confirmation_status = norm(diagnosis.get("authority_confirmation_status")) or "PENDING_USER_CONFIRMATION"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "closeout_status": (
            "STAGE2_ACTIONABILITY_AUDIT_DRAFT_READY"
            if authority_confirmation_status == "PENDING_USER_CONFIRMATION"
            else "STAGE2_ACTIONABILITY_AUDIT_READY"
        ),
        "authority_confirmation_status": authority_confirmation_status,
        "sample_manifest": {
            "status": norm(sample_manifest.get("status")),
            "sample_count": int(sample_manifest.get("sample_count") or 0),
        },
        "diagnosis": {
            "status": norm(diagnosis.get("status")),
            "record_count": int(diagnosis.get("record_count") or 0),
        },
        "characterization": {
            "status": norm(characterization.get("status")),
            "provisional_version_decision": norm(characterization.get("provisional_version_decision")),
            "dominant_target_action_type": norm(characterization.get("dominant_target_action_type")),
        },
        "targeting": {
            "status": norm(targeting.get("status")),
            "target_repair_action_types": list(targeting.get("target_repair_action_types") or []),
            "mutation_sketch_count": len(targeting.get("mutation_sketches") or []),
        },
        "conclusion": {
            "provisional_version_decision": norm(characterization.get("provisional_version_decision")) or "stage_2_partially_repairable",
            "summary": "The draft audit identifies a repairable stage_2 subset centered on component API alignment, but authority closeout still requires user confirmation of the human-repairability judgments.",
            "next_version_target": "v0.3.19 should target component_api_alignment mutations on simple/medium models before expanding into global structural repair families.",
        },
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.18 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- authority_confirmation_status: `{payload.get('authority_confirmation_status')}`",
                f"- provisional_version_decision: `{(payload.get('conclusion') or {}).get('provisional_version_decision')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.18 closeout draft.")
    parser.add_argument("--sample-manifest", default=str(DEFAULT_SAMPLE_MANIFEST_OUT_DIR / "manifest.json"))
    parser.add_argument("--diagnosis", default=str(DEFAULT_DIAGNOSIS_OUT_DIR / "records.json"))
    parser.add_argument("--characterization", default=str(DEFAULT_CHARACTERIZATION_OUT_DIR / "summary.json"))
    parser.add_argument("--targeting", default=str(DEFAULT_TARGETING_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_CLOSEOUT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0318_closeout(
        sample_manifest_path=str(args.sample_manifest),
        diagnosis_path=str(args.diagnosis),
        characterization_path=str(args.characterization),
        targeting_path=str(args.targeting),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "closeout_status": payload.get("closeout_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
