import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_l4_canonical_baseline_v0 import evaluate_l4_canonical_baseline_v0


def _write_candidate(
    root: Path,
    name: str,
    *,
    success_pct: float,
    in_range: bool,
    max_rounds: int,
    max_time_sec: int,
    planner_backend: str = "gemini",
    llm_model: str = "gemini-3.1-pro-preview",
    taskset_in: str = "assets_private/agent_modelica_l4_challenge_pack_v0/taskset_frozen.json",
    git_commit: str = "abc1234",
    baseline_rc: int = 0,
    include_results: bool = True,
) -> str:
    out = root / name
    out.mkdir(parents=True, exist_ok=True)
    provenance = {
        "taskset_in": taskset_in,
        "baseline_run_summary_path": str(out / "baseline_off_run_summary.json"),
        "baseline_run_results_path": str(out / "baseline_off_run_results.json"),
        "planner_backend": planner_backend,
        "llm_model": llm_model,
        "backend": "mock",
        "docker_image": "mock",
        "live_executor_cmd": "python3 -m gateforge.agent_modelica_live_executor_mock_v0",
        "live_executor_cmd_sha256": "deadbeef",
        "live_timeout_sec": 20,
        "live_max_output_chars": 1600,
        "max_rounds": max_rounds,
        "max_time_sec": max_time_sec,
        "runtime_threshold": 0.2,
        "git_commit": git_commit,
    }
    frozen_summary = {
        "schema_version": "agent_modelica_l4_challenge_pack_v0",
        "status": "PASS" if in_range else "FAIL",
        "baseline_off_success_at_k_pct": success_pct,
        "baseline_in_target_range": in_range,
        "baseline_off_run_exit_code": baseline_rc,
        "baseline_summary_refresh_exit_code": 0 if in_range else 1,
        "reasons": [] if in_range else ["baseline_off_success_out_of_target_range"],
        "baseline_provenance": provenance,
    }
    manifest = {
        "schema_version": "agent_modelica_l4_challenge_pack_v0",
        "taskset_in": taskset_in,
        "baseline_provenance": provenance,
    }
    baseline_summary = {
        "status": "PASS" if baseline_rc == 0 else "FAIL",
        "success_count": int(round(success_pct / 100.0 * 6)),
        "total_tasks": 6,
        "success_at_k_pct": success_pct,
        "max_rounds": max_rounds,
        "max_time_sec": max_time_sec,
    }
    (out / "frozen_summary.json").write_text(json.dumps(frozen_summary, indent=2), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (out / "baseline_off_run_summary.json").write_text(json.dumps(baseline_summary, indent=2), encoding="utf-8")
    if include_results:
        (out / "baseline_off_run_results.json").write_text(json.dumps({"records": []}, indent=2), encoding="utf-8")
    return str(out)


class AgentModelicaL4CanonicalBaselineV0Tests(unittest.TestCase):
    def test_selects_smallest_stable_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dirs = [
                _write_candidate(root, "mr1_mt20", success_pct=33.33, in_range=False, max_rounds=1, max_time_sec=20),
                _write_candidate(root, "mr2_mt20", success_pct=66.67, in_range=True, max_rounds=2, max_time_sec=20),
                _write_candidate(root, "mr2_mt20_r1", success_pct=66.67, in_range=True, max_rounds=2, max_time_sec=20),
                _write_candidate(root, "mr2_mt20_r2", success_pct=66.67, in_range=True, max_rounds=2, max_time_sec=20),
            ]
            summary = evaluate_l4_canonical_baseline_v0(candidate_dirs=dirs, target_min_off_success_pct=60.0, min_uplift_delta_pp=5.0)
            self.assertEqual(str(summary.get("decision") or ""), "ready")
            self.assertEqual(str(summary.get("primary_reason") or ""), "none")
            self.assertTrue(bool(summary.get("stability_ok")))
            canonical = summary.get("canonical_budget") if isinstance(summary.get("canonical_budget"), dict) else {}
            self.assertEqual(str(canonical.get("budget_token") or ""), "2x20")

    def test_holds_when_canonical_budget_has_no_headroom(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dirs = [
                _write_candidate(root, "mr1_mt20", success_pct=33.33, in_range=False, max_rounds=1, max_time_sec=20),
                _write_candidate(root, "mr2_mt20", success_pct=100.0, in_range=False, max_rounds=2, max_time_sec=20),
                _write_candidate(root, "mr2_mt20_r1", success_pct=100.0, in_range=False, max_rounds=2, max_time_sec=20),
                _write_candidate(root, "mr2_mt20_r2", success_pct=100.0, in_range=False, max_rounds=2, max_time_sec=20),
            ]
            for path in dirs[1:]:
                frozen = json.loads((Path(path) / "frozen_summary.json").read_text(encoding="utf-8"))
                frozen["baseline_meets_minimum"] = True
                frozen["baseline_has_headroom"] = False
                frozen["baseline_eligible_for_uplift"] = False
                frozen["baseline_in_target_range"] = True
                (Path(path) / "frozen_summary.json").write_text(json.dumps(frozen, indent=2), encoding="utf-8")
            summary = evaluate_l4_canonical_baseline_v0(candidate_dirs=dirs, target_min_off_success_pct=60.0, min_uplift_delta_pp=5.0)
            self.assertEqual(str(summary.get("decision") or ""), "hold")
            self.assertEqual(str(summary.get("primary_reason") or ""), "baseline_saturated_no_headroom")
            canonical = summary.get("canonical_budget") if isinstance(summary.get("canonical_budget"), dict) else {}
            self.assertEqual(str(canonical.get("budget_token") or ""), "2x20")

    def test_holds_when_candidate_is_unstable(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            dirs = [
                _write_candidate(root, "mr2_mt20", success_pct=70.0, in_range=True, max_rounds=2, max_time_sec=20),
                _write_candidate(root, "mr2_mt20_r1", success_pct=95.0, in_range=False, max_rounds=2, max_time_sec=20),
                _write_candidate(root, "mr2_mt20_r2", success_pct=70.0, in_range=True, max_rounds=2, max_time_sec=20),
            ]
            high = json.loads((root / "mr2_mt20_r1" / "frozen_summary.json").read_text(encoding="utf-8"))
            high["baseline_meets_minimum"] = True
            high["baseline_has_headroom"] = True
            high["baseline_eligible_for_uplift"] = True
            high["baseline_in_target_range"] = True
            (root / "mr2_mt20_r1" / "frozen_summary.json").write_text(json.dumps(high, indent=2), encoding="utf-8")
            summary = evaluate_l4_canonical_baseline_v0(candidate_dirs=dirs, target_min_off_success_pct=60.0, min_uplift_delta_pp=5.0)
            self.assertEqual(str(summary.get("decision") or ""), "hold")
            self.assertEqual(str(summary.get("primary_reason") or ""), "candidate_unstable")
            self.assertFalse(bool(summary.get("stability_ok")))


if __name__ == "__main__":
    unittest.main()
