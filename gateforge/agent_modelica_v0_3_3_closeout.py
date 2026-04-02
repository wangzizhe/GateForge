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


def _infer_external_provider_names(paper_matrix: dict) -> list[str]:
    rows = paper_matrix.get("provider_rows") if isinstance(paper_matrix.get("provider_rows"), list) else []
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _norm(row.get("provider_name")).lower()
        if not name or name == "gateforge" or name in names:
            continue
        names.append(name)
    return names


def build_v0_3_3_closeout(
    *,
    primary_slice_summary_path: str,
    paper_matrix_summary_path: str,
    primary_provider_stability_summary_path: str = "",
    claim_gate_summary_path: str,
    out_dir: str = DEFAULT_OUT_DIR,
    prefer_development_shift: bool = False,
    primary_provider_name: str = "",
    secondary_provider_name: str = "",
) -> dict:
    primary_provider_name = _norm(primary_provider_name).lower()
    secondary_provider_name = _norm(secondary_provider_name).lower()
    primary_provider_stability_summary_path = _norm(primary_provider_stability_summary_path)
    primary_slice = _load_json(primary_slice_summary_path)
    paper_matrix = _load_json(paper_matrix_summary_path)
    inferred_names = _infer_external_provider_names(paper_matrix)
    if not primary_provider_name:
        primary_provider_name = inferred_names[0] if inferred_names else ""
    if not secondary_provider_name:
        secondary_provider_name = next((name for name in inferred_names if name != primary_provider_name), "")
    stability = _load_json(primary_provider_stability_summary_path)
    claim_gate = _load_json(claim_gate_summary_path)

    provider_rows = paper_matrix.get("provider_rows") if isinstance(paper_matrix.get("provider_rows"), list) else []
    by_provider = {
        _norm(row.get("provider_name")): row
        for row in provider_rows
        if isinstance(row, dict) and _norm(row.get("provider_name"))
    }
    gateforge = by_provider.get("gateforge", {})
    primary_external = by_provider.get(primary_provider_name, {})
    secondary_external = by_provider.get(secondary_provider_name, {})

    primary_ready = _norm(primary_slice.get("status")) == "PRIMARY_READY"
    primary_metrics = primary_slice.get("metrics") if isinstance(primary_slice.get("metrics"), dict) else {}
    primary_external_stable = _norm(stability.get("classification")) == "STABLE"
    primary_external_clean_runs = int((stability.get("metrics") or {}).get("clean_run_count") or 0)
    primary_external_main_table_eligible = bool(primary_external.get("main_table_eligible"))
    switch_required = bool(stability.get("switch_required"))

    if primary_ready and primary_external_stable and primary_external_clean_runs >= 3 and primary_external_main_table_eligible:
        classification = "paper_usable_comparative_path"
    elif bool(prefer_development_shift) and primary_ready:
        classification = "development_priorities_shifted_comparative_path_retained"
    elif switch_required:
        classification = "cli_unstable_api_direct_fallback"
    elif primary_ready:
        classification = "development_priorities_shifted_comparative_path_retained"
    else:
        classification = "comparative_path_retained_provisional"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if primary_slice and paper_matrix and stability and claim_gate else "FAIL",
        "classification": classification,
        "primary_provider_name": primary_provider_name,
        "secondary_provider_name": secondary_provider_name,
        "primary_slice_summary_path": str(Path(primary_slice_summary_path).resolve()) if Path(primary_slice_summary_path).exists() else str(primary_slice_summary_path),
        "paper_matrix_summary_path": str(Path(paper_matrix_summary_path).resolve()) if Path(paper_matrix_summary_path).exists() else str(paper_matrix_summary_path),
        "primary_provider_stability_summary_path": str(Path(primary_provider_stability_summary_path).resolve()) if Path(primary_provider_stability_summary_path).exists() else str(primary_provider_stability_summary_path),
        "claim_gate_summary_path": str(Path(claim_gate_summary_path).resolve()) if Path(claim_gate_summary_path).exists() else str(claim_gate_summary_path),
        "metrics": {
            "primary_slice_status": _norm(primary_slice.get("status")),
            "primary_slice_admitted_count": int(primary_metrics.get("admitted_count") or primary_slice.get("admitted_count") or 0),
            "planner_sensitive_pct": float(primary_metrics.get("planner_sensitive_pct") or primary_slice.get("planner_sensitive_pct") or 0.0),
            "deterministic_only_pct": float(primary_metrics.get("deterministic_only_pct") or primary_slice.get("deterministic_only_pct") or 0.0),
            "gateforge_median_success_rate_pct": float(gateforge.get("median_infra_normalized_success_rate_pct") or 0.0),
            "primary_external_median_success_rate_pct": float(primary_external.get("median_infra_normalized_success_rate_pct") or 0.0),
            "secondary_external_median_success_rate_pct": float(secondary_external.get("median_infra_normalized_success_rate_pct") or 0.0),
            "primary_external_clean_run_count": primary_external_clean_runs,
            "primary_external_main_table_eligible": bool(primary_external_main_table_eligible),
            "secondary_external_clean_run_count": int(secondary_external.get("clean_run_count") or 0),
            "strong_claim_candidate": bool((claim_gate.get("claim_drafts") or {}).get("strong_comparative_claim_candidate")),
            "conservative_claim_candidate": bool((claim_gate.get("claim_drafts") or {}).get("conservative_claim_candidate")),
        },
        "notes": [
            "paper_usable_comparative_path requires a PRIMARY_READY slice plus a stable primary external baseline with at least 3 clean runs.",
            "cli_unstable_api_direct_fallback is triggered only when the primary provider stability gate requests a switch.",
            "development_priorities_shifted_comparative_path_retained means the comparative route is technically preserved, but remaining version budget is better spent on core development than full repeated-run completion.",
            "The secondary external baseline remains supplementary for v0.3.3 and does not block the primary release classification.",
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
                f"- primary_external_clean_run_count: `{payload['metrics']['primary_external_clean_run_count']}`",
                f"- primary_external_main_table_eligible: `{payload['metrics']['primary_external_main_table_eligible']}`",
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
    parser.add_argument("--primary-provider-stability-summary", default="")
    parser.add_argument("--primary-provider-name", default="")
    parser.add_argument("--secondary-provider-name", default="")
    parser.add_argument("--claim-gate-summary", required=True)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--prefer-development-shift", action="store_true")
    args = parser.parse_args()
    payload = build_v0_3_3_closeout(
        primary_slice_summary_path=str(args.primary_slice_summary),
        paper_matrix_summary_path=str(args.paper_matrix_summary),
        primary_provider_stability_summary_path=str(args.primary_provider_stability_summary),
        claim_gate_summary_path=str(args.claim_gate_summary),
        out_dir=str(args.out_dir),
        prefer_development_shift=bool(args.prefer_development_shift),
        primary_provider_name=str(args.primary_provider_name),
        secondary_provider_name=str(args.secondary_provider_name),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))


if __name__ == "__main__":
    main()
