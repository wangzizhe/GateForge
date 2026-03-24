from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_l5_performance_trend_v1 import compute_l5_performance_trend


def _make_row(iso_dt: str, success_at_k_pct: float, gate_result: str) -> dict:
    """Build a minimal ledger row."""
    return {
        "generated_at_utc": iso_dt,
        "success_at_k_pct": success_at_k_pct,
        "gate_result": gate_result,
    }


def _write_ledger(tmp_dir: str, rows: list[dict]) -> str:
    path = str(Path(tmp_dir) / "ledger.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return path


class TestInsufficientData(unittest.TestCase):
    """authority_status when there is not enough history."""

    def test_no_rows_gives_insufficient_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            ledger = _write_ledger(tmp, [])
            result = compute_l5_performance_trend(ledger_path=ledger)

        self.assertEqual(result["authority_status"], "insufficient_data")
        self.assertIsNone(result["baseline_derived_pct"])
        self.assertIsNone(result["volatility_pp"])
        self.assertEqual(result["trend_direction"], "unknown")
        self.assertEqual(result["consecutive_pass_weeks"], 0)
        self.assertEqual(result["consecutive_fail_weeks"], 0)
        self.assertIn("authority_status_insufficient_data", result["reasons"])

    def test_one_week_gives_insufficient_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [_make_row("2026-W10T10:00:00+00:00", 80.0, "PASS")]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        self.assertEqual(result["authority_status"], "insufficient_data")
        self.assertAlmostEqual(result["baseline_derived_pct"], 80.0)
        self.assertAlmostEqual(result["volatility_pp"], 0.0)
        self.assertEqual(result["trend_direction"], "unknown")
        self.assertEqual(result["consecutive_pass_weeks"], 1)

    def test_missing_ledger_file_gives_insufficient_data(self) -> None:
        result = compute_l5_performance_trend(ledger_path="/nonexistent/path/ledger.jsonl")

        self.assertEqual(result["authority_status"], "insufficient_data")
        self.assertEqual(result["total_ledger_weeks"], 0)


class TestCalibratingStatus(unittest.TestCase):
    """authority_status == 'calibrating' with 2–3 weeks."""

    def test_two_weeks_gives_calibrating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                _make_row("2026-03-09T10:00:00+00:00", 70.0, "PASS"),
                _make_row("2026-03-16T10:00:00+00:00", 75.0, "PASS"),
            ]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        self.assertEqual(result["authority_status"], "calibrating")
        self.assertEqual(result["total_ledger_weeks"], 2)
        self.assertEqual(result["window_row_count"], 2)
        self.assertIn("authority_status_calibrating", result["reasons"])

    def test_three_weeks_gives_calibrating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                _make_row("2026-03-02T10:00:00+00:00", 70.0, "PASS"),
                _make_row("2026-03-09T10:00:00+00:00", 72.0, "PASS"),
                _make_row("2026-03-16T10:00:00+00:00", 74.0, "PASS"),
            ]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        self.assertEqual(result["authority_status"], "calibrating")
        self.assertEqual(result["total_ledger_weeks"], 3)


class TestStableStatus(unittest.TestCase):
    """authority_status == 'stable' with 4+ weeks, low volatility."""

    def test_four_weeks_low_volatility_gives_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                _make_row("2026-02-23T10:00:00+00:00", 80.0, "PASS"),
                _make_row("2026-03-02T10:00:00+00:00", 82.0, "PASS"),
                _make_row("2026-03-09T10:00:00+00:00", 81.0, "PASS"),
                _make_row("2026-03-16T10:00:00+00:00", 83.0, "PASS"),
            ]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        self.assertEqual(result["authority_status"], "stable")
        self.assertEqual(result["window_row_count"], 4)
        self.assertEqual(result["reasons"], [])

    def test_four_weeks_high_volatility_stays_calibrating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                _make_row("2026-02-23T10:00:00+00:00", 20.0, "FAIL"),
                _make_row("2026-03-02T10:00:00+00:00", 80.0, "PASS"),
                _make_row("2026-03-09T10:00:00+00:00", 20.0, "FAIL"),
                _make_row("2026-03-16T10:00:00+00:00", 80.0, "PASS"),
            ]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        # stdev of [20, 80, 20, 80] ≈ 34pp >> 10pp threshold
        self.assertEqual(result["authority_status"], "calibrating")
        self.assertGreater(result["volatility_pp"], 10.0)


