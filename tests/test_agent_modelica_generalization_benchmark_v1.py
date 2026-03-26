"""Unit tests for agent_modelica_generalization_benchmark_v1 pure helpers."""
from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateforge.agent_modelica_generalization_benchmark_v1 import (
    compute_metrics,
    load_hardpack_cases,
    render_markdown,
    run_benchmark,
    verdict,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_result(success: bool, ft: str = "model_check_error", sc: str = "small") -> dict:
    return {
        "success": success,
        "expected_failure_type": ft,
        "target_scale": sc,
    }


def _write_pack(tmp_dir: str, cases: list[dict]) -> str:
    path = os.path.join(tmp_dir, "pack.json")
    pack = {"schema_version": "hardpack_v1", "cases": cases}
    Path(path).write_text(json.dumps(pack), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# TestLoadHardpackCases
# ---------------------------------------------------------------------------


class TestLoadHardpackCases(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        self.assertEqual(load_hardpack_cases("/nonexistent/pack.json"), [])

    def test_empty_cases_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_pack(tmp, [])
            self.assertEqual(load_hardpack_cases(path), [])

    def test_loads_all_cases(self):
        cases = [
            {"mutation_id": "m1", "target_scale": "small", "expected_failure_type": "model_check_error"},
            {"mutation_id": "m2", "target_scale": "large", "expected_failure_type": "simulate_error"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_pack(tmp, cases)
            result = load_hardpack_cases(path)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["mutation_id"], "m1")

    def test_max_cases_limits_output(self):
        cases = [{"mutation_id": f"m{i}"} for i in range(10)]
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_pack(tmp, cases)
            result = load_hardpack_cases(path, max_cases=3)
        self.assertEqual(len(result), 3)

    def test_max_cases_zero_returns_all(self):
        cases = [{"mutation_id": f"m{i}"} for i in range(5)]
        with tempfile.TemporaryDirectory() as tmp:
            path = _write_pack(tmp, cases)
            result = load_hardpack_cases(path, max_cases=0)
        self.assertEqual(len(result), 5)

    def test_malformed_json_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bad.json")
            Path(path).write_text("not json", encoding="utf-8")
            self.assertEqual(load_hardpack_cases(path), [])

    def test_non_dict_cases_filtered(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "pack.json")
            Path(path).write_text(
                json.dumps({"cases": [{"ok": True}, "bad", None, 42]}),
                encoding="utf-8",
            )
            result = load_hardpack_cases(path)
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# TestComputeMetrics
# ---------------------------------------------------------------------------


class TestComputeMetrics(unittest.TestCase):
    def test_empty_returns_zeros(self):
        m = compute_metrics([])
        self.assertEqual(m["total"], 0)
        self.assertEqual(m["repair_rate"], 0.0)

    def test_all_success(self):
        results = [_make_result(True)] * 4
        m = compute_metrics(results)
        self.assertEqual(m["total"], 4)
        self.assertEqual(m["success"], 4)
        self.assertEqual(m["repair_rate"], 1.0)

    def test_all_failure(self):
        results = [_make_result(False)] * 3
        m = compute_metrics(results)
        self.assertEqual(m["success"], 0)
        self.assertEqual(m["repair_rate"], 0.0)

    def test_mixed_repair_rate(self):
        results = [_make_result(True)] * 3 + [_make_result(False)] * 1
        m = compute_metrics(results)
        self.assertAlmostEqual(m["repair_rate"], 0.75, places=3)

    def test_by_failure_type_breakdown(self):
        results = [
            _make_result(True, ft="model_check_error"),
            _make_result(False, ft="model_check_error"),
            _make_result(True, ft="simulate_error"),
        ]
        m = compute_metrics(results)
        self.assertEqual(m["by_failure_type"]["model_check_error"]["total"], 2)
        self.assertEqual(m["by_failure_type"]["model_check_error"]["success"], 1)
        self.assertEqual(m["by_failure_type"]["simulate_error"]["total"], 1)

    def test_by_scale_breakdown(self):
        results = [
            _make_result(True, sc="small"),
            _make_result(False, sc="small"),
            _make_result(True, sc="large"),
        ]
        m = compute_metrics(results)
        self.assertEqual(m["by_scale"]["small"]["total"], 2)
        self.assertEqual(m["by_scale"]["large"]["success"], 1)

    def test_repair_rate_in_breakdown(self):
        results = [
            _make_result(True, ft="model_check_error"),
            _make_result(True, ft="model_check_error"),
        ]
        m = compute_metrics(results)
        self.assertEqual(
            m["by_failure_type"]["model_check_error"]["repair_rate"], 1.0
        )

    def test_unknown_field_fallback(self):
        # Results with no expected_failure_type should go to "unknown"
        results = [{"success": True}]
        m = compute_metrics(results)
        self.assertIn("unknown", m["by_failure_type"])


# ---------------------------------------------------------------------------
# TestVerdict
# ---------------------------------------------------------------------------


class TestVerdict(unittest.TestCase):
    def test_gf_advantage(self):
        self.assertEqual(verdict(0.40, 0.60), "GATEFORGE_ADVANTAGE")

    def test_inconclusive_close(self):
        self.assertEqual(verdict(0.50, 0.53), "INCONCLUSIVE")

    def test_inconclusive_equal(self):
        self.assertEqual(verdict(0.50, 0.50), "INCONCLUSIVE")

    def test_bare_llm_better(self):
        self.assertEqual(verdict(0.70, 0.40), "BARE_LLM_BETTER")

    def test_no_gf_results(self):
        self.assertEqual(verdict(0.50, None), "BARE_LLM_ONLY")

    def test_exact_threshold_advantage(self):
        # diff == 0.05 exactly → GATEFORGE_ADVANTAGE
        self.assertEqual(verdict(0.50, 0.55), "GATEFORGE_ADVANTAGE")

    def test_just_below_threshold(self):
        # diff = 0.049 → INCONCLUSIVE
        self.assertEqual(verdict(0.50, 0.549), "INCONCLUSIVE")


# ---------------------------------------------------------------------------
# TestRenderMarkdown
# ---------------------------------------------------------------------------


class TestRenderMarkdown(unittest.TestCase):
    def _make_summary(self, with_gf: bool = False) -> dict:
        bare_metrics = {
            "total": 10,
            "success": 6,
            "failure": 4,
            "repair_rate": 0.6,
            "by_failure_type": {
                "model_check_error": {"total": 5, "success": 3, "repair_rate": 0.6},
                "simulate_error": {"total": 5, "success": 3, "repair_rate": 0.6},
            },
            "by_scale": {
                "small": {"total": 5, "success": 3, "repair_rate": 0.6},
                "large": {"total": 5, "success": 3, "repair_rate": 0.6},
            },
        }
        gf = {"total": 10, "success": 8, "repair_rate": 0.8} if with_gf else None
        return {
            "generated_at_utc": "2026-03-25T00:00:00+00:00",
            "status": "PASS",
            "verdict": "GATEFORGE_ADVANTAGE",
            "bare_llm_metrics": bare_metrics,
            "gateforge_metrics": gf,
        }

    def test_contains_title(self):
        md = render_markdown(self._make_summary())
        self.assertIn("agent_modelica_generalization_benchmark_v1", md)

    def test_contains_repair_rate(self):
        md = render_markdown(self._make_summary())
        self.assertIn("60.0%", md)

    def test_contains_verdict(self):
        md = render_markdown(self._make_summary())
        self.assertIn("GATEFORGE_ADVANTAGE", md)

    def test_gf_section_absent_when_none(self):
        md = render_markdown(self._make_summary(with_gf=False))
        self.assertNotIn("GateForge Agent", md)

    def test_gf_section_present_when_provided(self):
        md = render_markdown(self._make_summary(with_gf=True))
        self.assertIn("GateForge Agent", md)

    def test_failure_type_table(self):
        md = render_markdown(self._make_summary())
        self.assertIn("model_check_error", md)
        self.assertIn("simulate_error", md)


class TestRunBenchmarkPreflight(unittest.TestCase):
    def test_fails_when_pack_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            pack = root / "benchmarks" / "private" / "pack.json"
            pack.parent.mkdir(parents=True, exist_ok=True)
            pack.write_text(
                json.dumps(
                    {
                        "schema_version": "hardpack_v1",
                        "cases": [
                            {
                                "mutation_id": "missing",
                                "target_scale": "small",
                                "expected_failure_type": "model_check_error",
                                "mutated_model_path": "artifacts/missing.mo",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out = root / "summary.json"

            with mock.patch(
                "gateforge.agent_modelica_generalization_benchmark_v1.run_bare_repair"
            ) as run_bare:
                summary = run_benchmark(
                    pack_path=str(pack),
                    backend="rule",
                    out=str(out),
                )
                payload = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(summary["verdict"], "PACK_INCOMPLETE")
        self.assertEqual(summary["pack_validation"]["missing_mutated_model_count"], 1)
        run_bare.assert_not_called()
        self.assertEqual(payload["verdict"], "PACK_INCOMPLETE")

    def test_success_path_emits_bare_batch_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            mutated = root / "artifacts" / "ok.mo"
            mutated.parent.mkdir(parents=True, exist_ok=True)
            mutated.write_text("model Ok end Ok;", encoding="utf-8")
            pack = root / "benchmarks" / "private" / "pack.json"
            pack.parent.mkdir(parents=True, exist_ok=True)
            pack.write_text(
                json.dumps(
                    {
                        "schema_version": "hardpack_v1",
                        "cases": [
                            {
                                "mutation_id": "ok",
                                "target_scale": "small",
                                "expected_failure_type": "model_check_error",
                                "mutated_model_path": "artifacts/ok.mo",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            out = root / "summary.json"
            stderr = io.StringIO()

            with mock.patch(
                "gateforge.agent_modelica_generalization_benchmark_v1.run_bare_repair",
                return_value={
                    "success": True,
                    "repaired_text": "model Ok end Ok;",
                    "omc_error": "",
                    "error": "",
                    "provider": "gemini",
                    "model_name": "Ok",
                    "elapsed_sec": 1.25,
                },
            ):
                with contextlib.redirect_stderr(stderr):
                    summary = run_benchmark(
                        pack_path=str(pack),
                        backend="gemini",
                        out=str(out),
                    )

        self.assertEqual(summary["status"], "PASS")
        log = stderr.getvalue()
        self.assertIn("[Bare-batch] Running 1 cases", log)
        self.assertIn("[Bare-batch] [1/1] ok ... OK", log)
        self.assertIn("[Bare-batch] Done: 1/1 = 100.0%", log)


if __name__ == "__main__":
    unittest.main()
