from __future__ import annotations

import json
import re
from typing import Any

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "structure_coverage_diagnostic",
        "description": (
            "Summarize structural coverage across candidate Modelica models. "
            "Diagnostic-only: it does not generate patches, select candidates, or submit final answers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "candidates": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string"},
                            "model_text": {"type": "string"},
                        },
                        "required": ["model_text"],
                    },
                    "description": "Candidate models that the LLM has already tested or is comparing.",
                },
                "focus": {
                    "type": "string",
                    "description": "Optional focus such as flow ownership, partial base, connector contract, or replaceable binding.",
                },
            },
            "required": ["candidates"],
        },
    }
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def _features(model_text: str) -> dict[str, Any]:
    text = str(model_text or "")
    flow_equations = re.findall(r"\b[\w.]+\s*\.i\s*=", text)
    partial_names = re.findall(r"\bpartial\s+model\s+(\w+)", text)
    replaceable_names = re.findall(r"\breplaceable\s+model\s+(\w+)", text)
    constrainedby_names = re.findall(r"\bconstrainedby\s+(\w+)", text)
    return {
        "connect_count": text.count("connect("),
        "equation_keyword_count": len(re.findall(r"\bequation\b", text)),
        "partial_count": len(partial_names),
        "replaceable_count": len(replaceable_names),
        "constrainedby_count": len(constrainedby_names),
        "extends_count": len(re.findall(r"\bextends\b", text)),
        "flow_equation_count": len(flow_equations),
        "partial_names": sorted(set(partial_names)),
        "replaceable_names": sorted(set(replaceable_names)),
        "constrainedby_names": sorted(set(constrainedby_names)),
        "fingerprint": [
            text.count("connect("),
            len(re.findall(r"\bequation\b", text)),
            len(partial_names),
            len(replaceable_names),
            len(constrainedby_names),
            len(re.findall(r"\bextends\b", text)),
            len(flow_equations),
        ],
    }


def structure_coverage_diagnostic(*, candidates: list[dict[str, Any]] | None = None, focus: str = "") -> str:
    candidate_rows: list[dict[str, Any]] = []
    exact_seen: set[str] = set()
    clusters: dict[str, dict[str, Any]] = {}
    for idx, candidate in enumerate(candidates or [], start=1):
        if not isinstance(candidate, dict):
            continue
        model_text = str(candidate.get("model_text") or "")
        if not model_text.strip():
            continue
        features = _features(model_text)
        fingerprint = json.dumps(features["fingerprint"])
        normalized = _normalize(model_text)
        exact_duplicate = normalized in exact_seen
        exact_seen.add(normalized)
        label = str(candidate.get("label") or f"candidate_{idx}")
        row = {
            "label": label,
            "exact_duplicate": exact_duplicate,
            **features,
        }
        candidate_rows.append(row)
        cluster = clusters.setdefault(
            fingerprint,
            {
                "fingerprint": features["fingerprint"],
                "candidate_labels": [],
                "count": 0,
                "features": features,
            },
        )
        cluster["candidate_labels"].append(label)
        cluster["count"] += 1

    payload = {
        "diagnostic_only": True,
        "patch_generated": False,
        "candidate_selected": False,
        "auto_submit": False,
        "focus": str(focus or ""),
        "candidate_count": len(candidate_rows),
        "exact_unique_candidate_count": len(exact_seen),
        "structure_cluster_count": len(clusters),
        "duplicate_candidate_count": sum(1 for row in candidate_rows if row["exact_duplicate"]),
        "clusters": list(clusters.values()),
        "candidates": candidate_rows,
        "guidance": (
            "Use this coverage report to notice which structural regions have already been tried. "
            "The tool does not say which candidate is correct and does not suggest a patch."
        ),
    }
    return json.dumps(payload, sort_keys=True)


def get_structure_coverage_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_structure_coverage_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "structure_coverage_diagnostic":
        return json.dumps({"error": f"unknown_structure_coverage_tool:{name}"})
    candidates = arguments.get("candidates") if isinstance(arguments.get("candidates"), list) else []
    return structure_coverage_diagnostic(
        candidates=[item for item in candidates if isinstance(item, dict)],
        focus=str(arguments.get("focus") or ""),
    )
