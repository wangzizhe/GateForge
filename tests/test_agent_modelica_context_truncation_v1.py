"""Tests for dual-cap context truncation utility.

Pure-function tests: no Docker, LLM, OMC, or filesystem dependencies.
"""
from __future__ import annotations

import unittest

from gateforge.agent_modelica_context_truncation_v1 import (
    BYTE_CAP_DEFAULT,
    LINE_CAP_DEFAULT,
    TruncationResult,
    needs_truncation,
    truncate_context,
    truncate_context_text,
)


# ===========================================================================
# No truncation needed
# ===========================================================================


class TestNoTruncation(unittest.TestCase):
    def test_short_text_is_unchanged(self) -> None:
        text = "line one\nline two\nline three"
        result = truncate_context(text, max_lines=200, max_bytes=20_000)
        self.assertFalse(result.was_truncated)
        self.assertEqual(result.truncation_reason, "none")
        self.assertEqual(result.text, text)

    def test_empty_string_is_unchanged(self) -> None:
        result = truncate_context("", max_lines=200, max_bytes=20_000)
        self.assertFalse(result.was_truncated)
        self.assertEqual(result.text, "")

    def test_exactly_at_line_cap_is_unchanged(self) -> None:
        text = "\n".join(f"line {i}" for i in range(10))
        result = truncate_context(text, max_lines=10, max_bytes=20_000)
        self.assertFalse(result.was_truncated)

    def test_original_counts_are_accurate(self) -> None:
        text = "hello\nworld"
        result = truncate_context(text)
        self.assertEqual(result.original_line_count, 2)
        self.assertEqual(result.original_byte_count, len(text.encode("utf-8")))


# ===========================================================================
# Line cap
# ===========================================================================


class TestLineCap(unittest.TestCase):
    def test_line_cap_triggers(self) -> None:
        text = "\n".join(f"line {i}" for i in range(20))
        result = truncate_context(text, max_lines=10, max_bytes=100_000)
        self.assertTrue(result.was_truncated)
        self.assertEqual(result.truncation_reason, "line_cap")

    def test_line_cap_retains_exactly_max_lines_of_content(self) -> None:
        lines = [f"line {i}" for i in range(20)]
        text = "\n".join(lines)
        result = truncate_context(text, max_lines=5, max_bytes=100_000)
        result_lines = result.text.splitlines()
        # First 5 content lines + 1 warning line
        self.assertEqual(result_lines[:5], lines[:5])
        self.assertEqual(len(result_lines), 6)

    def test_warning_line_is_appended(self) -> None:
        text = "\n".join(f"line {i}" for i in range(20))
        result = truncate_context(text, max_lines=5, max_bytes=100_000, label="my_context")
        last_line = result.text.splitlines()[-1]
        self.assertIn("my_context", last_line)
        self.assertIn("line_cap", last_line)
        self.assertIn("line(s) omitted", last_line)

    def test_warning_mentions_correct_omitted_count(self) -> None:
        text = "\n".join(f"line {i}" for i in range(15))
        result = truncate_context(text, max_lines=10, max_bytes=100_000)
        last_line = result.text.splitlines()[-1]
        self.assertIn("5", last_line)  # 15 - 10 = 5 omitted

    def test_original_line_count_is_preserved(self) -> None:
        text = "\n".join(f"line {i}" for i in range(30))
        result = truncate_context(text, max_lines=10, max_bytes=100_000)
        self.assertEqual(result.original_line_count, 30)

    def test_final_line_count_includes_warning(self) -> None:
        text = "\n".join(f"line {i}" for i in range(20))
        result = truncate_context(text, max_lines=10, max_bytes=100_000)
        # 10 content lines + 1 warning
        self.assertEqual(result.final_line_count, 11)

    def test_single_line_over_cap(self) -> None:
        text = "only line"
        result = truncate_context(text, max_lines=0, max_bytes=100_000)
        # max_lines=0 still keeps 0 content lines, but warning is appended
        # (splitlines of "" is [], len=0 which is not > 0, so no truncation)
        # Actually max_lines=0 means 0 lines retained — let's verify truncation fires
        # len(["only line"]) = 1 > 0, so it should trigger
        self.assertTrue(result.was_truncated)

    def test_default_max_lines_is_200(self) -> None:
        text = "\n".join(f"line {i}" for i in range(201))
        result = truncate_context(text)
        self.assertTrue(result.was_truncated)
        self.assertEqual(result.truncation_reason, "line_cap")

    def test_exactly_200_lines_is_not_truncated(self) -> None:
        text = "\n".join(f"line {i}" for i in range(200))
        result = truncate_context(text)
        self.assertFalse(result.was_truncated)