class TestTrendDirection(unittest.TestCase):
    """trend_direction up / flat / down."""

    def test_trend_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                _make_row("2026-02-23T10:00:00+00:00", 60.0, "PASS"),
                _make_row("2026-03-02T10:00:00+00:00", 65.0, "PASS"),
                _make_row("2026-03-09T10:00:00+00:00", 70.0, "PASS"),
                _make_row("2026-03-16T10:00:00+00:00", 75.0, "PASS"),
            ]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        self.assertEqual(result["trend_direction"], "up")

    def test_trend_down(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                _make_row("2026-02-23T10:00:00+00:00", 80.0, "PASS"),
                _make_row("2026-03-02T10:00:00+00:00", 75.0, "PASS"),
                _make_row("2026-03-09T10:00:00+00:00", 70.0, "PASS"),
                _make_row("2026-03-16T10:00:00+00:00", 65.0, "FAIL"),
            ]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        self.assertEqual(result["trend_direction"], "down")

    def test_trend_flat(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                _make_row("2026-02-23T10:00:00+00:00", 75.0, "PASS"),
                _make_row("2026-03-02T10:00:00+00:00", 75.5, "PASS"),
                _make_row("2026-03-09T10:00:00+00:00", 74.5, "PASS"),
                _make_row("2026-03-16T10:00:00+00:00", 75.0, "PASS"),
            ]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        self.assertEqual(result["trend_direction"], "flat")


class TestConsecutiveStreaks(unittest.TestCase):
    """consecutive_pass_weeks and consecutive_fail_weeks."""

    def test_consecutive_pass_streak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                _make_row("2026-02-09T10:00:00+00:00", 50.0, "FAIL"),
                _make_row("2026-02-16T10:00:00+00:00", 70.0, "FAIL"),
                _make_row("2026-02-23T10:00:00+00:00", 75.0, "PASS"),
                _make_row("2026-03-02T10:00:00+00:00", 78.0, "PASS"),
                _make_row("2026-03-09T10:00:00+00:00", 80.0, "PASS"),
                _make_row("2026-03-16T10:00:00+00:00", 82.0, "PASS"),
            ]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        self.assertEqual(result["consecutive_pass_weeks"], 4)
        self.assertEqual(result["consecutive_fail_weeks"], 0)

    def test_consecutive_fail_streak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                _make_row("2026-03-02T10:00:00+00:00", 80.0, "PASS"),
                _make_row("2026-03-09T10:00:00+00:00", 30.0, "FAIL"),
                _make_row("2026-03-16T10:00:00+00:00", 25.0, "FAIL"),
            ]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        self.assertEqual(result["consecutive_fail_weeks"], 2)
        self.assertEqual(result["consecutive_pass_weeks"], 0)


class TestMultipleRowsSameWeek(unittest.TestCase):
    """Multiple rows within the same ISO week — only latest survives."""

    def test_same_week_keeps_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                # Both fall in 2026-W11 (Mon 2026-03-09)
                _make_row("2026-03-09T08:00:00+00:00", 40.0, "FAIL"),
                _make_row("2026-03-11T12:00:00+00:00", 85.0, "PASS"),
                # A different week
                _make_row("2026-03-16T10:00:00+00:00", 87.0, "PASS"),
            ]
            ledger = _write_ledger(tmp, rows)
            result = compute_l5_performance_trend(ledger_path=ledger)

        # Should only see 2 weeks, not 3
        self.assertEqual(result["total_ledger_weeks"], 2)
        # The latest row in W11 has success_at_k_pct=85.0; latest overall is 87.0
        self.assertAlmostEqual(result["baseline_derived_pct"], (85.0 + 87.0) / 2)
        # The most recent week gate result (W12) is PASS
        self.assertEqual(result["consecutive_pass_weeks"], 2)


class TestCLIRoundtrip(unittest.TestCase):
    """CLI invocation with 5 low-volatility rows spanning 4 weeks."""

    def test_cli_stable_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = [
                _make_row("2026-02-23T10:00:00+00:00", 80.0, "PASS"),
                _make_row("2026-03-02T10:00:00+00:00", 81.0, "PASS"),
                # Two rows same week — only latest survives
                _make_row("2026-03-09T08:00:00+00:00", 50.0, "FAIL"),
                _make_row("2026-03-09T18:00:00+00:00", 82.0, "PASS"),
                _make_row("2026-03-16T10:00:00+00:00", 83.0, "PASS"),
            ]
            ledger = _write_ledger(tmp, rows)
            out_json = str(Path(tmp) / "trend.json")
            out_md = str(Path(tmp) / "trend.md")

            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_l5_performance_trend_v1",
                    "--ledger",
                    ledger,
                    "--window-weeks",
                    "4",
                    "--out",
                    out_json,
                    "--report-out",
                    out_md,
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)

            # stdout should be parseable JSON summary
            stdout_payload = json.loads(proc.stdout.strip())
            self.assertEqual(stdout_payload["authority_status"], "stable")
            self.assertIsInstance(stdout_payload["baseline_derived_pct"], float)
            self.assertEqual(stdout_payload["window_weeks"], 4)
            self.assertEqual(stdout_payload["total_ledger_weeks"], 4)

            # JSON output file should exist and be valid
            self.assertTrue(Path(out_json).exists())
            full_payload = json.loads(Path(out_json).read_text(encoding="utf-8"))
            self.assertEqual(full_payload["schema_version"], "agent_modelica_l5_performance_trend_v1")
            self.assertEqual(full_payload["authority_status"], "stable")

            # Markdown output file should exist
            self.assertTrue(Path(out_md).exists())


if __name__ == "__main__":
    unittest.main()
