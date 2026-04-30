from __future__ import annotations

import json
import re
from typing import Any

from .agent_modelica_connector_flow_state_tool_v0_35_9 import _UnionFind

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "arrayed_shared_bus_diagnostic",
        "description": (
            "Report arrayed shared-bus connector-flow structure: large connection sets, arrayed endpoint groups, "
            "and probe participation. Diagnostic-only; does not generate patches, select candidates, or submit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_text": {"type": "string", "description": "Modelica model source code."},
                "omc_output": {"type": "string", "description": "Optional recent OMC output."},
            },
            "required": ["model_text"],
        },
    }
]


def _array_root(endpoint: str) -> str:
    return str(endpoint).split("[", 1)[0]


def _arrayed_roots(members: list[str]) -> list[dict[str, Any]]:
    groups: dict[str, set[str]] = {}
    for member in members:
        if "[" not in member:
            continue
        groups.setdefault(_array_root(member), set()).add(member)
    return [
        {
            "root": root,
            "endpoint_count": len(endpoints),
            "endpoints": sorted(endpoints),
        }
        for root, endpoints in sorted(groups.items())
    ]


def _connect_pairs(text: str) -> list[tuple[str, str]]:
    return [
        (match.group(1).strip(), match.group(2).strip())
        for match in re.finditer(r"connect\s*\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)\s*;", text, re.DOTALL)
    ]


def _expanded_connect_pairs(model_text: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    loop_pattern = re.compile(
        r"for\s+([A-Za-z_][A-Za-z0-9_]*)\s+in\s+(\d+)\s*:\s*(\d+)\s+loop(?P<body>.*?)end\s+for\s*;",
        re.DOTALL,
    )
    loop_spans: list[tuple[int, int]] = []
    for loop in loop_pattern.finditer(model_text):
        var = loop.group(1)
        start = int(loop.group(2))
        stop = int(loop.group(3))
        body = loop.group("body")
        loop_spans.append(loop.span())
        for idx in range(start, stop + 1):
            expanded_body = re.sub(rf"\[\s*{re.escape(var)}\s*\]", f"[{idx}]", body)
            pairs.extend(_connect_pairs(expanded_body))
    remaining: list[str] = []
    cursor = 0
    for start, stop in loop_spans:
        remaining.append(model_text[cursor:start])
        cursor = stop
    remaining.append(model_text[cursor:])
    pairs.extend(_connect_pairs("".join(remaining)))
    return pairs


def _expanded_connection_sets(model_text: str) -> list[dict[str, Any]]:
    pairs = _expanded_connect_pairs(model_text)
    uf = _UnionFind()
    for left, right in pairs:
        uf.union(left, right)
    groups: dict[str, set[str]] = {}
    for left, right in pairs:
        for side in (left, right):
            groups.setdefault(uf.find(side), set()).add(side)
    result: list[dict[str, Any]] = []
    for idx, members in enumerate(sorted(groups.values(), key=lambda vals: sorted(vals)[0]), start=1):
        ordered = sorted(members)
        result.append({"set_id": f"expanded_connection_set_{idx}", "members": ordered, "member_count": len(ordered)})
    return result


def arrayed_shared_bus_diagnostic(model_text: str, omc_output: str = "") -> str:
    connection_sets = _expanded_connection_sets(model_text)
    shared_bus_sets: list[dict[str, Any]] = []
    for conn_set in connection_sets:
        members = [str(member) for member in conn_set.get("members", [])]
        arrayed = _arrayed_roots(members)
        probe_roots = [row for row in arrayed if row["root"].lower().startswith(("probe", "sensor", "monitor"))]
        if len(members) >= 5 and arrayed:
            shared_bus_sets.append(
                {
                    "set_id": conn_set.get("set_id"),
                    "member_count": len(members),
                    "arrayed_roots": arrayed,
                    "probe_array_roots": probe_roots,
                    "has_probe_array": bool(probe_roots),
                }
            )
    return json.dumps(
        {
            "diagnostic_only": True,
            "patch_generated": False,
            "candidate_selected": False,
            "submitted": False,
            "shared_bus_set_count": len(shared_bus_sets),
            "shared_bus_sets": shared_bus_sets,
            "omc_output_present": bool(str(omc_output or "").strip()),
            "interpretation": [
                "A large connection set is one shared flow-balance context, not separate local branches.",
                "Arrayed probe endpoints inside the same shared bus may require reasoning about the component contract.",
                "This diagnostic reports structure only; the LLM must still design, test, and submit any repair.",
            ],
        },
        sort_keys=True,
    )


def get_arrayed_shared_bus_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_arrayed_shared_bus_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "arrayed_shared_bus_diagnostic":
        return json.dumps({"error": f"unknown_arrayed_shared_bus_tool:{name}"}, sort_keys=True)
    model_text = str(arguments.get("model_text") or "")
    if not model_text.strip():
        return json.dumps({"error": "empty_model_text"}, sort_keys=True)
    return arrayed_shared_bus_diagnostic(model_text, str(arguments.get("omc_output") or ""))
