from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .agent_modelica_curated_hard_unseen_manifest_v1 import (
    load_curated_hard_unseen_manifest,
    validate_curated_hard_unseen_manifest,
)
from .agent_modelica_unknown_library_curated_retrieval_v1 import DEFAULT_ACTIONS, DEFAULT_FAILURE_TYPES


SCHEMA_VERSION = "agent_modelica_curated_hard_unseen_curated_retrieval_v1"


def _write_json(path: str, payload: object) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str, payload: dict) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(
            [
                "# GateForge Agent Modelica Curated Hard Unseen Retrieval v1",
                "",
                f"- status: `{payload.get('status')}`",
                f"- row_count: `{payload.get('row_count')}`",
                f"- library_count: `{payload.get('library_count')}`",
                f"- model_count: `{payload.get('model_count')}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _norm(value: object) -> str:
    return str(value or "").strip()


def _append_unique(out: list[str], seen: set[str], value: object) -> None:
    text = _norm(value).lower()
    if text and text not in seen:
        out.append(text)
        seen.add(text)


def build_curated_hard_unseen_retrieval_rows(manifest_path: str, failure_types: list[str]) -> dict:
    payload = load_curated_hard_unseen_manifest(manifest_path)
    libraries, reasons = validate_curated_hard_unseen_manifest(payload)
    manifest_real_path = _norm(payload.get("_manifest_path"))
    rows: list[dict] = []
    counts_by_library: dict[str, int] = {}
    counts_by_seen_risk_band: dict[str, int] = {}
    counts_by_source_type: dict[str, int] = {}
    model_count = 0
    for library in libraries:
        library_id = _norm(library.get("library_id")).lower()
        package_name = _norm(library.get("package_name"))
        domain = _norm(library.get("domain")).lower()
        library_hints = [str(x) for x in (library.get("library_hints") or []) if isinstance(x, str)]
        interface_hints = [str(x) for x in (library.get("component_interface_hints") or []) if isinstance(x, str)]
        connector_hints = [str(x) for x in (library.get("connector_semantic_hints") or []) if isinstance(x, str)]
        support_actions = library.get("retrieval_support_actions_by_failure_type") if isinstance(library.get("retrieval_support_actions_by_failure_type"), dict) else {}
        for model in library.get("allowed_models") or []:
            if not isinstance(model, dict):
                continue
            seen_risk_band = _norm(model.get("seen_risk_band") or library.get("seen_risk_band")).lower()
            if seen_risk_band not in {"less_likely_seen", "hard_unseen"}:
                continue
            source_type = _norm(model.get("source_type") or library.get("source_type")).lower()
            model_count += 1
            qualified_name = _norm(model.get("qualified_model_name"))
            component_hints: list[str] = []
            seen_components: set[str] = set()
            for item in [qualified_name, *interface_hints, *(model.get("component_hints") or [])]:
                _append_unique(component_hints, seen_components, item)
                if "." in _norm(item):
                    _append_unique(component_hints, seen_components, _norm(item).rsplit(".", 1)[-1])
            combined_connector_hints: list[str] = []
            seen_connectors: set[str] = set()
            for item in [*connector_hints, *(model.get("connector_hints") or [])]:
                _append_unique(combined_connector_hints, seen_connectors, item)
            context_lines = [
                f"library={library_id}",
                f"package={package_name}",
                f"domain={domain}",
                f"model={qualified_name}",
                f"seen_risk_band={seen_risk_band}",
                f"source_type={source_type}",
                _norm(model.get("selection_reason") or library.get("selection_reason")),
                _norm(model.get("exposure_notes") or library.get("exposure_notes")),
            ]
            for failure_type in failure_types:
                action_trace = [
                    str(x)
                    for x in (support_actions.get(failure_type) if isinstance(support_actions.get(failure_type), list) else DEFAULT_ACTIONS.get(failure_type) or [])
                    if isinstance(x, str)
                ]
                rows.append(
                    {
                        "failure_type": failure_type,
                        "model_id": qualified_name,
                        "used_strategy": f"curated_hard_unseen_{library_id}_{failure_type}",
                        "action_trace": action_trace,
                        "status": "PASS",
                        "library_hints": sorted({*(x.lower() for x in library_hints), library_id}),
                        "component_hints": component_hints,
                        "connector_hints": combined_connector_hints,
                        "domains": [domain] if domain else [],
                        "source_library": library_id,
                        "package_name": package_name,
                        "reason": "curated_hard_unseen_support",
                        "context_text": [line for line in context_lines if line],
                        "manifest_path": manifest_real_path,
                        "seen_risk_band": seen_risk_band,
                        "source_type": source_type,
                    }
                )
                counts_by_library[library_id] = int(counts_by_library.get(library_id, 0)) + 1
                counts_by_seen_risk_band[seen_risk_band] = int(counts_by_seen_risk_band.get(seen_risk_band, 0)) + 1
                counts_by_source_type[source_type] = int(counts_by_source_type.get(source_type, 0)) + 1
    status = "PASS" if rows and not reasons else "FAIL"
    return {
        "status": status,
        "reasons": reasons,
        "row_count": len(rows),
        "library_count": len(libraries),
        "model_count": model_count,
        "counts_by_library": counts_by_library,
        "counts_by_seen_risk_band": counts_by_seen_risk_band,
        "counts_by_source_type": counts_by_source_type,
        "rows": rows,
        "manifest_path": manifest_real_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build curated retrieval support rows for curated hard-unseen validation")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--failure-types", default="underconstrained_system,connector_mismatch,initialization_infeasible")
    parser.add_argument("--history-out", default="artifacts/agent_modelica_curated_hard_unseen_curated_retrieval_v1/history.json")
    parser.add_argument("--out", default="artifacts/agent_modelica_curated_hard_unseen_curated_retrieval_v1/summary.json")
    parser.add_argument("--report-out", default="")
    args = parser.parse_args()
    failure_types = [item.strip().lower() for item in str(args.failure_types or "").split(",") if item.strip()]
    if not failure_types:
        failure_types = list(DEFAULT_FAILURE_TYPES)
    payload = build_curated_hard_unseen_retrieval_rows(str(args.manifest), failure_types)
    history = {"schema_version": SCHEMA_VERSION, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "rows": payload.get("rows")}
    _write_json(args.history_out, history)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": payload.get("status"),
        "row_count": payload.get("row_count"),
        "library_count": payload.get("library_count"),
        "model_count": payload.get("model_count"),
        "counts_by_library": payload.get("counts_by_library"),
        "counts_by_seen_risk_band": payload.get("counts_by_seen_risk_band"),
        "counts_by_source_type": payload.get("counts_by_source_type"),
        "manifest_path": payload.get("manifest_path"),
        "history_out": args.history_out,
        "reasons": payload.get("reasons"),
    }
    _write_json(args.out, summary)
    _write_markdown(str(args.report_out or _default_md_path(str(args.out))), summary)
    print(json.dumps({"status": summary.get("status"), "row_count": summary.get("row_count")}))
    if str(summary.get("status")) != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
