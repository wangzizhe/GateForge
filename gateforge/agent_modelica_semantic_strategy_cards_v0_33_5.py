from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "semantic_strategy_cards_v0_33_5"

SEMANTIC_STRATEGY_CARDS: list[dict[str, Any]] = [
    {
        "card_id": "arrayed_connector_flow_ownership",
        "title": "Arrayed connector flow ownership",
        "applies_when": [
            "The model uses arrayed custom connectors with potential and flow fields.",
            "A probe, adapter, or measurement bank is connected to multiple branch nodes.",
            "OMC reports an underdetermined or structurally singular connector system.",
        ],
        "semantic_boundary": (
            "In Modelica, connection sets contribute potential equality equations and one flow "
            "balance equation per connection set. A reusable measurement interface must account "
            "for its flow variables without silently creating extra physical branches."
        ),
        "search_directions": [
            "Reason per connection set rather than per textual connect statement.",
            "Decide which component owns each flow balance or zero-flow measurement assumption.",
            "Preserve stated measurements and topology before simplifying connector structure.",
            "If a custom connector contract keeps failing, consider whether a standard library connector semantics match the task better.",
        ],
        "avoid": [
            "Do not add arbitrary direct flow equations just to balance equation counts.",
            "Do not remove required readings or collapse the adapter/probe abstraction unless the task permits it.",
            "Do not treat potential readings alone as a complete connector contract when flow variables remain unowned.",
        ],
    },
    {
        "card_id": "standard_library_semantic_migration",
        "title": "Standard-library semantic migration",
        "applies_when": [
            "A local custom connector is trying to emulate a common electrical or physical connector.",
            "The repair keeps looping around custom flow equations and structural singularity.",
            "The task constraints require preserving behavior but do not require preserving the local connector implementation.",
        ],
        "semantic_boundary": (
            "A standard Modelica library connector/component set can encode domain semantics that a "
            "small custom connector contract fails to express. Migration is a candidate strategy only "
            "when it preserves the task's named model, topology, and required observations."
        ),
        "search_directions": [
            "Map the custom potential/flow intent to an equivalent standard connector semantics.",
            "Use library source, ground/reference, passive branch, and sensor components as semantic building blocks when appropriate.",
            "Validate the migrated candidate with OMC rather than assuming the library substitution is correct.",
            "Keep the migration minimal and explain which task constraints remain preserved.",
        ],
        "avoid": [
            "Do not use library migration as a universal default.",
            "Do not rename the top-level model.",
            "Do not discard required output variables or required measurement topology.",
            "Do not submit without running OMC evidence on the exact candidate.",
        ],
    },
]


def validate_strategy_card(card: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["card_id", "title", "applies_when", "semantic_boundary", "search_directions", "avoid"]
    for key in required:
        if key not in card:
            errors.append(f"missing:{key}")
    for key in ["applies_when", "search_directions", "avoid"]:
        if not isinstance(card.get(key), list) or not card.get(key):
            errors.append(f"empty_list:{key}")
    forbidden_terms = [
        "replace this line",
        "exact patch",
        "submit this",
        "final model",
        "case_id",
        "sem_",
    ]
    rendered = json.dumps(card, sort_keys=True).lower()
    for term in forbidden_terms:
        if term in rendered:
            errors.append(f"forbidden_term:{term}")
    return errors


def render_strategy_cards(cards: list[dict[str, Any]] | None = None) -> str:
    active_cards = cards or SEMANTIC_STRATEGY_CARDS
    lines: list[str] = [
        "# Modelica Semantic Strategy Cards",
        "",
        "These cards are transparent external context for the LLM. They do not contain a patch, "
        "do not select a candidate, and do not submit a solution. Use them only to widen semantic search.",
        "",
    ]
    for card in active_cards:
        lines.extend(
            [
                f"## {card['title']}",
                "",
                f"- card_id: `{card['card_id']}`",
                f"- semantic_boundary: {card['semantic_boundary']}",
                "",
                "Applies when:",
            ]
        )
        lines.extend(f"- {item}" for item in card["applies_when"])
        lines.append("")
        lines.append("Search directions:")
        lines.extend(f"- {item}" for item in card["search_directions"])
        lines.append("")
        lines.append("Avoid:")
        lines.extend(f"- {item}" for item in card["avoid"])
        lines.append("")
    lines.extend(
        [
            "## Discipline",
            "",
            "- The wrapper must not generate patches.",
            "- The wrapper must not choose a candidate.",
            "- The wrapper must not auto-submit.",
            "- The LLM must still write candidates, call OMC tools, and call submit_final itself.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_semantic_strategy_cards(
    *,
    out_dir: Path = DEFAULT_OUT_DIR,
    cards: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    active_cards = cards or SEMANTIC_STRATEGY_CARDS
    card_errors = {str(card.get("card_id") or index): validate_strategy_card(card) for index, card in enumerate(active_cards)}
    invalid_cards = {card_id: errors for card_id, errors in card_errors.items() if errors}
    context_text = render_strategy_cards(active_cards)
    summary = {
        "version": "v0.33.5",
        "status": "PASS" if active_cards and not invalid_cards else "REVIEW",
        "analysis_scope": "semantic_strategy_cards",
        "card_count": len(active_cards),
        "invalid_card_count": len(invalid_cards),
        "invalid_cards": invalid_cards,
        "context_chars": len(context_text),
        "context_path": str(out_dir / "semantic_strategy_cards_context.md"),
        "decision": "semantic_strategy_cards_ready_for_live_probe" if active_cards and not invalid_cards else "semantic_strategy_cards_need_review",
        "discipline": {
            "patch_generated": False,
            "candidate_selected": False,
            "auto_submit_added": False,
            "case_specific_routing_added": False,
        },
    }
    write_outputs(out_dir=out_dir, summary=summary, context_text=context_text)
    return summary


def write_outputs(*, out_dir: Path, summary: dict[str, Any], context_text: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "semantic_strategy_cards_context.md").write_text(context_text, encoding="utf-8")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
