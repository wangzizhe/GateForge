from __future__ import annotations

MUTATION_TAXONOMY: dict[str, dict[str, str]] = {
    "T1": {
        "name": "unit_dimension_error",
        "description": "Unit or dimension mismatch, e.g. kg used as g or missing conversion factor",
        "expected_difficulty": "medium",
    },
    "T2": {
        "name": "initial_condition_problem",
        "description": "start value missing, contradictory, or physically unreasonable",
        "expected_difficulty": "medium_high",
    },
    "T3": {
        "name": "equation_count_error",
        "description": "Over- or under-constrained system; one equation too many or too few",
        "expected_difficulty": "high",
    },
    "T4": {
        "name": "physical_sign_direction_error",
        "description": "Physical sign or direction reversed, e.g. heating written as cooling",
        "expected_difficulty": "medium",
    },
    "T5": {
        "name": "parameter_value_physically_wrong",
        "description": "Parameter value in valid range but based on wrong physical assumption",
        "expected_difficulty": "high",
    },
    "T6": {
        "name": "connection_topology_error",
        "description": "Wrong port connection or incorrect flow direction",
        "expected_difficulty": "medium_high",
    },
}

TAXONOMY_VERSION = "v0_19_0"
TAXONOMY_FROZEN = True  # set after distribution alignment gate passed

TAXONOMY_IDS = frozenset(MUTATION_TAXONOMY.keys())

__all__ = [
    "MUTATION_TAXONOMY",
    "TAXONOMY_FROZEN",
    "TAXONOMY_IDS",
    "TAXONOMY_VERSION",
]
