import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_multi_round_repair_audit_v0_3_4 import build_multi_round_repair_audit


class AgentModelicaMultiRoundRepairAuditV034Tests(unittest.TestCase):
    def test_build_multi_round_repair_audit_detects_deterministic_rescue(self) -> None:
        payload = {
            "task_id": "case_a",
            "failure_type": "coupled_conflict_failure",
            "executor_status": "PASS",
            "check_model_pass": True,
            "simulate_pass": True,
            "resolution_path": "deterministic_rule_only",
            "live_request_count": 0,
            "rounds_used": 2,
            "attempts": [
                {
                    "check_model_pass": False,
                    "simulate_pass": False,
                    "source_repair": {"applied": False},
                    "multi_round_layered_repair": {"applied": False},
                },
                {
                    "check_model_pass": True,
                    "simulate_pass": True,
                    "source_repair": {"applied": True},
                    "multi_round_layered_repair": {"applied": False},
                },
            ],
        }
        with tempfile.TemporaryDirectory(prefix="gf_multiround_audit_") as td:
            input_path = Path(td) / "input.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            summary = build_multi_round_repair_audit(input_path=str(input_path), out_dir=str(Path(td) / "out"))
        self.assertEqual(summary.get("recommended_action"), "promote_multi_round_deterministic_repair_validation")
        rows = summary.get("rows") if isinstance(summary.get("rows"), list) else []
        self.assertEqual(rows[0].get("classification"), "deterministic_multi_round_rescue")

    def test_build_multi_round_repair_audit_marks_unresolved_multi_round_case(self) -> None:
        payload = {
            "task_id": "case_b",
            "failure_type": "false_friend_patch_trap",
            "executor_status": "FAIL",
            "check_model_pass": False,
            "simulate_pass": False,
            "resolution_path": "unresolved",
            "rounds_used": 3,
            "attempts": [
                {"check_model_pass": False, "simulate_pass": False},
                {"check_model_pass": False, "simulate_pass": False},
            ],
        }
        with tempfile.TemporaryDirectory(prefix="gf_multiround_audit_") as td:
            input_path = Path(td) / "input.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            summary = build_multi_round_repair_audit(input_path=str(input_path), out_dir=str(Path(td) / "out"))
        rows = summary.get("rows") if isinstance(summary.get("rows"), list) else []
        self.assertEqual(rows[0].get("classification"), "still_unresolved_multi_round")

    def test_build_multi_round_repair_audit_ignores_non_multi_round_cases(self) -> None:
        payload = {
            "task_id": "case_c",
            "failure_type": "event_logic_error",
            "executor_status": "PASS",
            "check_model_pass": True,
            "simulate_pass": True,
            "resolution_path": "deterministic_rule_only",
            "rounds_used": 1,
            "attempts": [],
        }
        with tempfile.TemporaryDirectory(prefix="gf_multiround_audit_") as td:
            input_path = Path(td) / "input.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            summary = build_multi_round_repair_audit(input_path=str(input_path), out_dir=str(Path(td) / "out"))
        rows = summary.get("rows") if isinstance(summary.get("rows"), list) else []
        self.assertEqual(rows[0].get("classification"), "not_applicable")

    def test_build_multi_round_repair_audit_supports_directory_input(self) -> None:
        payload_a = {
            "task_id": "case_a",
            "failure_type": "coupled_conflict_failure",
            "executor_status": "PASS",
            "check_model_pass": True,
            "simulate_pass": True,
            "resolution_path": "deterministic_rule_only",
            "live_request_count": 0,
            "rounds_used": 2,
            "attempts": [
                {"check_model_pass": False, "simulate_pass": False},
                {"check_model_pass": True, "simulate_pass": True, "source_repair": {"applied": True}},
            ],
        }
        payload_b = {
            "task_id": "case_b",
            "failure_type": "cascading_structural_failure",
            "executor_status": "PASS",
            "check_model_pass": True,
            "simulate_pass": True,
            "resolution_path": "deterministic_rule_only",
            "live_request_count": 0,
            "rounds_used": 2,
            "attempts": [
                {"check_model_pass": True, "simulate_pass": False},
                {"check_model_pass": True, "simulate_pass": True, "source_repair": {"applied": True}},
            ],
        }
        with tempfile.TemporaryDirectory(prefix="gf_multiround_audit_dir_") as td:
            input_dir = Path(td) / "inputs"
            input_dir.mkdir(parents=True, exist_ok=True)
            (input_dir / "a.json").write_text(json.dumps(payload_a), encoding="utf-8")
            (input_dir / "b.json").write_text(json.dumps(payload_b), encoding="utf-8")
            summary = build_multi_round_repair_audit(input_path=str(input_dir), out_dir=str(Path(td) / "out"))
        metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
        self.assertEqual(summary.get("input_kind"), "directory")
        self.assertEqual(metrics.get("applicable_multi_round_rows"), 2)
        self.assertEqual(metrics.get("deterministic_multi_round_rescue_count"), 2)


if __name__ == "__main__":
    unittest.main()
