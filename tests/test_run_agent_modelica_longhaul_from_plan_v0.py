import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path


def _pass_segment_command() -> str:
    code = """
import os
from pathlib import Path
out_dir = Path(os.environ.get("GATEFORGE_AGENT_LONGHAUL_SEGMENT_OUT_DIR", "."))
out_dir.mkdir(parents=True, exist_ok=True)
(out_dir / "ok.txt").write_text("ok", encoding="utf-8")
print("segment-pass")
""".strip()
    return f"python3 -c {shlex.quote(code)}"


class RunAgentModelicaLonghaulFromPlanV0ScriptTests(unittest.TestCase):
    def test_runs_longhaul_from_markdown_plan(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_longhaul_from_plan_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_dir = root / "out"
            plan = root / "plan.md"
            payload = {
                "schema_version": "agent_modelica_longhaul_plan_v0",
                "plan_id": "test_plan",
                "longhaul": {
                    "out_dir": str(out_dir),
                    "total_minutes": 120,
                    "segment_timeout_sec": 10,
                    "max_segments": 2,
                    "retry_per_segment": 0,
                    "continue_on_fail": 0,
                    "sleep_between_sec": 0,
                    "resume": 1,
                    "cwd": ".",
                },
                "segment_command": _pass_segment_command(),
                "env": {},
            }
            plan.write_text(
                "\n".join(
                    [
                        "# test",
                        "<!-- GATEFORGE_LONGHAUL_PLAN_V0_BEGIN -->",
                        json.dumps(payload, indent=2),
                        "<!-- GATEFORGE_LONGHAUL_PLAN_V0_END -->",
                    ]
                ),
                encoding="utf-8",
            )
            proc = subprocess.run(
                ["bash", str(script), str(plan)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                env=dict(os.environ),
                check=False,
                timeout=180,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(str(summary.get("status") or ""), "PASS")
            self.assertEqual(int(summary.get("segments_total") or -1), 2)

    def test_fails_when_plan_markers_missing(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_longhaul_from_plan_v0.sh"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            bad_plan = root / "bad_plan.md"
            bad_plan.write_text("# missing markers\n", encoding="utf-8")
            proc = subprocess.run(
                ["bash", str(script), str(bad_plan)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                env=dict(os.environ),
                check=False,
                timeout=60,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Plan markers not found", proc.stderr)


if __name__ == "__main__":
    unittest.main()
