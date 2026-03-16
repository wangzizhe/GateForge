from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_wave2_realism_manifest_v1 import load_wave2_realism_manifest, validate_wave2_realism_manifest
from .agent_modelica_unknown_library_curated_retrieval_v1 import DEFAULT_ACTIONS


SCHEMA_VERSION = "agent_modelica_wave2_curated_retrieval_v1"


def _write_json(path: str, payload: object) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_wave2_curated_retrieval_rows(manifest_path: str, failure_types: list[str]) -> dict:
    payload = load_wave2_realism_manifest(manifest_path)
    libraries, reasons = validate_wave2_realism_manifest(payload)
    manifest_real_path = str(payload.get("_manifest_path") or "")
    rows: list[dict] = []
    counts_by_library: dict[str, int] = {}
    counts_by_failure_type: dict[str, int] = {}
    for library in libraries:
        library_id = str(library.get("library_id") or "").strip().lower()
        package_name = str(library.get("package_name") or "").strip()
        domain = str(library.get("domain") or "").strip().lower()
        library_hints = [str(x).lower() for x in (library.get("library_hints") or []) if isinstance(x, str)]
        interface_hints = [str(x) for x in (library.get("component_interface_hints") or []) if isinstance(x, str)]
        connector_hints = [str(x) for x in (library.get("connector_semantic_hints") or []) if isinstance(x, str)]
        for model in library.get("allowed_models") or []:
            if not isinstance(model, dict):
                continue
            seen_risk_band = str(model.get("seen_risk_band") or library.get("seen_risk_band") or "").strip().lower()
            source_type = str(model.get("source_type") or library.get("source_type") or "").strip().lower()
            qualified_name = str(model.get("qualified_model_name") or "").strip()
            component_hints = [qualified_name, *interface_hints, *[str(x) for x in (model.get("component_hints") or []) if isinstance(x, str)]]
            combined_connector_hints = [*connector_hints, *[str(x) for x in (model.get("connector_hints") or []) if isinstance(x, str)]]
            context_lines = [
                f"library={library_id}",
                f"package={package_name}",
                f"domain={domain}",
                f"model={qualified_name}",
                f"seen_risk_band={seen_risk_band}",
                f"source_type={source_type}",
                str(model.get("selection_reason") or library.get("selection_reason") or ""),
                str(model.get("exposure_notes") or library.get("exposure_notes") or ""),
            ]
            for failure_type in failure_types:
                rows.append(
                    {
                        "failure_type": failure_type,
                        "model_id": qualified_name,
                        "used_strategy": f"wave2_curated_{library_id}_{failure_type}",
                        "action_trace": DEFAULT_ACTIONS.get(failure_type) or [],
                        "status": "PASS",
                        "library_hints": sorted({*library_hints, library_id}),
                        "component_hints": component_hints,
                        "connector_hints": combined_connector_hints,
                        "domains": [domain] if domain else [],
                        "source_library": library_id,
                        "package_name": package_name,
                        "reason": "wave2_curated_support",
                        "context_text": [line for line in context_lines if line],
                        "manifest_path": manifest_real_path,
                        "seen_risk_band": seen_risk_band,
                        "source_type": source_type,
                    }
                )
                counts_by_library[library_id] = int(counts_by_library.get(library_id, 0)) + 1
                counts_by_failure_type[failure_type] = int(counts_by_failure_type.get(failure_type, 0)) + 1
    return {
        "status": "PASS" if rows and not reasons else "FAIL",
        "reasons": reasons,
        "row_count": len(rows),
        "counts_by_library": counts_by_library,
        "counts_by_failure_type": counts_by_failure_type,
        "rows": rows,
        "manifest_path": manifest_real_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build wave2 curated retrieval rows")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--failure-types", default="overconstrained_system,parameter_binding_error,array_dimension_mismatch")
    parser.add_argument("--history-out", default="artifacts/agent_modelica_wave2_curated_retrieval_v1/history.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_wave2_curated_retrieval_v1/summary.json")
    args = parser.parse_args()
    failure_types = [item.strip().lower() for item in str(args.failure_types or "").split(",") if item.strip()]
    payload = build_wave2_curated_retrieval_rows(str(args.manifest), failure_types)
    _write_json(args.history_out, {"schema_version": SCHEMA_VERSION, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "rows": payload.get("rows")})
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": payload.get("status"),
        "row_count": payload.get("row_count"),
        "counts_by_library": payload.get("counts_by_library"),
        "counts_by_failure_type": payload.get("counts_by_failure_type"),
        "manifest_path": payload.get("manifest_path"),
        "history_out": args.history_out,
        "reasons": payload.get("reasons"),
    }
    _write_json(args.out, summary)
    print(json.dumps({"status": summary.get("status"), "row_count": summary.get("row_count")}))
    if str(summary.get("status")) != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
