from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_2_common import (
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_ENTRY_TRIAGE_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_2_entry_triage import build_v052_entry_triage


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_entry_spec"


def build_v052_entry_spec(
    *,
    entry_triage_path: str = str(DEFAULT_ENTRY_TRIAGE_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR),
) -> dict:
    if not Path(entry_triage_path).exists():
        build_v052_entry_triage(out_dir=str(Path(entry_triage_path).parent))

    triage = load_json(entry_triage_path)
    selected_entry_pattern_id = str(triage.get("selected_entry_pattern_id") or "")
    allowed_patch_types = ["replace_redeclare_medium_package_path", "align_local_medium_redeclare_clause"]
    anti_expansion_boundary_rules = [
        "disallow topology-heavy patch or cross-component network rewrite",
        "disallow cross-stage scope expansion beyond local medium redeclare alignment",
    ]
    entry_spec_ready = bool(triage.get("entry_candidate_boundedness_supported")) and len(anti_expansion_boundary_rules) >= 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "entry_triage_path": str(Path(entry_triage_path).resolve()),
        "selected_entry_pattern_id": selected_entry_pattern_id,
        "entry_subtype_scope": "bounded local medium-redeclare pressure on fluid-network / medium-cluster slices",
        "entry_spec_ready": entry_spec_ready,
        "allowed_patch_types": allowed_patch_types,
        "target_first_failure_bucket": "stage_2_structural_balance_reference|undefined_symbol",
        "anti_expansion_boundary_rules": anti_expansion_boundary_rules,
        "dual_sidecar_expectation": "optional_first_pass_only_after_entry_ready",
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.2 Entry Spec",
                "",
                f"- selected_entry_pattern_id: `{selected_entry_pattern_id}`",
                f"- entry_spec_ready: `{entry_spec_ready}`",
                f"- allowed_patch_types: `{', '.join(allowed_patch_types)}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.2 targeted-expansion entry spec.")
    parser.add_argument("--entry-triage", default=str(DEFAULT_ENTRY_TRIAGE_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR))
    args = parser.parse_args()
    payload = build_v052_entry_spec(entry_triage_path=str(args.entry_triage), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "entry_spec_ready": payload.get("entry_spec_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
