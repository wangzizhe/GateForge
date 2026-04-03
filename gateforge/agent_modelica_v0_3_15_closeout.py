from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_15_closeout"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADMISSION_SPEC = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_replay_sensitive_admission_spec_current" / "summary.json"
DEFAULT_CANDIDATE_PREVIEW = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_candidate_preview_current" / "summary.json"
DEFAULT_BASELINE_GATE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_baseline_gate_current" / "summary.json"
DEFAULT_REPLAY_EVIDENCE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_replay_evidence_current" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_closeout_current"


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


def build_v0315_closeout(
    *,
    admission_spec_path: str = str(DEFAULT_ADMISSION_SPEC),
    candidate_preview_path: str = str(DEFAULT_CANDIDATE_PREVIEW),
    baseline_gate_path: str = str(DEFAULT_BASELINE_GATE),
    replay_evidence_path: str = str(DEFAULT_REPLAY_EVIDENCE),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    admission_spec = _load_json(admission_spec_path)
    candidate_preview = _load_json(candidate_preview_path)
    baseline_gate = _load_json(baseline_gate_path)
    replay_evidence = _load_json(replay_evidence_path)
    replay_decision = str(replay_evidence.get("version_decision") or "")
    if replay_decision in {
        "replay_sensitive_gain_confirmed",
        "replay_sensitive_eval_built_but_gain_weak",
        "replay_sensitive_eval_not_ready",
    }:
        version_decision = replay_decision
    else:
        version_decision = "replay_sensitive_eval_not_ready"
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "closeout_status": "REPLAY_SENSITIVE_EVAL_READY" if version_decision != "replay_sensitive_eval_not_ready" else "REPLAY_SENSITIVE_EVAL_NOT_READY",
        "admission_spec": {
            "status": admission_spec.get("status"),
            "runtime_primary_anchor_ready": ((admission_spec.get("anchor_readiness") or {}).get("runtime_primary_anchor_ready")),
            "initialization_primary_anchor_ready": ((admission_spec.get("anchor_readiness") or {}).get("initialization_primary_anchor_ready")),
        },
        "candidate_lane": {
            "total_task_count": candidate_preview.get("total_task_count"),
            "preview_admitted_count": candidate_preview.get("preview_admitted_count"),
            "admitted_for_baseline_count": candidate_preview.get("admitted_for_baseline_count"),
        },
        "baseline_gate": {
            "decision": baseline_gate.get("decision"),
            "baseline_band_status": baseline_gate.get("baseline_band_status"),
            "retrieval_gate_status": baseline_gate.get("retrieval_gate_status"),
            "admitted_eval_task_count": baseline_gate.get("admitted_eval_task_count"),
            "admitted_baseline": baseline_gate.get("admitted_baseline"),
        },
        "replay_evidence": {
            "version_decision": replay_decision,
            "delta": replay_evidence.get("delta"),
            "replay_hit_rate_pct": ((replay_evidence.get("replay") or {}).get("replay_hit_rate_pct")),
        },
        "conclusion": {
            "version_decision": version_decision,
            "primary_bottleneck": _primary_bottleneck(version_decision, baseline_gate),
            "summary": _summary_text(version_decision, baseline_gate, replay_evidence),
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", summary)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.15 Closeout",
                "",
                f"- closeout_status: `{summary.get('closeout_status')}`",
                f"- version_decision: `{version_decision}`",
                "",
            ]
        ),
    )
    return summary


def _summary_text(version_decision: str, baseline_gate: dict, replay_evidence: dict) -> str:
    if version_decision == "replay_sensitive_gain_confirmed":
        return "A replay-sensitive eval slice was built with acceptable retrieval coverage and replay produced measurable gain on the admitted slice."
    if version_decision == "replay_sensitive_eval_built_but_gain_weak":
        return "A replay-sensitive eval slice was built and replay was consumed, but the replay deltas remained weak on the admitted slice."
    return (
        "The candidate lane did not produce a replay-sensitive admitted slice that was both in-band and retrieval-compatible, "
        "so the version closes without a replay gain claim."
    )


def _primary_bottleneck(version_decision: str, baseline_gate: dict) -> str:
    if version_decision != "replay_sensitive_eval_not_ready":
        return "gain_not_established_after_eval_build"
    if str(baseline_gate.get("retrieval_gate_status") or "") == "retrieval_coverage_fail":
        return "candidate_lane_drifted_outside_exact_match_keyspace"
    if str(baseline_gate.get("baseline_band_status") or "") in {"baseline_too_hard", "baseline_out_of_band"}:
        return "candidate_lane_too_hard_for_replay_sensitive_band"
    return "candidate_lane_not_ready"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.15 closeout summary.")
    parser.add_argument("--admission-spec", default=str(DEFAULT_ADMISSION_SPEC))
    parser.add_argument("--candidate-preview", default=str(DEFAULT_CANDIDATE_PREVIEW))
    parser.add_argument("--baseline-gate", default=str(DEFAULT_BASELINE_GATE))
    parser.add_argument("--replay-evidence", default=str(DEFAULT_REPLAY_EVIDENCE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_v0315_closeout(
        admission_spec_path=str(args.admission_spec),
        candidate_preview_path=str(args.candidate_preview),
        baseline_gate_path=str(args.baseline_gate),
        replay_evidence_path=str(args.replay_evidence),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "version_decision": ((payload.get("conclusion") or {}).get("version_decision"))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
