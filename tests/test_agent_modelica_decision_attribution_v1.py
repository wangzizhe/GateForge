"""
Tests for agent_modelica_decision_attribution_v1.

All tests use synthetic attempts[] data -- no Docker, no mocks needed.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_decision_attribution_v1 import (
    attribute_decision,
    summarize_decision_attribution,
)


def _attempt(
    round_num: int,
    *,
    check_ok: bool = False,
    sim_ok: bool = False,
    first_plan_branch_match: bool | None = None,
    replan_used: bool = False,
    replan_resolved: bool = False,
    guided_search_used: bool = False,
    guided_search_resolution: bool = False,
    llm_plan_was_decisive: bool = False,
    applied_repairs: list[str] | None = None,
) -> dict:
    """Build a synthetic attempt record for testing."""
    rec: dict = {
        "round": round_num,
        "check_model_pass": check_ok,
        "simulate_pass": sim_ok,
        "replan_used": replan_used,
        "replan_resolved": replan_resolved,
        "guided_search_used": guided_search_used,
        "guided_search_resolution": guided_search_resolution,
        "llm_plan_was_decisive": llm_plan_was_decisive,
    }
    if first_plan_branch_match is not None:
        rec["first_plan_branch_match"] = first_plan_branch_match
    for key in (applied_repairs or []):
        rec[key] = {"applied": True, "reason": "test"}
    return rec


def _run_result(task_id: str, failure_type: str, attempts: list[dict]) -> dict:
    return {"task_id": task_id, "failure_type": failure_type, "attempts": attempts}


class TestDirectPath(unittest.TestCase):
    def test_direct_path(self) -> None:
        result = _run_result(
            "t1",
            "simulate_error",
            [_attempt(1, check_ok=True, sim_ok=True, first_plan_branch_match=True)],
        )
        rec = attribute_decision(result)
        self.assertEqual(rec["causal_path"], "direct")
        self.assertEqual(rec["decisive_round"], 1)
        self.assertEqual(rec["first_plan_verdict"], "correct")
        self.assertFalse(rec["replan_corrected"])

    def test_direct_path_requires_first_plan_correct(self) -> None:
        # Round 1 passes but first_plan_branch_match=False => not "direct"
        result = _run_result(
            "t1",
            "simulate_error",
            [_attempt(1, check_ok=True, sim_ok=True, first_plan_branch_match=False)],
        )
        rec = attribute_decision(result)
        self.assertNotEqual(rec["causal_path"], "direct")
        self.assertEqual(rec["first_plan_verdict"], "wrong")


class TestReplanCorrected(unittest.TestCase):
    def test_replan_corrected(self) -> None:
        result = _run_result(
            "t2",
            "model_check_error",
            [
                _attempt(1, check_ok=False, sim_ok=False, first_plan_branch_match=False),
                _attempt(
                    2,
                    check_ok=True,
                    sim_ok=True,
                    replan_used=True,
                    replan_resolved=True,
                ),
            ],
        )
        rec = attribute_decision(result)
        self.assertEqual(rec["causal_path"], "replan_corrected")
        self.assertTrue(rec["replan_corrected"])
        self.assertEqual(rec["decisive_round"], 2)

    def test_replan_used_but_not_resolved_is_not_replan_corrected(self) -> None:
        result = _run_result(
            "t2",
            "model_check_error",
            [
                _attempt(1, check_ok=False, sim_ok=False),
                _attempt(2, check_ok=True, sim_ok=True, replan_used=True, replan_resolved=False),
            ],
        )
        rec = attribute_decision(result)
        self.assertFalse(rec["replan_corrected"])


class TestExhaustivePath(unittest.TestCase):
    def test_exhaustive_path(self) -> None:
        # Resolves at round 3, no replan, no guided search correction
        result = _run_result(
            "t3",
            "simulate_error",
            [
                _attempt(1, check_ok=False),
                _attempt(2, check_ok=False),
                _attempt(3, check_ok=True, sim_ok=True),
            ],
        )
        rec = attribute_decision(result)
        self.assertEqual(rec["causal_path"], "exhaustive")
        self.assertEqual(rec["decisive_round"], 3)
        self.assertEqual(rec["total_rounds"], 3)


class TestFailedRun(unittest.TestCase):
    def test_failed_run(self) -> None:
        result = _run_result(
            "t4",
            "simulate_error",
            [
                _attempt(1, check_ok=False),
                _attempt(2, check_ok=False),
                _attempt(3, check_ok=True, sim_ok=False),
            ],
        )
        rec = attribute_decision(result)
        self.assertIsNone(rec["decisive_round"])
        self.assertEqual(rec["causal_path"], "failed")

    def test_empty_attempts(self) -> None:
        rec = attribute_decision({"task_id": "t0", "failure_type": "x", "attempts": []})
        self.assertIsNone(rec["decisive_round"])
        self.assertEqual(rec["causal_path"], "failed")
        self.assertEqual(rec["total_rounds"], 0)


class TestGuidedSearchPath(unittest.TestCase):
    def test_guided_search_path(self) -> None:
        result = _run_result(
            "t5",
            "simulate_error",
            [
                _attempt(1, check_ok=False),
                _attempt(
                    2,
                    check_ok=True,
                    sim_ok=True,
                    guided_search_used=True,
                    guided_search_resolution=True,
                ),
            ],
        )
        rec = attribute_decision(result)
        self.assertEqual(rec["causal_path"], "guided_search")

    def test_guided_search_without_resolution_is_exhaustive(self) -> None:
        result = _run_result(
            "t5",
            "simulate_error",
            [
                _attempt(1, check_ok=False),
                _attempt(
                    2,
                    check_ok=True,
                    sim_ok=True,
                    guided_search_used=True,
                    guided_search_resolution=False,
                ),
            ],
        )
        rec = attribute_decision(result)
        self.assertEqual(rec["causal_path"], "exhaustive")


class TestFirstPlanVerdict(unittest.TestCase):
    def test_correct(self) -> None:
        result = _run_result(
            "t6", "x", [_attempt(1, check_ok=True, sim_ok=True, first_plan_branch_match=True)]
        )
        self.assertEqual(attribute_decision(result)["first_plan_verdict"], "correct")

    def test_wrong(self) -> None:
        result = _run_result(
            "t6", "x", [_attempt(1, check_ok=False, first_plan_branch_match=False)]
        )
        self.assertEqual(attribute_decision(result)["first_plan_verdict"], "wrong")

    def test_unknown_when_field_absent(self) -> None:
        result = _run_result("t6", "x", [_attempt(1, check_ok=True, sim_ok=True)])
        self.assertEqual(attribute_decision(result)["first_plan_verdict"], "unknown")


class TestDecisiveActionsExtracted(unittest.TestCase):
    def test_applied_repair_methods_collected(self) -> None:
        result = _run_result(
            "t7",
            "x",
            [
                _attempt(
                    1,
                    check_ok=True,
                    sim_ok=True,
                    applied_repairs=["pre_repair", "source_repair"],
                )
            ],
        )
        rec = attribute_decision(result)
        self.assertIn("pre_repair", rec["decisive_actions"])
        self.assertIn("source_repair", rec["decisive_actions"])

    def test_unapplied_repairs_excluded(self) -> None:
        attempt = _attempt(1, check_ok=True, sim_ok=True)
        attempt["pre_repair"] = {"applied": False, "reason": "skipped"}
        attempt["source_repair"] = {"applied": True, "reason": "ok"}
        result = _run_result("t7", "x", [attempt])
        rec = attribute_decision(result)
        self.assertNotIn("pre_repair", rec["decisive_actions"])
        self.assertIn("source_repair", rec["decisive_actions"])

    def test_no_decisive_round_gives_empty_actions(self) -> None:
        result = _run_result("t7", "x", [_attempt(1, check_ok=False)])
        rec = attribute_decision(result)
        self.assertEqual(rec["decisive_actions"], [])

    def test_llm_was_decisive_flag(self) -> None:
        result = _run_result(
            "t7",
            "x",
            [_attempt(1, check_ok=True, sim_ok=True, llm_plan_was_decisive=True)],
        )
        rec = attribute_decision(result)
        self.assertTrue(rec["llm_was_decisive"])


class TestSummarizeMixed(unittest.TestCase):
    def _make_records(self) -> list[dict]:
        return [
            attribute_decision(
                _run_result(
                    "t1",
                    "x",
                    [_attempt(1, check_ok=True, sim_ok=True, first_plan_branch_match=True)],
                )
            ),
            attribute_decision(
                _run_result(
                    "t2",
                    "x",
                    [
                        _attempt(1, check_ok=False, first_plan_branch_match=False),
                        _attempt(2, check_ok=True, sim_ok=True, replan_used=True, replan_resolved=True),
                    ],
                )
            ),
            attribute_decision(
                _run_result(
                    "t3",
                    "x",
                    [_attempt(1, check_ok=False), _attempt(2, check_ok=False)],
                )
            ),
            attribute_decision(
                _run_result(
                    "t4",
                    "x",
                    [
                        _attempt(1, check_ok=False),
                        _attempt(2, check_ok=True, sim_ok=True),
                    ],
                )
            ),
        ]

    def test_total_tasks(self) -> None:
        summary = summarize_decision_attribution(self._make_records())
        self.assertEqual(summary["total_tasks"], 4)

    def test_causal_path_distribution(self) -> None:
        summary = summarize_decision_attribution(self._make_records())
        dist = summary["causal_path_distribution"]
        self.assertEqual(dist["direct"], 1)
        self.assertEqual(dist["replan_corrected"], 1)
        self.assertEqual(dist["failed"], 1)
        self.assertEqual(dist["exhaustive"], 1)

    def test_first_plan_correct_pct(self) -> None:
        summary = summarize_decision_attribution(self._make_records())
        # 1 out of 4 has first_plan_verdict=="correct"
        self.assertAlmostEqual(summary["first_plan_correct_pct"], 25.0)

    def test_median_rounds_to_success(self) -> None:
        summary = summarize_decision_attribution(self._make_records())
        # successful rounds: [1, 2, 2] -> median = 2.0
        self.assertAlmostEqual(summary["median_rounds_to_success"], 2.0)

    def test_schema_version_present(self) -> None:
        summary = summarize_decision_attribution(self._make_records())
        self.assertEqual(summary["schema_version"], "agent_modelica_decision_attribution_v1")

    def test_empty_records(self) -> None:
        summary = summarize_decision_attribution([])
        self.assertEqual(summary["total_tasks"], 0)
        self.assertEqual(summary["median_rounds_to_success"], 0.0)


class TestCLIRoundtrip(unittest.TestCase):
    def test_cli_produces_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run_results = root / "run_results.json"
            out = root / "attribution.json"
            run_results.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "task_id": "cli_t1",
                                "failure_type": "simulate_error",
                                "attempts": [
                                    {
                                        "round": 1,
                                        "check_model_pass": True,
                                        "simulate_pass": True,
                                        "first_plan_branch_match": True,
                                    }
                                ],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "gateforge.agent_modelica_decision_attribution_v1",
                    "--run-results",
                    str(run_results),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(out.read_text())
            self.assertEqual(data["schema_version"], "agent_modelica_decision_attribution_v1")
            self.assertEqual(len(data["records"]), 1)
            self.assertEqual(data["records"][0]["causal_path"], "direct")
            self.assertEqual(data["summary"]["causal_path_distribution"]["direct"], 1)


class TestWastedRounds(unittest.TestCase):
    def test_no_wasted_rounds_when_error_changes(self) -> None:
        attempts = [
            {**_attempt(1), "observed_failure_type": "model_check_error"},
            {**_attempt(2), "observed_failure_type": "simulate_error"},
            {**_attempt(3, check_ok=True, sim_ok=True), "observed_failure_type": ""},
        ]
        rec = attribute_decision(_run_result("t", "x", attempts))
        self.assertEqual(rec["wasted_rounds"], 0)

    def test_wasted_rounds_counted_when_error_repeats(self) -> None:
        attempts = [
            {**_attempt(1), "observed_failure_type": "simulate_error"},
            {**_attempt(2), "observed_failure_type": "simulate_error"},
            {**_attempt(3, check_ok=True, sim_ok=True), "observed_failure_type": "simulate_error"},
        ]
        rec = attribute_decision(_run_result("t", "x", attempts))
        self.assertEqual(rec["wasted_rounds"], 2)

    def test_empty_attempts_zero_wasted(self) -> None:
        rec = attribute_decision(_run_result("t", "x", []))
        self.assertEqual(rec["wasted_rounds"], 0)


class TestDiagnosticProgression(unittest.TestCase):
    def test_progression_has_round_and_type(self) -> None:
        attempts = [
            {**_attempt(1), "observed_failure_type": "model_check_error"},
            {**_attempt(2, check_ok=True, sim_ok=True), "observed_failure_type": ""},
        ]
        rec = attribute_decision(_run_result("t", "x", attempts))
        prog = rec["diagnostic_progression"]
        self.assertEqual(len(prog), 2)
        self.assertEqual(prog[0], [1, "model_check_error"])
        self.assertEqual(prog[1], [2, ""])

    def test_empty_attempts_empty_progression(self) -> None:
        rec = attribute_decision(_run_result("t", "x", []))
        self.assertEqual(rec["diagnostic_progression"], [])

    def test_physics_contract_in_decisive(self) -> None:
        attempt = _attempt(1, check_ok=True, sim_ok=True)
        attempt["physics_contract_pass"] = True
        rec = attribute_decision(_run_result("t", "x", [attempt]))
        self.assertTrue(rec["physics_contract_in_decisive"])

    def test_physics_contract_none_when_no_decisive(self) -> None:
        rec = attribute_decision(_run_result("t", "x", [_attempt(1, check_ok=False)]))
        self.assertIsNone(rec["physics_contract_in_decisive"])


class TestSummaryByFailureType(unittest.TestCase):
    def test_causal_path_by_failure_type(self) -> None:
        records = [
            attribute_decision(_run_result(
                "t1", "simulate_error",
                [_attempt(1, check_ok=True, sim_ok=True, first_plan_branch_match=True)]
            )),
            attribute_decision(_run_result(
                "t2", "simulate_error",
                [_attempt(1, check_ok=False), _attempt(2, check_ok=True, sim_ok=True)]
            )),
            attribute_decision(_run_result(
                "t3", "model_check_error",
                [_attempt(1, check_ok=False)]
            )),
        ]
        summary = summarize_decision_attribution(records)
        by_ft = summary["causal_path_by_failure_type"]
        self.assertIn("simulate_error", by_ft)
        self.assertIn("model_check_error", by_ft)
        self.assertEqual(by_ft["simulate_error"].get("direct", 0), 1)
        self.assertEqual(by_ft["simulate_error"].get("exhaustive", 0), 1)
        self.assertEqual(by_ft["model_check_error"].get("failed", 0), 1)

    def test_median_wasted_rounds_in_summary(self) -> None:
        attempts_with_waste = [
            {**_attempt(1), "observed_failure_type": "simulate_error"},
            {**_attempt(2), "observed_failure_type": "simulate_error"},  # wasted: same as round 1
            {**_attempt(3, check_ok=True, sim_ok=True), "observed_failure_type": ""},
        ]
        records = [
            attribute_decision(_run_result("t1", "x", attempts_with_waste)),
            attribute_decision(_run_result("t2", "x", [_attempt(1, check_ok=True, sim_ok=True)])),
        ]
        summary = summarize_decision_attribution(records)
        # t1 has 1 wasted (round 2 repeats round 1; round 3 changes to ""), t2 has 0 → median = 0.5
        self.assertAlmostEqual(summary["median_wasted_rounds"], 0.5)


if __name__ == "__main__":
    unittest.main()