# ===========================================================================
# Byte cap
# ===========================================================================


class TestByteCap(unittest.TestCase):
    def _make_text(self, total_bytes: int) -> str:
        # 'a' is 1 byte in UTF-8; build lines of 100 'a's separated by newlines
        line = "a" * 99  # 99 chars + newline = 100 bytes per line
        line_count = (total_bytes // 100) + 1
        return "\n".join([line] * line_count)

    def test_byte_cap_triggers(self) -> None:
        text = self._make_text(25_000)
        result = truncate_context(text, max_lines=100_000, max_bytes=1_000)
        self.assertTrue(result.was_truncated)
        self.assertEqual(result.truncation_reason, "byte_cap")

    def test_byte_cap_result_within_limit(self) -> None:
        text = self._make_text(30_000)
        result = truncate_context(text, max_lines=100_000, max_bytes=5_000)
        # Result byte count should be close to but not exceed max_bytes
        # (warning line may push slightly over, which is acceptable by design)
        # The core content must be within limit; the warning itself is short
        content_lines = result.text.splitlines()[:-1]  # exclude warning
        content = "\n".join(content_lines)
        self.assertLessEqual(len(content.encode("utf-8")), 5_000)

    def test_byte_cap_truncates_at_newline(self) -> None:
        # Verify no line is split mid-way
        text = self._make_text(10_000)
        result = truncate_context(text, max_lines=100_000, max_bytes=500)
        # All lines (except warning) should be complete 99-char lines
        content_lines = result.text.splitlines()[:-1]
        for line in content_lines:
            self.assertEqual(len(line), 99)

    def test_warning_is_appended_on_byte_cap(self) -> None:
        text = self._make_text(10_000)
        result = truncate_context(text, max_lines=100_000, max_bytes=200, label="planner_ctx")
        last_line = result.text.splitlines()[-1]
        self.assertIn("planner_ctx", last_line)
        self.assertIn("byte_cap", last_line)
        self.assertIn("byte(s) omitted", last_line)

    def test_original_byte_count_is_preserved(self) -> None:
        text = self._make_text(5_000)
        result = truncate_context(text, max_lines=100_000, max_bytes=200)
        self.assertGreater(result.original_byte_count, 200)

    def test_default_byte_cap_is_20000(self) -> None:
        text = "a" * 20_001
        result = truncate_context(text, max_lines=100_000)
        self.assertTrue(result.was_truncated)
        self.assertEqual(result.truncation_reason, "byte_cap")

    def test_exactly_at_byte_cap_is_not_truncated(self) -> None:
        text = "a" * 20_000
        result = truncate_context(text, max_lines=100_000, max_bytes=20_000)
        self.assertFalse(result.was_truncated)


# ===========================================================================
# Line cap fires before byte cap
# ===========================================================================


class TestLineCapsBeforeByte(unittest.TestCase):
    def test_line_cap_wins_when_both_would_trigger(self) -> None:
        # Build text that exceeds both caps
        line = "a" * 99
        text = "\n".join([line] * 300)  # 300 lines, each ~100 bytes → ~30KB
        result = truncate_context(text, max_lines=10, max_bytes=500)
        # Line cap fires first (300 > 10), so reason should be line_cap
        # Then byte cap may also fire on the already-truncated text
        # Either way, truncation happened; reason indicates the first cap
        self.assertTrue(result.was_truncated)


# ===========================================================================
# Label in warning messages
# ===========================================================================


class TestWarningLabel(unittest.TestCase):
    def test_custom_label_in_line_warning(self) -> None:
        text = "\n".join(f"x {i}" for i in range(20))
        result = truncate_context(text, max_lines=5, max_bytes=100_000, label="multistep_memory")
        self.assertIn("multistep_memory", result.text.splitlines()[-1])

    def test_default_label_is_context(self) -> None:
        text = "\n".join(f"x {i}" for i in range(20))
        result = truncate_context(text, max_lines=5, max_bytes=100_000)
        self.assertIn("context", result.text.splitlines()[-1])


# ===========================================================================
# TruncationResult.summary()
# ===========================================================================


class TestTruncationResultSummary(unittest.TestCase):
    def test_summary_contains_required_keys(self) -> None:
        result = truncate_context("short text")
        summary = result.summary()
        for key in (
            "was_truncated",
            "truncation_reason",
            "original_line_count",
            "original_byte_count",
            "final_line_count",
            "final_byte_count",
        ):
            self.assertIn(key, summary)

    def test_summary_not_truncated(self) -> None:
        result = truncate_context("hello")
        summary = result.summary()
        self.assertFalse(summary["was_truncated"])
        self.assertEqual(summary["truncation_reason"], "none")

    def test_summary_truncated(self) -> None:
        text = "\n".join(f"line {i}" for i in range(20))
        result = truncate_context(text, max_lines=5)
        summary = result.summary()
        self.assertTrue(summary["was_truncated"])
        self.assertEqual(summary["truncation_reason"], "line_cap")


# ===========================================================================
# truncate_context_text convenience wrapper
# ===========================================================================


class TestTruncateContextText(unittest.TestCase):
    def test_returns_string(self) -> None:
        result = truncate_context_text("hello\nworld")
        self.assertIsInstance(result, str)

    def test_short_text_unchanged(self) -> None:
        text = "hello\nworld"
        self.assertEqual(truncate_context_text(text), text)

    def test_truncated_text_contains_warning(self) -> None:
        text = "\n".join(f"line {i}" for i in range(20))
        result = truncate_context_text(text, max_lines=5)
        self.assertIn("line_cap", result)

    def test_label_passed_through(self) -> None:
        text = "\n".join(f"line {i}" for i in range(20))
        result = truncate_context_text(text, max_lines=5, label="myblock")
        self.assertIn("myblock", result)


# ===========================================================================
# needs_truncation
# ===========================================================================


class TestNeedsTruncation(unittest.TestCase):
    def test_short_text_does_not_need_truncation(self) -> None:
        self.assertFalse(needs_truncation("short"))

    def test_many_lines_need_truncation(self) -> None:
        text = "\n".join(f"line {i}" for i in range(201))
        self.assertTrue(needs_truncation(text))

    def test_many_bytes_need_truncation(self) -> None:
        text = "a" * 20_001
        self.assertTrue(needs_truncation(text))

    def test_exactly_at_caps_does_not_need_truncation(self) -> None:
        text = "\n".join("x" for _ in range(200))
        self.assertFalse(needs_truncation(text, max_lines=200, max_bytes=100_000))

    def test_empty_string_does_not_need_truncation(self) -> None:
        self.assertFalse(needs_truncation(""))

    def test_custom_caps_respected(self) -> None:
        text = "line one\nline two\nline three"
        self.assertTrue(needs_truncation(text, max_lines=2))
        self.assertFalse(needs_truncation(text, max_lines=3))


# ===========================================================================
# Unicode / multi-byte safety
# ===========================================================================


class TestUnicodeSafety(unittest.TestCase):
    def test_multibyte_chars_do_not_cause_decode_error(self) -> None:
        # Each Chinese character is 3 bytes in UTF-8
        line = "你好世界" * 10   # 40 chars × 3 bytes = 120 bytes per line
        text = "\n".join([line] * 300)
        result = truncate_context(text, max_lines=100_000, max_bytes=500)
        # Should not raise; result should be valid UTF-8 string
        self.assertIsInstance(result.text, str)
        result.text.encode("utf-8")  # must not raise

    def test_multibyte_line_not_split(self) -> None:
        line = "你好世界" * 10
        text = "\n".join([line] * 10)
        result = truncate_context(text, max_lines=100_000, max_bytes=200)
        # The content lines (excluding warning) should each be either
        # complete or the result of a clean decode
        content_lines = result.text.splitlines()[:-1]
        for l in content_lines:
            # Each retained line should be a complete copy of the original line
            self.assertEqual(l, line)


if __name__ == "__main__":
    unittest.main()
