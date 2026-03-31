from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_3_closeout"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_v0_3_3_closeout"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm(value: object) -> str:
    return str(value or "").strip()


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


def build_v0_3_3_closeout(
    *,
    primary_slice_summary_path: str,
    paper_matrix_summary_path: str,
    claude_stability_summary_path: str,
    claim_gate_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
) -> dict:
    primary_slice = _load_json(primary_slice_summary_path)
    paper_matrix = _load_json(paper_matrix_summary_path)
    stability = _load_json(claude_stability_summary_path)
    claim_gate = _load_json(claim_gate_summary_path)

    provider_rows = paper_matrix.get("provider_rows") if isinstance(paper_matrix.get("provider_rows"), list) else []
    by_provider = {
        _norm(row.get("provider_name")): row
        for row in provider_rows
        if isinstance(row, dict) and _norm(row.get("provider_name"))
    }
    gateforge = by_provider.get("gateforge", {})
    claude = by_provider.get("claude", {})
    codex = by_provider.get("codex", {})

    primary_ready = _norm(primary_slice.get("status")) == "PRIMARY_READY"
    claude_stable = _norm(stability.get("classification")) == "STABLE"
    claude_clean_runs = int((stability.get("metrics") or {}).get("clean_run_count") or 0)
    claude_main_table_eligible = bool(claude.get("main_table_eligible"))
    switch_required = bool(stability.get("switch_required"))

    if primary_ready and claude_stable and claude_clean_runs >= 3 and claude_main_table_eligible:
        classification = "paper_usable_comparative_path"
    elif switch_required:
        classification = "cli_unstable_api_direct_fallback"
    else:
        classification = "comparative_path_retained_provisional"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if primary_slice and paper_matrix and stability and claim_gate else "FAIL",
        "classification": classification,
        "primary_slice_summary_path": str(Path(primary_slice_summary_path).resolve()) if Path(primary_slice_summary_path).exists() else str(primary_slice_summary_path),
        "paper_matrix_summary_path": str(Path(paper_matrix_summary_path).resolve()) if Path(paper_matrix_summary_path).exists() else str(paper_matrix_summary_path),
        "claude_stability_summary_path": str(Path(claude_stability_summary_path).resolve()) if Path(claude_stability_summary_path).exists() else str(claude_stability_summary_path),
        "claim_gate_summary_path": str(Path(claim_gate_summary_path).resolve()) if Path(claim_gate_summary_path).exists() else str(claim_gate_summary_path),
        "metrics": {
            "primary_slice_status": _norm(primary_slice.get("status")),
            "primary_slice_admitted_count": int(primary_slice.get("admitted_count") or 0),
            "planner_sensitive_pct": float(primary_slice.get("planner_sensitive_pct") or 0.0),
            "deterministic_only_pct": float(primary_slice.get("deterministic_only_pct") or 0.0),
            "gateforge_median_success_rate_pct": float(gateforge.get("median_infra_normalized_success_rate_pct") or 0.0),
            "claude_median_success_rate_pct": float(claude.get("median_infra_normalized_success_rate_pct") or 0.0),
            "codex_median_success_rate_pct": float(codex.get("median_infra_normalized_success_rate_pct") or 0.0),
            "claude_clean_run_count": claude_clean_runs,
            "claude_main_table_eligible": bool(claude_main_table_eligible),
            "codex_clean_run_count": int(codex.get("clean_run_count") or 0),
            "strong_claim_candidate": bool((claim_gate.get("claim_drafts") or {}).get("strong_comparative_claim_candidate")),
            "conservative_claim_candidate": bool((claim_gate.get("claim_drafts") or {}).get("conservative_claim_candidate")),
        },
        "notes": [
            "paper_usable_comparative_path requires a PRIMARY_READY slice plus a stable Claude baseline with at least 3 clean runs.",
            "cli_unstable_api_direct_fallback is triggered only when the Claude stability gate requests a switch.",
            "Codex remains supplementary for v0.3.3 and does not block the primary release classification.",
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.3 Closeout",
                "",
                f"- classification: `{payload['classification']}`",
                f"- primary_slice_status: `{payload['metrics']['primary_slice_status']}`",
                f"- primary_slice_admitted_count: `{payload['metrics']['primary_slice_admitted_count']}`",
                f"- planner_sensitive_pct: `{payload['metrics']['planner_sensitive_pct']}`",
                f"- deterministic_only_pct: `{payload['metrics']['deterministic_only_pct']}`",
                f"- claude_clean_run_count: `{payload['metrics']['claude_clean_run_count']}`",
                f"- claude_main_table_eligible: `{payload['metrics']['claude_main_table_eligible']}`",
                f"- strong_claim_candidate: `{payload['metrics']['strong_claim_candidate']}`",
                f"- conservative_claim_candidate: `{payload['metrics']['conservative_claim_candidate']}`",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.3 release closeout summary.")
    parser.add_argument("--primary-slice-summary", required=True)
    parser.add_argument("--paper-matrix-summary", required=True)
    parser.add_argument("--claude-stability-summary", required=True)
    parser.add_argument("--claim-gate-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_v0_3_3_closeout(
        primary_slice_summary_path=str(args.primary_slice_summary),
        paper_matrix_summary_path=str(args.paper_matrix_summary),
        claude_stability_summary_path=str(args.claude_stability_summary),
        claim_gate_summary_path=str(args.claim_gate_summary),
        out_dir=str(args.out_dir),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))


if __name__ == "__main__":
    main()
