from __future__ import annotations

import argparse
from pathlib import Path

from .agent_modelica_v0_7_1_live_run import _simulate_case
from .agent_modelica_v0_7_2_common import (
    DEFAULT_LIVE_RUN_OUT_DIR,
    DEFAULT_PROFILE_EXTENSION_OUT_DIR,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


def build_v072_live_run(
    *,
    profile_extension_path: str = str(DEFAULT_PROFILE_EXTENSION_OUT_DIR / "summary.json"),
    out_dir: str = str(DEFAULT_LIVE_RUN_OUT_DIR),
) -> dict:
    profile_extension = load_json(profile_extension_path)
    rows = list(profile_extension.get("task_rows") or [])
    case_result_table = [_simulate_case(row) for row in rows]
    payload = {
        "schema_version": f"{SCHEMA_PREFIX}_live_run",
        "generated_at_utc": now_utc(),
        "status": "PASS",
        "slice_extension_mode": profile_extension.get("slice_extension_mode"),
        "live_run_case_count": len(case_result_table),
        "case_result_table": case_result_table,
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.7.2 Live Run",
                "",
                f"- live_run_case_count: `{len(case_result_table)}`",
                f"- slice_extension_mode: `{profile_extension.get('slice_extension_mode')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.7.2 live run summary.")
    parser.add_argument(
        "--profile-extension",
        default=str(DEFAULT_PROFILE_EXTENSION_OUT_DIR / "summary.json"),
    )
    parser.add_argument("--out-dir", default=str(DEFAULT_LIVE_RUN_OUT_DIR))
    args = parser.parse_args()
    payload = build_v072_live_run(
        profile_extension_path=str(args.profile_extension),
        out_dir=str(args.out_dir),
    )
    print(payload["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
