from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_16_preservation_lane_freeze"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROBE_SUMMARY = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_live_residual_probe_current" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_preservation_lane_freeze_current"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: str | Path) -> dict:
    target = Path(path)
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def build_preservation_lane_freeze(
    *,
    probe_summary_path: str = str(DEFAULT_PROBE_SUMMARY),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    probe = _load_json(probe_summary_path)
    admitted_count = int(probe.get("probe_admitted_candidate_count") or 0)
    lane_status = "PRESERVATION_LANE_READY" if admitted_count >= 4 else "RESIDUAL_PRESERVATION_NOT_READY"
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "probe_summary_path": str(Path(probe_summary_path).resolve()) if Path(probe_summary_path).exists() else str(probe_summary_path),
        "probe_admitted_candidate_count": admitted_count,
        "probe_admitted_rate_pct": probe.get("probe_admitted_rate_pct"),
        "lane_status": lane_status,
        "decision_reason": (
            "probe_admitted_candidate_count_meets_minimum_lane_threshold"
            if admitted_count >= 4
            else "probe_path_failed_to_preserve_historical_residual_clusters"
        ),
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.16 Preservation Lane Freeze",
                "",
                f"- lane_status: `{lane_status}`",
                f"- probe_admitted_candidate_count: `{admitted_count}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze the v0.3.16 preservation-valid lane.")
    parser.add_argument("--probe-summary", default=str(DEFAULT_PROBE_SUMMARY))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_preservation_lane_freeze(probe_summary_path=str(args.probe_summary), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "lane_status": payload.get("lane_status")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
