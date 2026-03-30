from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_may_checkpoint_decision_v0_3_2"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_may_checkpoint_decision_v0_3_2"


def _load_json(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: str | Path, text: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _norm(value: object) -> str:
    return str(value or "").strip()


def _find_variance_row(matrix: dict, *, provider_name: str) -> dict:
    rows = matrix.get("variance_summary") if isinstance(matrix.get("variance_summary"), list) else []
    for row in rows:
        if isinstance(row, dict) and _norm(row.get("provider_name")) == provider_name:
            return row
    return {}


def _find_group_rows(matrix: dict, *, provider_name: str) -> list[dict]:
    rows = matrix.get("grouped_rows") if isinstance(matrix.get("grouped_rows"), list) else []
    return [row for row in rows if isinstance(row, dict) and _norm(row.get("provider_name")) == provider_name]


def build_may_checkpoint_decision(
    *,
    matrix_summary_path: str,
    claude_probe_summary_path: str,
    codex_probe_summary_path: str = "",
    slice_summary_path: str = "",
    out_dir: str = DEFAULT_OUT_DIR,
    min_repeated_runs: int = 3,
) -> dict:
    matrix = _load_json(matrix_summary_path)
    claude_probe = _load_json(claude_probe_summary_path)
    codex_probe = _load_json(codex_probe_summary_path) if _norm(codex_probe_summary_path) else {}
    slice_summary = _load_json(slice_summary_path) if _norm(slice_summary_path) else {}

    gateforge_rows = _find_group_rows(matrix, provider_name="gateforge")
    claude_rows = _find_group_rows(matrix, provider_name="claude")
    codex_rows = _find_group_rows(matrix, provider_name="codex")
    claude_variance = _find_variance_row(matrix, provider_name="claude")
    codex_variance = _find_variance_row(matrix, provider_name="codex")
    slice_status = _norm(slice_summary.get("status"))
    claude_mean_infra = float(claude_variance.get("mean_infra_failure_rate_pct") or 0.0)

    conditions = {
        "shared_oracle_runnable": bool(claude_probe.get("shared_tool_plane_reached")),
        "primary_external_baseline_runnable": bool(claude_probe.get("shared_tool_plane_reached")),
        "track_c_slice_audit_justified": slice_status in {"PASS", "SEED_READY", "NEEDS_MORE_GENERATION", "PRELIMINARY_NEEDS_MORE_EVIDENCE"},
        "paper_scale_primary_slice_ready": slice_status in {"PASS", "PRIMARY_READY"},
        "gateforge_authority_present": bool(gateforge_rows),
        "primary_external_repeated_runs_met": int(claude_variance.get("run_count") or 0) >= int(min_repeated_runs),
        "model_identity_reportable": bool(claude_rows) and all(_norm(row.get("model_id")) for row in claude_rows),
        "infra_failures_separated": bool(claude_rows) and all("infra_failure_rate_pct" in row for row in claude_rows),
        "primary_external_infra_stable": claude_mean_infra < 50.0 if claude_rows else False,
    }

    comparative_core_ready = all(
        [
            bool(conditions["shared_oracle_runnable"]),
            bool(conditions["primary_external_baseline_runnable"]),
            bool(conditions["track_c_slice_audit_justified"]),
            bool(conditions["gateforge_authority_present"]),
            bool(conditions["primary_external_repeated_runs_met"]),
            bool(conditions["model_identity_reportable"]),
            bool(conditions["infra_failures_separated"]),
        ]
    )
    if comparative_core_ready:
        if bool(conditions["paper_scale_primary_slice_ready"]) and bool(conditions["primary_external_infra_stable"]):
            classification = "comparative_path_retained"
        else:
            classification = "comparative_path_retained_provisional"
    else:
        classification = "fallback_path_locked"

    gateforge_best = max([float(row.get("infra_normalized_success_rate_pct") or 0.0) for row in gateforge_rows], default=0.0)
    claude_best = max([float(row.get("infra_normalized_success_rate_pct") or 0.0) for row in claude_rows], default=0.0)
    codex_best = max([float(row.get("infra_normalized_success_rate_pct") or 0.0) for row in codex_rows], default=0.0)

    comparative_path_retained = classification != "fallback_path_locked"
    strong_claim_candidate = gateforge_best >= claude_best + 5.0 and comparative_path_retained
    conservative_claim_candidate = comparative_path_retained

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if matrix else "FAIL",
        "classification": classification,
        "matrix_summary_path": str(Path(matrix_summary_path).resolve()) if Path(matrix_summary_path).exists() else str(matrix_summary_path),
        "claude_probe_summary_path": str(Path(claude_probe_summary_path).resolve()) if Path(claude_probe_summary_path).exists() else str(claude_probe_summary_path),
        "codex_probe_summary_path": str(Path(codex_probe_summary_path).resolve()) if _norm(codex_probe_summary_path) and Path(codex_probe_summary_path).exists() else str(codex_probe_summary_path),
        "slice_summary_path": str(Path(slice_summary_path).resolve()) if _norm(slice_summary_path) and Path(slice_summary_path).exists() else str(slice_summary_path),
        "conditions": conditions,
        "metrics": {
            "gateforge_best_infra_normalized_success_rate_pct": round(gateforge_best, 2),
            "claude_best_infra_normalized_success_rate_pct": round(claude_best, 2),
            "codex_best_infra_normalized_success_rate_pct": round(codex_best, 2),
            "claude_run_count": int(claude_variance.get("run_count") or 0),
            "codex_run_count": int(codex_variance.get("run_count") or 0),
        },
        "claim_drafts": {
            "strong_comparative_claim_candidate": bool(strong_claim_candidate),
            "conservative_claim_candidate": bool(conservative_claim_candidate),
        },
        "notes": [
            "Claude + shared OMC MCP is treated as the primary external baseline for the May decision.",
            "Codex is supplementary for v0.3.2 and does not block the primary comparative-path decision.",
            "A provisional classification means the comparative route is retained at decision-gate scale, but either the paper-scale primary slice or infra stability still needs follow-up.",
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# May Checkpoint Decision v0.3.2",
                "",
                f"- classification: `{payload['classification']}`",
                f"- shared_oracle_runnable: `{conditions['shared_oracle_runnable']}`",
                f"- primary_external_repeated_runs_met: `{conditions['primary_external_repeated_runs_met']}`",
                f"- gateforge_best_infra_normalized_success_rate_pct: `{payload['metrics']['gateforge_best_infra_normalized_success_rate_pct']}`",
                f"- claude_best_infra_normalized_success_rate_pct: `{payload['metrics']['claude_best_infra_normalized_success_rate_pct']}`",
                f"- codex_best_infra_normalized_success_rate_pct: `{payload['metrics']['codex_best_infra_normalized_success_rate_pct']}`",
                f"- strong_comparative_claim_candidate: `{payload['claim_drafts']['strong_comparative_claim_candidate']}`",
                f"- conservative_claim_candidate: `{payload['claim_drafts']['conservative_claim_candidate']}`",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.2 May checkpoint decision summary.")
    parser.add_argument("--matrix-summary", required=True)
    parser.add_argument("--claude-probe-summary", required=True)
    parser.add_argument("--codex-probe-summary", default="")
    parser.add_argument("--slice-summary", default="")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-repeated-runs", type=int, default=3)
    args = parser.parse_args()
    payload = build_may_checkpoint_decision(
        matrix_summary_path=str(args.matrix_summary),
        claude_probe_summary_path=str(args.claude_probe_summary),
        codex_probe_summary_path=str(args.codex_probe_summary),
        slice_summary_path=str(args.slice_summary),
        out_dir=str(args.out_dir),
        min_repeated_runs=int(args.min_repeated_runs),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
