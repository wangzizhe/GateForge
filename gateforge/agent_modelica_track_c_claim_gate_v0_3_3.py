from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_track_c_claim_gate_v0_3_3"
DEFAULT_OUT_DIR = "artifacts/agent_modelica_track_c_claim_gate_v0_3_3"


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


def _provider_row(payload: dict, provider_name: str) -> dict:
    rows = payload.get("provider_rows") if isinstance(payload.get("provider_rows"), list) else []
    for row in rows:
        if isinstance(row, dict) and _norm(row.get("provider_name")) == provider_name:
            return row
    return {}


def _infer_primary_external_provider_name(payload: dict) -> str:
    rows = payload.get("provider_rows") if isinstance(payload.get("provider_rows"), list) else []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _norm(row.get("provider_name")).lower()
        if name and name != "gateforge":
            return name
    return ""


def build_claim_gate(
    *,
    paper_matrix_summary_path: str,
    primary_provider_stability_summary_path: str = "",
    primary_slice_summary_path: str = "",
    gateforge_attribution_missing_rate_pct: float = 0.0,
    gateforge_terminal_path_coverage_pct: float = 0.0,
    out_dir: str = DEFAULT_OUT_DIR,
    primary_provider_name: str = "",
) -> dict:
    primary_provider_name = _norm(primary_provider_name).lower()
    primary_provider_stability_summary_path = _norm(primary_provider_stability_summary_path)
    matrix = _load_json(paper_matrix_summary_path)
    if not primary_provider_name:
        primary_provider_name = _infer_primary_external_provider_name(matrix)
    stability = _load_json(primary_provider_stability_summary_path)
    primary_slice = _load_json(primary_slice_summary_path) if _norm(primary_slice_summary_path) else {}
    gateforge = _provider_row(matrix, "gateforge")
    primary_external = _provider_row(matrix, primary_provider_name)

    gateforge_success = float(gateforge.get("median_infra_normalized_success_rate_pct") or 0.0)
    primary_external_success = float(primary_external.get("median_infra_normalized_success_rate_pct") or 0.0)
    success_gap_pp = round(gateforge_success - primary_external_success, 2)
    wall_clock_advantage = False
    tool_call_advantage = False
    if float(primary_external.get("median_avg_wall_clock_sec") or 0.0) > 0:
        wall_clock_advantage = gateforge.get("median_avg_wall_clock_sec", 0.0) <= float(primary_external.get("median_avg_wall_clock_sec") or 0.0) * 0.8
    if float(primary_external.get("median_avg_omc_tool_call_count") or 0.0) > 0:
        tool_call_advantage = gateforge.get("median_avg_omc_tool_call_count", 0.0) <= float(primary_external.get("median_avg_omc_tool_call_count") or 0.0) * 0.8

    external_infra_gap = round(float(primary_external.get("infra_failure_rate_pct") or 0.0) - float(gateforge.get("infra_failure_rate_pct") or 0.0), 2)
    unresolved_session_gap = round(float(primary_external.get("auth_session_failure_rate_pct") or 0.0) - float(gateforge.get("auth_session_failure_rate_pct") or 0.0), 2)
    failure_quality_advantage = (
        float(gateforge_attribution_missing_rate_pct) < 10.0
        and (
            external_infra_gap >= 15.0
            or float(gateforge_terminal_path_coverage_pct) >= 80.0
            or unresolved_session_gap >= 15.0
        )
    )

    strong_claim_candidate = (
        success_gap_pp >= 5.0
        and int(primary_external.get("clean_run_count") or 0) >= 3
        and float(primary_external.get("infra_failure_rate_pct") or 0.0) < 10.0
    )
    conservative_claim_candidate = (
        (
            abs(success_gap_pp) < 5.0
            and (wall_clock_advantage or tool_call_advantage)
        )
        or failure_quality_advantage
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS" if matrix and stability else "FAIL",
        "paper_matrix_summary_path": str(Path(paper_matrix_summary_path).resolve()) if Path(paper_matrix_summary_path).exists() else str(paper_matrix_summary_path),
        "primary_provider_name": primary_provider_name,
        "primary_provider_stability_summary_path": str(Path(primary_provider_stability_summary_path).resolve()) if Path(primary_provider_stability_summary_path).exists() else str(primary_provider_stability_summary_path),
        "primary_slice_summary_path": str(Path(primary_slice_summary_path).resolve()) if _norm(primary_slice_summary_path) and Path(primary_slice_summary_path).exists() else str(primary_slice_summary_path),
        "primary_slice_status": _norm(primary_slice.get("status")),
        "metrics": {
            "gateforge_median_infra_normalized_success_rate_pct": gateforge_success,
            "primary_external_median_infra_normalized_success_rate_pct": primary_external_success,
            "success_gap_pp": success_gap_pp,
            "gateforge_median_avg_wall_clock_sec": float(gateforge.get("median_avg_wall_clock_sec") or 0.0),
            "primary_external_median_avg_wall_clock_sec": float(primary_external.get("median_avg_wall_clock_sec") or 0.0),
            "gateforge_median_avg_omc_tool_call_count": float(gateforge.get("median_avg_omc_tool_call_count") or 0.0),
            "primary_external_median_avg_omc_tool_call_count": float(primary_external.get("median_avg_omc_tool_call_count") or 0.0),
            "external_infra_gap_pp": external_infra_gap,
            "unresolved_session_gap_pp": unresolved_session_gap,
            "gateforge_attribution_missing_rate_pct": float(gateforge_attribution_missing_rate_pct),
            "gateforge_terminal_path_coverage_pct": float(gateforge_terminal_path_coverage_pct),
        },
        "claim_drafts": {
            "strong_comparative_claim_candidate": bool(strong_claim_candidate),
            "conservative_claim_candidate": bool(conservative_claim_candidate),
            "failure_quality_advantage": bool(failure_quality_advantage),
            "wall_clock_advantage": bool(wall_clock_advantage),
            "tool_call_advantage": bool(tool_call_advantage),
        },
        "notes": [
            "Strong claim uses median infra-normalized success rate across clean repeated runs.",
            "Conservative claim allows near-tied success if efficiency or failure-quality evidence is stronger for GateForge.",
        ],
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# Track C Claim Gate v0.3.3",
                "",
                f"- strong_comparative_claim_candidate: `{payload['claim_drafts']['strong_comparative_claim_candidate']}`",
                f"- conservative_claim_candidate: `{payload['claim_drafts']['conservative_claim_candidate']}`",
                f"- success_gap_pp: `{payload['metrics']['success_gap_pp']}`",
                f"- failure_quality_advantage: `{payload['claim_drafts']['failure_quality_advantage']}`",
                "",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.3 Track C claim gate summary.")
    parser.add_argument("--paper-matrix-summary", required=True)
    parser.add_argument("--primary-provider-stability-summary", default="")
    parser.add_argument("--primary-provider-name", default="")
    parser.add_argument("--primary-slice-summary", default="")
    parser.add_argument("--gateforge-attribution-missing-rate-pct", type=float, default=0.0)
    parser.add_argument("--gateforge-terminal-path-coverage-pct", type=float, default=0.0)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    payload = build_claim_gate(
        paper_matrix_summary_path=str(args.paper_matrix_summary),
        primary_provider_stability_summary_path=str(args.primary_provider_stability_summary),
        primary_slice_summary_path=str(args.primary_slice_summary),
        gateforge_attribution_missing_rate_pct=float(args.gateforge_attribution_missing_rate_pct),
        gateforge_terminal_path_coverage_pct=float(args.gateforge_terminal_path_coverage_pct),
        out_dir=str(args.out_dir),
        primary_provider_name=str(args.primary_provider_name),
    )
    print(json.dumps({"status": payload.get("status"), "strong": payload.get("claim_drafts", {}).get("strong_comparative_claim_candidate")}))


if __name__ == "__main__":
    main()
