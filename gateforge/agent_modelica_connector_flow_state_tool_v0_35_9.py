from __future__ import annotations

import json
import re
from typing import Any

from .agent_modelica_connector_flow_semantics_tool_v0_34_15 import (
    _connect_rows,
    _declared_connectors,
    _model_rows,
    _omc_state,
)

_TOOL_DEFS: list[dict[str, Any]] = [
    {
        "name": "connector_flow_state_diagnostic",
        "description": (
            "Report connector-flow semantic state: connection sets, flow participants, and where flow equations "
            "are owned. Diagnostic-only; does not generate patches, select candidates, or submit."
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


def _endpoint_root(endpoint: str) -> str:
    return str(endpoint).strip().split(".", 1)[0].split("[", 1)[0]


def _component_path(endpoint: str) -> str:
    return str(endpoint).strip().split(".", 1)[0]


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        if item not in self.parent:
            self.parent[item] = item
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        lroot = self.find(left)
        rroot = self.find(right)
        if lroot != rroot:
            self.parent[rroot] = lroot


def _connection_sets(model_text: str) -> list[dict[str, Any]]:
    connects = _connect_rows(model_text)
    uf = _UnionFind()
    for row in connects:
        uf.union(row["left"], row["right"])
    groups: dict[str, set[str]] = {}
    for row in connects:
        for side in (row["left"], row["right"]):
            groups.setdefault(uf.find(side), set()).add(side)
    result: list[dict[str, Any]] = []
    for idx, members in enumerate(sorted(groups.values(), key=lambda vals: sorted(vals)[0]), start=1):
        ordered = sorted(members)
        result.append(
            {
                "set_id": f"connection_set_{idx}",
                "member_count": len(ordered),
                "members": ordered,
                "component_roots": sorted({_endpoint_root(member) for member in ordered}),
                "has_arrayed_member": any("[" in member for member in ordered),
                "flow_balance_participants": [f"{member}.i" for member in ordered],
            }
        )
    return result


def _flow_owner_rows(model_text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    models = _model_rows(model_text)
    for model_name, model in models.items():
        for equation in model.get("flow_equation_examples", []):
            connector_refs = sorted(set(re.findall(r"\b([A-Za-z_][A-Za-z0-9_\[\]]*)\.i\b", str(equation))))
            rows.append(
                {
                    "model": model_name,
                    "equation": equation,
                    "connector_refs": connector_refs,
                    "constraint_kind": "flow_equation",
                }
            )
    return rows


def _unowned_measurement_components(connection_sets: list[dict[str, Any]], owner_rows: list[dict[str, Any]]) -> list[str]:
    owned = {ref.split("[", 1)[0] for row in owner_rows for ref in row.get("connector_refs", [])}
    suspects: set[str] = set()
    for conn_set in connection_sets:
        for member in conn_set["members"]:
            component = _component_path(str(member))
            root = component.split("[", 1)[0]
            if root.lower().startswith(("probe", "sensor", "monitor")) and root not in owned:
                suspects.add(component)
    return sorted(suspects)


def connector_flow_state_diagnostic(model_text: str, omc_output: str = "") -> str:
    connection_sets = _connection_sets(model_text)
    owner_rows = _flow_owner_rows(model_text)
    unowned_measurement = _unowned_measurement_components(connection_sets, owner_rows)
    omc = _omc_state(omc_output)
    return json.dumps(
        {
            "diagnostic_only": True,
            "patch_generated": False,
            "candidate_selected": False,
            "submitted": False,
            "declared_connectors": _declared_connectors(model_text),
            "connection_sets": connection_sets,
            "flow_owner_rows": owner_rows,
            "unowned_measurement_components": unowned_measurement,
            "omc_state": omc,
            "interpretation": [
                "Connection sets define flow-balance participants; they do not by themselves explain component intent.",
                "A measurement/probe component connected into a flow set may still need an explicit flow contract.",
                "This diagnostic reports semantic state only; the LLM must still design, test, and submit any repair.",
            ],
        },
        sort_keys=True,
    )


def get_connector_flow_state_tool_defs() -> list[dict[str, Any]]:
    return list(_TOOL_DEFS)


def dispatch_connector_flow_state_tool(name: str, arguments: dict[str, Any]) -> str:
    if name != "connector_flow_state_diagnostic":
        return json.dumps({"error": f"unknown_connector_flow_state_tool:{name}"}, sort_keys=True)
    model_text = str(arguments.get("model_text") or "")
    if not model_text.strip():
        return json.dumps({"error": "empty_model_text"}, sort_keys=True)
    return connector_flow_state_diagnostic(model_text, str(arguments.get("omc_output") or ""))
