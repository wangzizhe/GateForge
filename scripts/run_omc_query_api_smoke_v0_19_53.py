"""Smoke test the v0.19.53 Modelica query API on existing model artifacts.

This script is intentionally read-only with respect to model files. It does
not call an LLM, does not run OMC, and does not produce repair decisions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_omc_query_api_v1 import (  # noqa: E402
    extract_real_declarations,
    structural_signal_summary,
)


DEFAULT_GLOBS = [
    "assets_private/standalone_explicit_equation_source_models_v0_19_34/*.mo",
    "artifacts/triple_underdetermined_experiment_v0_19_45/*.mo",
    "artifacts/triple_underdetermined_experiment_v0_19_45_pp_pv_pv/*.mo",
]


def _rel(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT))


def discover_model_paths(patterns: list[str], limit: int | None = None) -> list[Path]:
    """Return a stable list of model paths matching repository-relative globs."""
    paths: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if path.suffix != ".mo":
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(path)
    if limit is not None:
        return paths[:limit]
    return paths


def summarize_model(path: Path) -> dict[str, Any]:
    """Summarize one Modelica file with the v0.19.53 query API."""
    text = path.read_text(encoding="utf-8")
    summary = structural_signal_summary(text)
    declarations = extract_real_declarations(text)
    declared_phantom_names = sorted(
        decl["name"] for decl in declarations if "_phantom" in decl["name"]
    )
    unused_names = {row["name"] for row in summary["declared_but_unused"]}
    no_definition_names = {
        row["name"] for row in summary["variables_with_no_defining_equation"]
    }
    return {
        "path": _rel(path),
        "ok": True,
        "declaration_count": summary["declaration_count"],
        "equation_count": summary["equation_count"],
        "connect_count": summary["connect_count"],
        "variables_with_no_defining_equation_count": len(
            summary["variables_with_no_defining_equation"]
        ),
        "declared_but_unused_count": len(summary["declared_but_unused"]),
        "unbound_parameter_count": len(summary["unbound_parameters"]),
        "used_but_undeclared_count": len(summary["used_but_undeclared"]),
        "declared_phantom_names": declared_phantom_names,
        "unused_phantom_names": [
            name for name in declared_phantom_names if name in unused_names
        ],
        "phantom_without_defining_equation_names": [
            name for name in declared_phantom_names if name in no_definition_names
        ],
        "variables_with_no_defining_equation": [
            row["name"] for row in summary["variables_with_no_defining_equation"]
        ],
        "declared_but_unused": [
            row["name"] for row in summary["declared_but_unused"]
        ],
        "unbound_parameters": [
            row["name"] for row in summary["unbound_parameters"]
        ],
        "used_but_undeclared": [
            row["name"] for row in summary["used_but_undeclared"]
        ],
    }


def build_smoke_summary(paths: list[Path]) -> dict[str, Any]:
    """Run query summaries over model paths and aggregate smoke-level stats."""
    rows: list[dict[str, Any]] = []
    for path in paths:
        try:
            rows.append(summarize_model(path))
        except Exception as exc:  # pragma: no cover - defensive smoke logging
            rows.append(
                {
                    "path": _rel(path),
                    "ok": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )

    ok_rows = [row for row in rows if row.get("ok")]
    phantom_rows = [
        row for row in ok_rows
        if row.get("declared_phantom_names")
    ]
    unused_phantom_rows = [
        row for row in ok_rows
        if row.get("unused_phantom_names")
    ]
    phantom_without_definition_rows = [
        row for row in ok_rows
        if row.get("phantom_without_defining_equation_names")
    ]
    return {
        "version": "v0.19.53",
        "model_count": len(rows),
        "ok_count": len(ok_rows),
        "crash_count": len(rows) - len(ok_rows),
        "aggregate": {
            "declaration_count": sum(row.get("declaration_count", 0) for row in ok_rows),
            "equation_count": sum(row.get("equation_count", 0) for row in ok_rows),
            "connect_count": sum(row.get("connect_count", 0) for row in ok_rows),
            "declared_phantom_model_count": len(phantom_rows),
            "unused_phantom_model_count": len(unused_phantom_rows),
            "phantom_without_defining_equation_model_count": len(
                phantom_without_definition_rows
            ),
            "used_but_undeclared_model_count": sum(
                1 for row in ok_rows if row.get("used_but_undeclared_count", 0) > 0
            ),
        },
        "api_ready_for_tool_injection": [
            "extract_real_declarations",
            "extract_equation_statements",
            "who_defines",
            "who_uses",
            "declared_but_unused",
            "structural_signal_summary",
        ],
        "known_limitations": [
            "text parser only; inherited declarations and equations are not flattened",
            "connect statements are recorded but not expanded into implicit equations",
            "arrays, when, if, for, and algorithm sections may be partial",
            "Modelica component declarations outside Real-like declarations are not enumerated",
        ],
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="artifacts/omc_query_api_v0_19_53/smoke_summary.json",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    paths = discover_model_paths(DEFAULT_GLOBS, limit=args.limit)
    summary = build_smoke_summary(paths)
    output_path = REPO_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    print(
        f"v0.19.53 query API smoke: "
        f"{summary['ok_count']}/{summary['model_count']} models parsed, "
        f"crashes={summary['crash_count']}, "
        f"phantom_models={summary['aggregate']['declared_phantom_model_count']}"
    )
    print(f"Wrote {output_path}")
    return 0 if summary["crash_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
