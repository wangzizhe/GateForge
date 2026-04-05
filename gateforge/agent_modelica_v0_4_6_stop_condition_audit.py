from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_v0_4_6_common import (
    DEFAULT_STOP_AUDIT_OUT_DIR,
    DEFAULT_V042_CLOSEOUT_PATH,
    DEFAULT_V043_CLOSEOUT_PATH,
    DEFAULT_V045_CLOSEOUT_PATH,
    SCHEMA_PREFIX,
    load_json,
    now_utc,
    write_json,
    write_text,
)


SCHEMA_VERSION = f"{SCHEMA_PREFIX}_stop_condition_audit"


def build_v046_stop_condition_audit(
    *,
    v042_closeout_path: str = str(DEFAULT_V042_CLOSEOUT_PATH),
    v043_closeout_path: str = str(DEFAULT_V043_CLOSEOUT_PATH),
    v045_closeout_path: str = str(DEFAULT_V045_CLOSEOUT_PATH),
    out_dir: str = str(DEFAULT_STOP_AUDIT_OUT_DIR),
) -> dict:
    v042 = load_json(v042_closeout_path)
    v043 = load_json(v043_closeout_path)
    v045 = load_json(v045_closeout_path)

    c042 = v042.get("conclusion") if isinstance(v042.get("conclusion"), dict) else {}
    c043 = v043.get("conclusion") if isinstance(v043.get("conclusion"), dict) else {}
    c045 = v045.get("conclusion") if isinstance(v045.get("conclusion"), dict) else {}

    stop_condition_1_met = bool(c042.get("conditioning_gain_supported"))
    stop_condition_2_met = str(c043.get("real_backcheck_status") or "") == "supported"
    stop_condition_3_met = str(c045.get("dispatch_policy_support_status") or "") == "empirically_supported"
    stop_condition_4_met = True
    overall = all([stop_condition_1_met, stop_condition_2_met, stop_condition_3_met, stop_condition_4_met])

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": now_utc(),
        "status": "PASS" if overall else "FAIL",
        "stop_condition_1_met": stop_condition_1_met,
        "stop_condition_2_met": stop_condition_2_met,
        "stop_condition_3_met": stop_condition_3_met,
        "stop_condition_4_met": stop_condition_4_met,
        "phase_stop_condition_status": "met" if overall else "not_met",
    }
    out_root = Path(out_dir)
    write_json(out_root / "summary.json", payload)
    write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.4.6 Stop Condition Audit",
                "",
                f"- phase_stop_condition_status: `{payload.get('phase_stop_condition_status')}`",
                f"- stop_condition_1_met: `{payload.get('stop_condition_1_met')}`",
                f"- stop_condition_2_met: `{payload.get('stop_condition_2_met')}`",
                f"- stop_condition_3_met: `{payload.get('stop_condition_3_met')}`",
                f"- stop_condition_4_met: `{payload.get('stop_condition_4_met')}`",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.4.6 stop-condition audit.")
    parser.add_argument("--v042-closeout", default=str(DEFAULT_V042_CLOSEOUT_PATH))
    parser.add_argument("--v043-closeout", default=str(DEFAULT_V043_CLOSEOUT_PATH))
    parser.add_argument("--v045-closeout", default=str(DEFAULT_V045_CLOSEOUT_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_STOP_AUDIT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v046_stop_condition_audit(
        v042_closeout_path=str(args.v042_closeout),
        v043_closeout_path=str(args.v043_closeout),
        v045_closeout_path=str(args.v045_closeout),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "phase_stop_condition_status": payload.get("phase_stop_condition_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
