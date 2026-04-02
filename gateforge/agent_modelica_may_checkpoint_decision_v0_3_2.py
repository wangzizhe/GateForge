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


def _infer_external_provider_names(matrix: dict) -> list[str]:
    rows = matrix.get("grouped_rows") if isinstance(matrix.get("grouped_rows"), list) else []
    names: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _norm(row.get("provider_name")).lower()
        if not name or name == "gateforge" or name in names:
            continue
        names.append(name)
    return names


def build_may_checkpoint_decision(
    *,
    matrix_summary_path: str,
    primary_probe_summary_path: str = "",
    secondary_probe_summary_path: str = "",
    slice_summary_path: str = "",
    out_dir: str = DEFAULT_OUT_DIR,
    min_repeated_runs: int = 3,
    primary_provider_name: str = "",
    secondary_provider_name: str = "",
) -> dict:
    primary_provider_name = _norm(primary_provider_name).lower()
    secondary_provider_name = _norm(secondary_provider_name).lower()
    primary_probe_summary_path = _norm(primary_probe_summary_path)
    secondary_probe_summary_path = _norm(secondary_probe_summary_path)
    matrix = _load_json(matrix_summary_path)
    inferred_names = _infer_external_provider_names(matrix)
    if not primary_provider_name:
        primary_provider_name = inferred_names[0] if inferred_names else ""
    if not secondary_provider_name:
        secondary_provider_name = next((name for name in inferred_names if name != primary_provider_name), "")
    primary_probe = _load_json(primary_probe_summary_path)
    secondary_probe = _load_json(secondary_probe_summary_path) if _norm(secondary_probe_summary_path) else {}
    slice_summary = _load_json(slice_summary_path) if _norm(slice_summary_path) else {}

    gateforge_rows = _find_group_rows(matrix, provider_name="gateforge")
    primary_rows = _find_group_rows(matrix, provider_name=primary_provider_name)
    secondary_rows = _find_group_rows(matrix, provider_name=secondary_provider_name)
    primary_variance = _find_variance_row(matrix, provider_name=primary_provider_name)
    secondary_variance = _find_variance_row(matrix, provider_name=secondary_provider_name)
    slice_status = _norm(slice_summary.get("status"))
    primary_mean_infra = float(primary_variance.get("mean_infra_failure_rate_pct") or 0.0)

    conditions = {
        "shared_oracle_runnable": bool(primary_probe.get("shared_tool_plane_reached")),
        "primary_external_baseline_runnable": bool(primary_probe.get("shared_tool_plane_reached")),
        "track_c_slice_audit_justified": slice_status in {"PASS", "SEED_READY", "NEEDS_MORE_GENERATION", "PRELIMINARY_NEEDS_MORE_EVIDENCE"},
        "paper_scale_primary_slice_ready": slice_status in {"PASS", "PRIMARY_READY"},
        "gateforge_authority_present": bool(gateforge_rows),
        "primary_external_repeated_runs_met": int(primary_variance.get("run_count") or 0) >= int(min_repeated_runs),
        "model_identity_reportable": bool(primary_rows) and all(_norm(row.get("model_id")) for row in primary_rows),
        "infra_failures_separated": bool(primary_rows) and all("infra_failure_rate_pct" in row for row in primary_rows),
        "primary_external_infra_stable": primary_mean_infra < 50.0 if primary_rows else False,
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
    primary_best = max([float(row.get("infra_normalized_success_rate_pct") or 0.0) for row in primary_rows], default=0.0)
    secondary_best = max([float(row.get("infra_normalized_success_rate_pct") or 0.0) for row in secondary_rows], default=0.0)

    comparative_path_retained = classification != "fallback_path_locked"
    strong_claim_candidate = gateforge_best >= primary_best + 5.0 and comparative_path_retained
    conservative_claim_candidate = comparative_path_retained

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if matrix else "FAIL",
        "classification": classification,
        "primary_provider_name": primary_provider_name,
        "secondary_provider_name": secondary_provider_name,
        "matrix_summary_path": str(Path(matrix_summary_path).resolve()) if Path(matrix_summary_path).exists() else str(matrix_summary_path),
        "primary_probe_summary_path": str(Path(primary_probe_summary_path).resolve()) if Path(primary_probe_summary_path).exists() else str(primary_probe_summary_path),
        "secondary_probe_summary_path": str(Path(secondary_probe_summary_path).resolve()) if _norm(secondary_probe_summary_path) and Path(secondary_probe_summary_path).exists() else str(secondary_probe_summary_path),
        "slice_summary_path": str(Path(slice_summary_path).resolve()) if _norm(slice_summary_path) and Path(slice_summary_path).exists() else str(slice_summary_path),
        "conditions": conditions,
        "metrics": {
            "gateforge_best_infra_normalized_success_rate_pct": round(gateforge_best, 2),
            "primary_external_best_infra_normalized_success_rate_pct": round(primary_best, 2),
            "secondary_external_best_infra_normalized_success_rate_pct": round(secondary_best, 2),
            "primary_external_run_count": int(primary_variance.get("run_count") or 0),
            "secondary_external_run_count": int(secondary_variance.get("run_count") or 0),
        },
        "claim_drafts": {
            "strong_comparative_claim_candidate": bool(strong_claim_candidate),
            "conservative_claim_candidate": bool(conservative_claim_candidate),
        },
        "notes": [
            "The primary external baseline is treated as the main external comparator for the May decision.",
            "The secondary external baseline is supplementary for v0.3.2 and does not block the primary comparative-path decision.",
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
                f"- primary_provider_name: `{payload['primary_provider_name']}`",
                f"- shared_oracle_runnable: `{conditions['shared_oracle_runnable']}`",
                f"- primary_external_repeated_runs_met: `{conditions['primary_external_repeated_runs_met']}`",
                f"- gateforge_best_infra_normalized_success_rate_pct: `{payload['metrics']['gateforge_best_infra_normalized_success_rate_pct']}`",
                f"- primary_external_best_infra_normalized_success_rate_pct: `{payload['metrics']['primary_external_best_infra_normalized_success_rate_pct']}`",
                f"- secondary_external_best_infra_normalized_success_rate_pct: `{payload['metrics']['secondary_external_best_infra_normalized_success_rate_pct']}`",
                f"- strong_comparative_claim_candidate: `{payload['claim_drafts']['strong_comparative_claim_candidate']}`",
                f"- conservative_claim_candidate: `{payload['claim_drafts']['conservative_claim_candidate']}`",
            ]
        ),
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the v0.3.2 May checkpoint decision summary.")
    parser.add_argument("--matrix-summary", required=True)
    parser.add_argument("--primary-probe-summary", default="")
    parser.add_argument("--secondary-probe-summary", default="")
    parser.add_argument("--primary-provider-name", default="")
    parser.add_argument("--secondary-provider-name", default="")
    parser.add_argument("--slice-summary", default="")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    parser.add_argument("--min-repeated-runs", type=int, default=3)
    args = parser.parse_args()
    payload = build_may_checkpoint_decision(
        matrix_summary_path=str(args.matrix_summary),
        primary_probe_summary_path=str(args.primary_probe_summary),
        secondary_probe_summary_path=str(args.secondary_probe_summary),
        slice_summary_path=str(args.slice_summary),
        out_dir=str(args.out_dir),
        min_repeated_runs=int(args.min_repeated_runs),
        primary_provider_name=str(args.primary_provider_name),
        secondary_provider_name=str(args.secondary_provider_name),
    )
    print(json.dumps({"status": payload.get("status"), "classification": payload.get("classification")}))
    if payload.get("status") != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
