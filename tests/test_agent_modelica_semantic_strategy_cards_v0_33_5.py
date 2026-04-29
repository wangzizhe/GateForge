from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_semantic_strategy_cards_v0_33_5 import (
    SEMANTIC_STRATEGY_CARDS,
    build_semantic_strategy_cards,
    render_strategy_cards,
    validate_strategy_card,
)


class SemanticStrategyCardsV0335Tests(unittest.TestCase):
    def test_default_cards_are_valid_and_not_case_specific(self) -> None:
        for card in SEMANTIC_STRATEGY_CARDS:
            self.assertEqual(validate_strategy_card(card), [])

    def test_rendered_context_declares_wrapper_boundaries(self) -> None:
        rendered = render_strategy_cards()
        self.assertIn("The wrapper must not generate patches.", rendered)
        self.assertIn("The LLM must still write candidates", rendered)
        self.assertNotIn("sem_19", rendered)

    def test_build_writes_context_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = build_semantic_strategy_cards(out_dir=Path(tmp))
            self.assertEqual(summary["status"], "PASS")
            self.assertFalse(summary["discipline"]["patch_generated"])
            self.assertTrue((Path(tmp) / "semantic_strategy_cards_context.md").exists())

    def test_rejects_case_specific_card_text(self) -> None:
        bad = {
            "card_id": "bad",
            "title": "Bad",
            "applies_when": ["sem_19 fails"],
            "semantic_boundary": "x",
            "search_directions": ["x"],
            "avoid": ["x"],
        }
        self.assertIn("forbidden_term:sem_", validate_strategy_card(bad))


if __name__ == "__main__":
    unittest.main()
