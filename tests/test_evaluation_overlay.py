from __future__ import annotations

import unittest

from scripts.build_evaluation_overlay import build_overlay, load_replacements


class EvaluationOverlayTests(unittest.TestCase):
    def test_overlay_applies_only_passing_replacements_to_failures(self) -> None:
        base_rows = [
            {"case_id": "case_a", "bucket": "small", "subject_status": "fail", "baseline_status": "pass"},
            {"case_id": "case_b", "bucket": "small", "subject_status": "pass", "baseline_status": "pass"},
            {"case_id": "case_c", "bucket": "large", "subject_status": "fail", "baseline_status": "fail"},
        ]
        replacements = {
            "case_a": {"case_id": "case_a", "status": "pass", "source": "replacement.jsonl", "tokens": 10},
            "case_b": {"case_id": "case_b", "status": "pass", "source": "replacement.jsonl", "tokens": 20},
            "case_x": {"case_id": "case_x", "status": "pass", "source": "replacement.jsonl", "tokens": 30},
        }

        adjusted, summary = build_overlay(
            base_rows=base_rows,
            replacements=replacements,
            subject_key="subject_status",
        )

        self.assertEqual(adjusted[0]["subject_status"], "pass")
        self.assertNotIn("overlay_replacement", adjusted[1])
        self.assertEqual(summary["subject_pass"], 2)
        self.assertEqual(summary["applied_replacement_case_ids"], ["case_a"])
        self.assertEqual(summary["missing_replacement_case_ids"], ["case_x"])
        self.assertEqual(summary["status"], "REVIEW")

    def test_load_replacements_ignores_failed_rows(self) -> None:
        import tempfile
        from pathlib import Path
        import json

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "rows.jsonl"
            path.write_text(
                json.dumps({"case_id": "case_a", "status": "pass"}) + "\n"
                + json.dumps({"case_id": "case_b", "status": "fail"}) + "\n",
                encoding="utf-8",
            )

            replacements = load_replacements([path])

        self.assertEqual(sorted(replacements), ["case_a"])


if __name__ == "__main__":
    unittest.main()
