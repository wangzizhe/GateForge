from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_5_2_common import (
    DEFAULT_ADJUDICATION_OUT_DIR,
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_ENTRY_TRIAGE_OUT_DIR,
    DEFAULT_SIGNAL_AUDIT_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_5_2_entry_spec import build_v052_entry_spec
from .agent_modelica_v0_5_2_entry_triage import build_v052_entry_triage
from .agent_modelica_v0_5_2_signal_audit import build_v052_signal_audit


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_expansion_adjudication"


def build_v052_expansion_adjudication(
    *,
    signal_audit_path: str = str(DEFAULT_SIGNAL_AUDIT_OUT_DIR / "summary.json"),
    entry_triage_path: str = str(DEFAULT_ENTRY_TRIAGE_OUT_DIR / "summary.json"),
    entry_spec_path: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_ADJUDICATION_OUT_DIR),
) -> dict:
    if not Path(signal_audit_path).exists():
        build_v052_signal_audit(out_dir=str(Path(signal_audit_path).parent))
    if not Path(entry_triage_path).exists():
        build_v052_entry_triage(signal_audit_path=str(signal_audit_path), out_dir=str(Path(entry_triage_path).parent))
    if not Path(entry_spec_path).exists():
        build_v052_entry_spec(entry_triage_path=str(entry_triage_path), out_dir=str(Path(entry_spec_path).parent))

    signal = load_json(signal_audit_path)
    triage = load_json(entry_triage_path)
    spec = load_json(entry_spec_path)

    recurring_signal_supported = bool(signal.get("recurring_signal_supported"))
    entry_candidate_boundedness_supported = bool(triage.get("entry_candidate_boundedness_supported"))
    entry_not_policy_residue = bool(triage.get("entry_not_policy_residue"))
    entry_spec_ready = bool(spec.get("entry_spec_ready"))
    entry_ready = (
        recurring_signal_supported
        and entry_candidate_boundedness_supported
        and entry_spec_ready
        and entry_not_policy_residue
    )
    targeted_expansion_supported = entry_ready

    support_gap_table = []
    if not recurring_signal_supported:
        support_gap_table.append("recurring_signal_not_supported")
    if not entry_candidate_boundedness_supported:
        support_gap_table.append("entry_candidate_not_bounded_enough")
    if not entry_not_policy_residue:
        support_gap_table.append("entry_still_reads_as_policy_residue")
    if not entry_spec_ready:
        support_gap_table.append("entry_spec_not_ready")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "signal_audit_path": str(Path(signal_audit_path).resolve()),
        "entry_triage_path": str(Path(entry_triage_path).resolve()),
        "entry_spec_path": str(Path(entry_spec_path).resolve()),
        "targeted_expansion_supported": targeted_expansion_supported,
        "entry_ready": entry_ready,
        "entry_not_policy_residue": entry_not_policy_residue,
        "support_gap_table": support_gap_table,
    }

    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.5.2 Expansion Adjudication",
                "",
                f"- targeted_expansion_supported: `{targeted_expansion_supported}`",
                f"- entry_ready: `{entry_ready}`",
                f"- entry_not_policy_residue: `{entry_not_policy_residue}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.5.2 targeted-expansion adjudication.")
    parser.add_argument("--signal-audit", default=str(DEFAULT_SIGNAL_AUDIT_OUT_DIR / "summary.json"))
    parser.add_argument("--entry-triage", default=str(DEFAULT_ENTRY_TRIAGE_OUT_DIR / "summary.json"))
    parser.add_argument("--entry-spec", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_ADJUDICATION_OUT_DIR))
    args = parser.parse_args()
    payload = build_v052_expansion_adjudication(
        signal_audit_path=str(args.signal_audit),
        entry_triage_path=str(args.entry_triage),
        entry_spec_path=str(args.entry_spec),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "entry_ready": payload.get("entry_ready")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
