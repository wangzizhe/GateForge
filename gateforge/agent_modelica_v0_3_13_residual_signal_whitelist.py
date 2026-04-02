from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_13_residual_signal_whitelist"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_13_residual_signal_whitelist"

DEFAULT_SIGNAL_CLUSTERS = [
    {
        "cluster_id": "runtime_parameter_recovery",
        "status": "ACTIVE",
        "agent_provenance": "v0.3.5 numeric recovery sweep",
        "allowed_stage_subtypes": [
            "stage_5_runtime_numerical_instability",
        ],
        "allowed_error_types": [
            "numerical_instability",
        ],
        "reason_tokens_any": [
            "division by zero",
            "assertion",
            "integrator failed",
            "solver divergence",
        ],
        "recommended_family_ids": [
            "surface_cleanup_then_parameter_recovery",
        ],
        "rationale": "Matches the v0.3.5 collapse-family residual that the current agent can already convert into numeric parameter recovery.",
    },
    {
        "cluster_id": "initialization_parameter_recovery",
        "status": "ACTIVE",
        "agent_provenance": "v0.3.5 post-restore initialization recovery",
        "allowed_stage_subtypes": [
            "stage_4_initialization_singularity",
        ],
        "allowed_error_types": [
            "simulate_error",
        ],
        "reason_tokens_any": [
            "initialization failed",
            "initial conditions",
            "singular",
            "initialization",
        ],
        "recommended_family_ids": [
            "surface_cleanup_then_parameter_recovery",
            "surface_cleanup_then_residual_branch_choice",
        ],
        "rationale": "Matches the v0.3.5 sign-flip residual where deterministic cleanup exposes an initialization-singularity task the current agent can read.",
    },
]


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


def _write_json(path: str | Path, payload: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def build_residual_signal_whitelist(*, out_dir: str = DEFAULT_OUT_DIR) -> dict:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "cluster_count": len(DEFAULT_SIGNAL_CLUSTERS),
        "clusters": DEFAULT_SIGNAL_CLUSTERS,
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(out_root / "summary.md", render_markdown(payload))
    return payload


def match_residual_signal_cluster(*, diagnostic: dict, whitelist_payload: dict) -> dict:
    clusters = whitelist_payload.get("clusters")
    if not isinstance(clusters, list):
        return {}

    stage_subtype = _norm(diagnostic.get("stage_subtype") or diagnostic.get("dominant_stage_subtype"))
    error_type = _norm(diagnostic.get("error_type"))
    reason = _norm(diagnostic.get("reason"))
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        allowed_stage_subtypes = {_norm(x) for x in cluster.get("allowed_stage_subtypes") or []}
        allowed_error_types = {_norm(x) for x in cluster.get("allowed_error_types") or []}
        reason_tokens_any = [_norm(x) for x in cluster.get("reason_tokens_any") or [] if _norm(x)]
        if stage_subtype not in allowed_stage_subtypes:
            continue
        if error_type not in allowed_error_types:
            continue
        if reason_tokens_any and not any(token in reason for token in reason_tokens_any):
            continue
        return cluster
    return {}


def render_markdown(payload: dict) -> str:
    lines = [
        "# Residual Signal Whitelist v0.3.13",
        "",
        f"- status: `{payload.get('status')}`",
        f"- cluster_count: `{payload.get('cluster_count')}`",
        "",
        "## Active Clusters",
        "",
    ]
    for cluster in payload.get("clusters") or []:
        if not isinstance(cluster, dict):
            continue
        lines.append(
            "- "
            + f"`{cluster.get('cluster_id')}` "
            + f"(stages={','.join(cluster.get('allowed_stage_subtypes') or [])}; "
            + f"errors={','.join(cluster.get('allowed_error_types') or [])})"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.13 residual signal whitelist.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_residual_signal_whitelist(out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "cluster_count": payload.get("cluster_count")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
