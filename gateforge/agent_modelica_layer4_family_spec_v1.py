from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_layer4_family_spec_v1"
REQUIRED_FAMILY_IDS = {
    "initialization_singularity",
    "structural_singularity",
    "runtime_numerical_instability",
    "hard_multiround_simulate_failure",
}
ALLOWED_VIABILITY = {"approved_v0_3_0", "deferred_v0_3_1", "needs_review"}


def _load_json(path: str | None) -> dict:
    if not path:
        return {}
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


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _family_rows(payload: dict) -> list[dict]:
    rows = payload.get("families") if isinstance(payload.get("families"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def _criterion_present(row: dict) -> bool:
    payload = row.get("validation_criterion") if isinstance(row.get("validation_criterion"), dict) else {}
    for key in (
        "min_observed_layer4_share_pct",
        "min_stage4_stage5_share_pct",
        "max_gateforge_success_rate_pct",
        "min_hard_case_rate_pct",
    ):
        if isinstance(payload.get(key), (int, float)):
            return True
    return False


def build_summary(spec: dict) -> dict:
    reasons: list[str] = []
    families = _family_rows(spec)
    by_id = {str(row.get("family_id") or "").strip(): row for row in families if str(row.get("family_id") or "").strip()}

    missing_ids = sorted(REQUIRED_FAMILY_IDS - set(by_id.keys()))
    unknown_ids = sorted(set(by_id.keys()) - REQUIRED_FAMILY_IDS)
    if missing_ids:
        reasons.append("required_family_missing")
    if unknown_ids:
        reasons.append("unknown_family_present")

    family_summaries: list[dict] = []
    structural_viability = "missing"
    for family_id in sorted(by_id.keys()):
        row = by_id[family_id]
        viability = str(row.get("viability_status") or "").strip()
        enabled_for_v030 = bool(row.get("enabled_for_v0_3_0"))
        expected_layer_hint = str(row.get("expected_layer_hint") or "").strip()
        constraints = row.get("mutation_acceptance_constraints") if isinstance(row.get("mutation_acceptance_constraints"), list) else []
        criterion_ok = _criterion_present(row)
        family_reasons: list[str] = []
        if viability not in ALLOWED_VIABILITY:
            family_reasons.append("viability_status_invalid")
        if expected_layer_hint != "layer_4":
            family_reasons.append("expected_layer_hint_not_layer_4")
        if not constraints:
            family_reasons.append("mutation_acceptance_constraints_missing")
        if not criterion_ok:
            family_reasons.append("validation_criterion_missing")
        if family_id == "structural_singularity":
            structural_viability = viability or "missing"
        family_summaries.append(
            {
                "family_id": family_id,
                "display_name": str(row.get("display_name") or family_id),
                "enabled_for_v0_3_0": enabled_for_v030,
                "viability_status": viability,
                "reason_count": len(family_reasons),
                "reasons": family_reasons,
            }
        )

    if structural_viability not in {"approved_v0_3_0", "deferred_v0_3_1"}:
        reasons.append("structural_singularity_viability_not_decided")

    status = "PASS" if not reasons and all(not row["reasons"] for row in family_summaries) else "FAIL"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "reasons": reasons,
        "required_family_ids": sorted(REQUIRED_FAMILY_IDS),
        "missing_family_ids": missing_ids,
        "unknown_family_ids": unknown_ids,
        "structural_singularity_viability": structural_viability,
        "families": family_summaries,
    }


def _write_markdown(path: str | Path, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Agent Modelica Layer 4 Family Spec v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- reasons: `{','.join(payload.get('reasons') or []) or 'none'}`",
        f"- structural_singularity_viability: `{payload.get('structural_singularity_viability')}`",
        "",
    ]
    for row in payload.get("families") or []:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- {row.get('family_id')}: enabled_for_v0_3_0=`{row.get('enabled_for_v0_3_0')}`, viability_status=`{row.get('viability_status')}`, reasons=`{','.join(row.get('reasons') or []) or 'none'}`"
        )
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a machine-readable Layer 4 family spec for Agent-Modelica")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()

    spec = _load_json(str(args.spec))
    summary = build_summary(spec)
    _write_json(str(args.out), summary)
    _write_markdown(str(args.report_out or _default_md_path(str(args.out))), summary)
    print(json.dumps({"status": summary.get("status"), "family_count": len(summary.get("families") or [])}))
    if summary.get("status") == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
