from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_v0_3_16_preservation_mutation_spec"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_residual_preservation_audit_current" / "summary.json"
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "agent_modelica_v0_3_16_preservation_mutation_spec_current"


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


def build_preservation_mutation_spec(
    *,
    audit_path: str = str(DEFAULT_AUDIT),
    out_dir: str = str(DEFAULT_OUT_DIR),
) -> dict:
    audit = _load_json(audit_path)
    taxonomy = audit.get("preservation_failure_taxonomy") if isinstance(audit.get("preservation_failure_taxonomy"), dict) else {}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now_utc(),
        "status": "PASS",
        "audit_path": str(Path(audit_path).resolve()) if Path(audit_path).exists() else str(audit_path),
        "primary_drift_cause": taxonomy.get("primary_drift_cause"),
        "allowed_runtime_operations": [
            "paired_value_collapse_with_exactly_two_target_parameters",
        ],
        "disallowed_runtime_operations": [
            "multi_value_collapse_with_target_count_greater_than_two",
            "hidden_base_parameter_arity_expansion_relative_to_proven_runtime_seed",
        ],
        "allowed_initialization_operations": [
            "init_equation_sign_flip_with_exactly_one_target_lhs",
        ],
        "disallowed_initialization_operations": [
            "multi_target_init_equation_sign_flip",
            "hidden_base_lhs_arity_expansion_relative_to_proven_initialization_seed",
        ],
        "source_model_eligibility": {
            "runtime": {
                "status": "PROMOTED_SEED_ONLY",
                "rule": "Only use runtime source families that already produced v0.3.13 promoted pairs.",
            },
            "initialization": {
                "status": "PROMOTED_SEED_ONLY",
                "rule": "Only use initialization source families that already produced v0.3.13 promoted tasks.",
            },
        },
        "design_note": "v0.3.16 uses preservation-control candidates first; new harder variants are blocked until the probe path itself is calibrated against preserved historical seeds.",
    }
    out_root = Path(out_dir)
    _write_json(out_root / "summary.json", payload)
    _write_text(
        out_root / "summary.md",
        "\n".join(
            [
                "# v0.3.16 Preservation Mutation Spec",
                "",
                f"- status: `{payload.get('status')}`",
                f"- primary_drift_cause: `{payload.get('primary_drift_cause')}`",
                "",
            ]
        ),
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.3.16 preservation-oriented mutation spec.")
    parser.add_argument("--audit", default=str(DEFAULT_AUDIT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    payload = build_preservation_mutation_spec(audit_path=str(args.audit), out_dir=str(args.out_dir))
    print(json.dumps({"status": payload.get("status"), "primary_drift_cause": payload.get("primary_drift_cause")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
