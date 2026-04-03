from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_16_closeout"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_residual_preservation_audit_current" / "summary.json"
DEFAULT_MUTATION_SPEC = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_preservation_mutation_spec_current" / "summary.json"
DEFAULT_PROBE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_live_residual_probe_current" / "summary.json"
DEFAULT_LANE_FREEZE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_preservation_lane_freeze_current" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_closeout_current"


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


def build_v0316_closeout(
    *,
    audit_path: str = str(DEFAULT_AUDIT),
    mutation_spec_path: str = str(DEFAULT_MUTATION_SPEC),
    probe_path: str = str(DEFAULT_PROBE),
    lane_freeze_path: str = str(DEFAULT_LANE_FREEZE),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    audit = _load_json(audit_path)
    mutation_spec = _load_json(mutation_spec_path)
    probe = _load_json(probe_path)
    lane_freeze = _load_json(lane_freeze_path)
    lane_status = str(lane_freeze.get("lane_status") or "")
    version_decision = (
        "residual_preservation_lane_ready"
        if lane_status == "PRESERVATION_LANE_READY"
        else "residual_preservation_not_ready"
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "closeout_status": "RESIDUAL_PRESERVATION_READY" if version_decision == "residual_preservation_lane_ready" else "RESIDUAL_PRESERVATION_NOT_READY",
        "audit": {
            "status": audit.get("status"),
            "step_store_sampling_timepoint": audit.get("step_store_sampling_timepoint"),
            "primary_drift_cause": ((audit.get("preservation_failure_taxonomy") or {}).get("primary_drift_cause")),
        },
        "mutation_spec": {
            "status": mutation_spec.get("status"),
            "primary_drift_cause": mutation_spec.get("primary_drift_cause"),
        },
        "probe": {
            "status": probe.get("status"),
            "probe_mode": probe.get("probe_mode"),
            "probe_admitted_candidate_count": probe.get("probe_admitted_candidate_count"),
            "observed_probe_stage_counts": probe.get("observed_probe_stage_counts"),
        },
        "lane_freeze": {
            "lane_status": lane_status,
            "decision_reason": lane_freeze.get("decision_reason"),
        },
        "conclusion": {
            "version_decision": version_decision,
            "primary_bottleneck": (
                "deterministic_probe_path_not_aligned_with_historical_preserved_residuals"
                if version_decision == "residual_preservation_not_ready"
                else "none"
            ),
            "summary": (
                "The v0.3.16 preservation-control probe did not reproduce the historical preserved residual clusters under the current deterministic cleanup path, so the version closes without a preservation-valid lane."
                if version_decision == "residual_preservation_not_ready"
                else "A preservation-valid control lane was frozen with enough probe-admitted candidates to support the next replay-sensitive version."
            ),
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.16 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{version_decision}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.16 closeout summary.")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--mutation-spec", default=str(DEFAULT_MUTATION_SPEC))
    parser.add_argument("--probe", default=str(DEFAULT_PROBE))
    parser.add_argument("--lane-freeze", default=str(DEFAULT_LANE_FREEZE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0316_closeout(
        audit_path=str(args.audit),
        mutation_spec_path=str(args.mutation_spec),
        probe_path=str(args.probe),
        lane_freeze_path=str(args.lane_freeze),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": ((payload.get("conclusion") or {}).get("version_decision"))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
