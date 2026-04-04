from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_3_29_common import (
    DEFAULT_ENTRY_SPEC_OUT_DIR,
    DEFAULT_PATCH_CONTRACT_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    norm,
    now_utc,
    write_json,
    write_text,
)
from .agent_modelica_v0_3_29_entry_family_spec import build_v0329_entry_family_spec


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_patch_contract"


def build_v0329_patch_contract(
    *,
    entry_spec_path: str = str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_PATCH_CONTRACT_OUT_DIR),
) -> dict:
    if not Path(entry_spec_path).exists():
        build_v0329_entry_family_spec(out_dir=str(Path(entry_spec_path).parent))
    entry_spec = load_json(entry_spec_path)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if norm(entry_spec.get("selected_family")) else "FAIL",
        "selected_family": norm(entry_spec.get("selected_family")),
        "allowed_patch_types": list(entry_spec.get("allowed_patch_types") or []),
        "max_patch_count_per_round": int(entry_spec.get("max_patch_count_per_round") or 1),
        "allowed_patch_scope": norm(entry_spec.get("allowed_patch_scope")),
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.29 Patch Contract",
                "",
                f"- status: `{payload.get('status')}`",
                f"- selected_family: `{payload.get('selected_family')}`",
                f"- allowed_patch_types: `{', '.join(payload.get('allowed_patch_types') or [])}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.29 patch contract.")
    parser.add_argument("--entry-spec", default=str(DEFAULT_ENTRY_SPEC_OUT_DIR / "summary.json"))
    parser.add_argument("--out-dir", default=str(DEFAULT_PATCH_CONTRACT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0329_patch_contract(entry_spec_path=str(args.entry_spec), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "selected_family": payload.get("selected_family")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
