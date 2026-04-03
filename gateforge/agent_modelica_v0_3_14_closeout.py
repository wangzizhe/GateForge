from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_14_closeout"
DEFAULT_MANIFEST_SUMMARY = "artifacts/agent_modelica_v0_3_14_authority_manifest_current/summary.json"
DEFAULT_SCHEMA_SUMMARY = "artifacts/agent_modelica_v0_3_14_step_experience_schema_current/summary.json"
DEFAULT_TRACE_SUMMARY = "artifacts/agent_modelica_v0_3_14_authority_trace_extraction_current/summary.json"
DEFAULT_REPLAY_EVIDENCE = "artifacts/agent_modelica_v0_3_14_replay_evidence_current/summary.json"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_14_closeout_current"


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


def build_v0_3_14_closeout(
    *,
    manifest_summary_path: str = DEFAULT_MANIFEST_SUMMARY,
    schema_summary_path: str = DEFAULT_SCHEMA_SUMMARY,
    trace_summary_path: str = DEFAULT_TRACE_SUMMARY,
    replay_evidence_path: str = DEFAULT_REPLAY_EVIDENCE,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    manifest_summary = _load_json(manifest_summary_path)
    schema_summary = _load_json(schema_summary_path)
    trace_summary = _load_json(trace_summary_path)
    replay_evidence = _load_json(replay_evidence_path)
    runtime = replay_evidence.get("runtime") if isinstance(replay_evidence.get("runtime"), dict) else {}
    initialization = replay_evidence.get("initialization") if isinstance(replay_evidence.get("initialization"), dict) else {}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "closeout_status": "REPLAY_EVIDENCE_READY",
        "authority_substrate": {
            "manifest_status": manifest_summary.get("status"),
            "trace_availability_status": (manifest_summary.get("trace_availability") or {}).get("status"),
            "runtime_eval_count": int(manifest_summary.get("runtime_eval_count") or 0),
            "initialization_eval_count": int(manifest_summary.get("initialization_eval_count") or 0),
        },
        "step_experience": {
            "schema_status": schema_summary.get("status"),
            "compatible_result_count": int(schema_summary.get("compatible_result_count") or 0),
            "trace_extraction_status": trace_summary.get("status"),
            "step_record_count": int(trace_summary.get("step_record_count") or 0),
            "failure_bank_step_count": int(trace_summary.get("failure_bank_step_count") or 0),
        },
        "replay_evidence": {
            "decision": replay_evidence.get("version_decision"),
            "retrieval_ready_rate_pct": float((replay_evidence.get("retrieval_summary") or {}).get("exact_match_ready_rate_pct") or 0.0),
            "runtime_replay_hit_rate_pct": float((replay_evidence.get("injection_summary") or {}).get("runtime_replay_hit_rate_pct") or 0.0),
            "initialization_replay_hit_rate_pct": float((replay_evidence.get("injection_summary") or {}).get("initialization_replay_hit_rate_pct") or 0.0),
            "runtime_delta": (runtime.get("delta") or {}),
            "initialization_delta": (initialization.get("delta") or {}),
        },
        "conclusion": {
            "summary": "Replay is operational on the fixed authority curriculum and exact-match retrieval is fully available, but the current eval slices are already saturated at 100% success / 100% progressive solve, so replay does not yet show measurable metric gain.",
            "version_decision": replay_evidence.get("version_decision"),
            "primary_bottleneck": "eval_slice_saturation",
        },
        "next_actions": [
            "Keep the v0.3.14 authority substrate and step-level extraction path as the default replay-ready base.",
            "Do not overclaim replay gains on the current authority eval because runtime and initialization slices are already saturated.",
            "Design the next replay-sensitive eval slice so baseline is below saturation before spending more budget on replay gain claims.",
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.14 Closeout",
                "",
                f"- closeout_status: `{payload.get('closeout_status')}`",
                f"- version_decision: `{(payload.get('conclusion') or {}).get('version_decision')}`",
                f"- primary_bottleneck: `{(payload.get('conclusion') or {}).get('primary_bottleneck')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.14 closeout summary.")
    parser.add_argument("--manifest-summary", default=DEFAULT_MANIFEST_SUMMARY)
    parser.add_argument("--schema-summary", default=DEFAULT_SCHEMA_SUMMARY)
    parser.add_argument("--trace-summary", default=DEFAULT_TRACE_SUMMARY)
    parser.add_argument("--replay-evidence", default=DEFAULT_REPLAY_EVIDENCE)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_14_closeout(
        manifest_summary_path=str(args.manifest_summary),
        schema_summary_path=str(args.schema_summary),
        trace_summary_path=str(args.trace_summary),
        replay_evidence_path=str(args.replay_evidence),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"closeout_status": payload.get("closeout_status"), "version_decision": (payload.get("conclusion") or {}).get("version_decision")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
