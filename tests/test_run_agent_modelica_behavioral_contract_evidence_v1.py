import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class RunAgentModelicaBehavioralContractEvidenceV1Tests(unittest.TestCase):
    def test_mock_chain_produces_behavioral_decision(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script = repo_root / "scripts" / "run_agent_modelica_behavioral_contract_evidence_v1.sh"
        manifest = repo_root / "assets_private" / "agent_modelica_behavioral_contract_pack_v1" / "manifest.json"
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "out"
            proc = subprocess.run(
                ["bash", str(script)],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
                env={
                    **os.environ,
                    "GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_MANIFEST": str(manifest),
                    "GATEFORGE_AGENT_BEHAVIORAL_CONTRACT_EVIDENCE_OUT_DIR": str(out_dir),
                },
                timeout=900,
            )
            self.assertEqual(proc.returncode, 0, msg=proc.stderr or proc.stdout)
            decision = json.loads((out_dir / "decision_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(decision.get("primary_reason"), "retrieval_hold_the_floor")
            self.assertEqual(decision.get("decision"), "promote")
            self.assertTrue((out_dir / "behavioral_contract_baseline_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
