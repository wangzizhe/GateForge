from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class RunAgentModelicaFoundationAcceptanceV0ScriptTests(unittest.TestCase):
    def _write_json(self, path: Path, payload: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def test_run_script_writes_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            spec = root / "spec.json"
            layer_summary = root / "layer_summary.json"
            run_results = root / "run_results.json"
            sidecar = root / "sidecar.json"
            regen = root / "regen.json"
            out = root / "out" / "summary.json"

            self._write_json(
                run_results,
                {
                    "records": [
                        {
                            "task_id": "demo",
                            "passed": True,
                            "dominant_stage_subtype": "stage_3_behavioral_contract_semantic",
                            "resolution_path": "deterministic_rule_only",
                            "planner_invoked": False,
                        }
                    ]
                },
            )
            self._write_json(
                layer_summary,
                {"coverage_gap": {"aggregate_layer_counts": {"layer_1": 2, "layer_4": 0}}},
            )
            self._write_json(sidecar, {"annotations": []})
            self._write_json(regen, {"ok": True})
            self._write_json(
                spec,
                {
                    "layer_summary": str(layer_summary),
                    "required_regeneration_paths": [str(regen)],
                    "lanes": [
                        {
                            "lane_id": "demo_lane",
                            "run_results": str(run_results),
                            "sidecar": str(sidecar),
                            "planner_expected": False,
                        }
                    ],
                    "thresholds": {
                        "min_stage_subtype_coverage_pct": 95.0,
                        "max_unresolved_success_count": 0,
                        "max_layer4_share_pct": 10.0,
                    },
                },
            )

            env = dict(os.environ)
            env["GATEFORGE_AGENT_FOUNDATION_ACCEPTANCE_SPEC"] = str(spec)
            env["GATEFORGE_AGENT_FOUNDATION_ACCEPTANCE_OUT"] = str(out)
            result = subprocess.run(
                ["bash", "scripts/run_agent_modelica_foundation_acceptance_v0.sh"],
                cwd=str(REPO_ROOT),
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["lane_count"], 1)


if __name__ == "__main__":
    unittest.main()
