from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = "agent_modelica_cross_domain_validation_spec_v1"
DEFAULT_TRACK_MANIFEST = "data/agent_modelica_cross_domain_track_manifest_v1.json"
DEFAULT_EXPECTATION_TEMPLATE = "data/agent_modelica_cross_domain_validation_spec_template_v1.json"


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


def _default_md_path(out_json: str | Path) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _write_markdown(path: str | Path, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Agent Modelica Cross-Domain Validation Spec Builder v1",
        "",
        f"- status: `{payload.get('status')}`",
        f"- track_count: `{payload.get('track_count')}`",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")


def build_spec(
    *,
    matrix_summary_paths: list[str],
    track_manifest_path: str = DEFAULT_TRACK_MANIFEST,
    expectation_template_path: str = DEFAULT_EXPECTATION_TEMPLATE,
) -> dict:
    track_manifest = _load_json(track_manifest_path)
    template = _load_json(expectation_template_path)
    track_meta = {
        str(row.get("track_id") or ""): row
        for row in (track_manifest.get("tracks") if isinstance(track_manifest.get("tracks"), list) else [])
        if isinstance(row, dict) and str(row.get("track_id") or "").strip()
    }

    tracks: list[dict] = []
    missing: list[str] = []
    for path in matrix_summary_paths:
        summary = _load_json(path)
        if not summary:
            missing.append(str(path))
            continue
        track_id = str(summary.get("track_id") or "").strip()
        library = str(summary.get("library") or "") or str((track_meta.get(track_id) or {}).get("library") or "")
        configs: dict[str, dict] = {}
        for row in summary.get("configs") or []:
            if not isinstance(row, dict):
                continue
            label = str(row.get("config_label") or "").strip()
            if not label:
                continue
            configs[label] = {
                "comparison_summary": str(row.get("comparison_summary") or ""),
                "gateforge_results": str(row.get("gateforge_results") or ""),
            }
        tracks.append(
            {
                "track_id": track_id,
                "library": library,
                "configs": configs,
            }
        )

    spec = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "experiment_expectations": (
            template.get("experiment_expectations")
            if isinstance(template.get("experiment_expectations"), dict)
            else {}
        ),
        "tracks": tracks,
        "_builder_status": "PASS" if not missing else "NEEDS_REVIEW",
        "_missing_matrix_summaries": missing,
        "_sources": {
            "track_manifest_path": str(track_manifest_path),
            "expectation_template_path": str(expectation_template_path),
            "matrix_summary_paths": matrix_summary_paths,
        },
    }
    return spec


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a cross-domain validation spec from matrix summary artifacts")
    parser.add_argument("--matrix-summary", action="append", default=[])
    parser.add_argument("--track-manifest", default=DEFAULT_TRACK_MANIFEST)
    parser.add_argument("--expectation-template", default=DEFAULT_EXPECTATION_TEMPLATE)
    parser.add_argument("--out", default="artifacts/agent_modelica_cross_domain_validation_v1/spec.json")
    args = parser.parse_args()

    spec = build_spec(
        matrix_summary_paths=[str(x) for x in (args.matrix_summary or []) if str(x).strip()],
        track_manifest_path=args.track_manifest,
        expectation_template_path=args.expectation_template,
    )
    _write_json(args.out, spec)
    summary = {
        "status": str(spec.get("_builder_status") or "PASS"),
        "track_count": len(spec.get("tracks") or []),
    }
    _write_json(_default_md_path(args.out), summary)
    print(json.dumps(summary))
    if summary["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
