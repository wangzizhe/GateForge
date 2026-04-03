from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_versioned_ci_fixtures import v0314_fixture_step_store_payload


SCHEMA_VERSION = "agent_modelica_v0_3_15_replay_sensitive_admission_spec"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPERIENCE_STORE = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_14_authority_trace_extraction_current" / "experience_store.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_15_replay_sensitive_admission_spec_current"

MAIN_RUNTIME_ANCHOR = {
    "dominant_stage_subtype": "stage_5_runtime_numerical_instability",
    "residual_signal_cluster": "stage_5_runtime_numerical_instability|division_by_zero",
}
MAIN_INITIALIZATION_ANCHOR = {
    "dominant_stage_subtype": "stage_4_initialization_singularity",
    "residual_signal_cluster": "stage_4_initialization_singularity|init_failure",
}
SUPPORTING_INITIALIZATION_ANCHOR = {
    "dominant_stage_subtype": "stage_1_parse_syntax",
    "residual_signal_cluster": "stage_1_parse_syntax|parse_lexer_error",
}


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def _step_rows(experience_payload: dict) -> list[dict]:
    rows = experience_payload.get("step_records")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _exact_match_inventory(experience_payload: dict) -> list[dict]:
    counts: dict[tuple[str, str], int] = {}
    for row in _step_rows(experience_payload):
        key = (
            _norm(row.get("dominant_stage_subtype")),
            _norm(row.get("residual_signal_cluster")),
        )
        if not all(key):
            continue
        counts[key] = counts.get(key, 0) + 1
    inventory = []
    for key, count in sorted(counts.items()):
        inventory.append(
            {
                "dominant_stage_subtype": key[0],
                "residual_signal_cluster": key[1],
                "step_count": count,
            }
        )
    return inventory


def has_exact_match_anchor(
    experience_payload: dict,
    *,
    dominant_stage_subtype: str,
    residual_signal_cluster: str,
) -> bool:
    stage_key = _norm(dominant_stage_subtype)
    cluster_key = _norm(residual_signal_cluster)
    if not stage_key or not cluster_key:
        return False
    for row in _step_rows(experience_payload):
        if _norm(row.get("dominant_stage_subtype")) != stage_key:
            continue
        if _norm(row.get("residual_signal_cluster")) != cluster_key:
            continue
        return True
    return False


def build_replay_sensitive_admission_spec(
    *,
    experience_store_path: str = str(DEFAULT_EXPERIENCE_STORE),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    experience_payload = _load_json(experience_store_path)
    if not experience_payload:
        experience_payload = v0314_fixture_step_store_payload()
    inventory = _exact_match_inventory(experience_payload)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if inventory else "EMPTY",
        "experience_store_path": str(Path(experience_store_path).resolve()) if Path(experience_store_path).exists() else str(experience_store_path),
        "admission_band": {
            "baseline_pass_rate_pct_min": 25.0,
            "baseline_pass_rate_pct_max": 85.0,
            "retrieval_ready_rate_pct_min": 60.0,
        },
        "required_properties": [
            "baseline_not_authority_saturated",
            "multiround_lane_not_deterministic_one_shot",
            "exact_match_retrieval_anchor_available",
            "not_terminal_or_repair_safety_blocked",
        ],
        "primary_candidate_families": [
            "runtime_same_cluster_harder_variant",
            "initialization_same_cluster_harder_variant",
        ],
        "supplementary_candidate_families": [
            "failure_bank_near_miss_variant",
        ],
        "retrieval_anchor_whitelist": {
            "runtime_primary_anchor": dict(MAIN_RUNTIME_ANCHOR),
            "initialization_primary_anchor": dict(MAIN_INITIALIZATION_ANCHOR),
            "initialization_supporting_anchor": dict(SUPPORTING_INITIALIZATION_ANCHOR),
        },
        "exact_match_inventory": inventory,
        "anchor_readiness": {
            "runtime_primary_anchor_ready": has_exact_match_anchor(experience_payload, **MAIN_RUNTIME_ANCHOR),
            "initialization_primary_anchor_ready": has_exact_match_anchor(experience_payload, **MAIN_INITIALIZATION_ANCHOR),
            "initialization_supporting_anchor_ready": has_exact_match_anchor(experience_payload, **SUPPORTING_INITIALIZATION_ANCHOR),
        },
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def render_markdown(payload: dict) -> str:
    anchor_readiness = payload.get("anchor_readiness") if isinstance(payload.get("anchor_readiness"), dict) else {}
    return "\n".join(
        [
            "# v0.3.15 Replay-Sensitive Admission Spec",
            "",
            f"- status: `{payload.get('status')}`",
            f"- exact_match_inventory_count: `{len(payload.get('exact_match_inventory') or [])}`",
            f"- runtime_primary_anchor_ready: `{anchor_readiness.get('runtime_primary_anchor_ready')}`",
            f"- initialization_primary_anchor_ready: `{anchor_readiness.get('initialization_primary_anchor_ready')}`",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.15 replay-sensitive admission spec.")
    parser.add_argument("--experience-store", default=str(DEFAULT_EXPERIENCE_STORE))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_replay_sensitive_admission_spec(
        experience_store_path=str(args.experience_store),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "inventory_count": len(payload.get("exact_match_inventory") or [])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
