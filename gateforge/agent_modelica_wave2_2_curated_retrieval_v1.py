from __future__ import annotations

import argparse
import json
from pathlib import Path

from .agent_modelica_wave2_2_coupled_hard_manifest_v1 import (
    load_wave2_2_coupled_hard_manifest,
    validate_wave2_2_coupled_hard_manifest,
)


SCHEMA_VERSION = "agent_modelica_wave2_2_curated_retrieval_v1"


def _norm(value: object) -> str:
    return str(value or "").strip()


def build_wave2_2_curated_retrieval_rows(manifest_path: str, failure_types: list[str]) -> dict:
    payload = load_wave2_2_coupled_hard_manifest(manifest_path)
    libraries, reasons = validate_wave2_2_coupled_hard_manifest(payload)
    rows: list[dict] = []
    for library in libraries:
        library_id = _norm(library.get("library_id")).lower()
        package_name = _norm(library.get("package_name"))
        domain = _norm(library.get("domain")).lower()
        interface_hints = [str(x) for x in (library.get("component_interface_hints") or []) if str(x).strip()]
        semantic_hints = [str(x) for x in (library.get("connector_semantic_hints") or []) if str(x).strip()]
        for model in library.get("allowed_models") or []:
            if not isinstance(model, dict):
                continue
            model_id = _norm(model.get("model_id")).lower()
            qualified_name = _norm(model.get("qualified_model_name"))
            component_hints = [str(x) for x in (model.get("component_hints") or []) if str(x).strip()]
            connector_hints = [str(x) for x in (model.get("connector_hints") or []) if str(x).strip()]
            for failure_type in failure_types:
                rows.append(
                    {
                        "library_id": library_id,
                        "model_id": model_id,
                        "task_id_hint": f"wave2_2_{library_id}_{model_id}_{failure_type}",
                        "failure_type": failure_type,
                        "source_library": package_name,
                        "used_strategy": f"wave2_2_curated_{library_id}_{failure_type}",
                        "domain": domain,
                        "library_hints": [library_id, package_name],
                        "component_hints": component_hints + interface_hints,
                        "connector_hints": connector_hints + semantic_hints,
                        "model_hint": qualified_name,
                        "reason": "wave2_2_curated_support",
                    }
                )
    return {
        "schema_version": SCHEMA_VERSION,
        "manifest_path": str(Path(manifest_path).resolve()),
        "rows": rows,
        "summary": {"status": "PASS" if rows and not reasons else "FAIL", "row_count": len(rows), "reasons": reasons},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build wave2.2 coupled-hard curated retrieval support")
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--failure-types",
        default="cross_component_parameter_coupling_error,control_loop_sign_semantic_drift,mode_switch_guard_logic_error",
    )
    parser.add_argument("--history-out", default="artifacts/agent_modelica_wave2_2_curated_retrieval_v1/history.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_wave2_2_curated_retrieval_v1/summary.json")
    args = parser.parse_args()
    failure_types = [item.strip().lower() for item in str(args.failure_types or "").split(",") if item.strip()]
    payload = build_wave2_2_curated_retrieval_rows(str(args.manifest), failure_types)
    history_out = Path(args.history_out)
    history_out.parent.mkdir(parents=True, exist_ok=True)
    history_out.write_text(json.dumps({"schema_version": SCHEMA_VERSION, "rows": payload["rows"]}, indent=2), encoding="utf-8")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload["summary"], indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"]))
    if payload["summary"]["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
