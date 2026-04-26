from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from gateforge.agent_modelica_provider_role_overrides_v0_27_12 import (
    build_provider_role_overrides,
    run_provider_role_overrides,
)


class ProviderRoleOverridesV02712Tests(unittest.TestCase):
    def test_build_overrides_blocks_failed_capability_for_current_harness(self) -> None:
        overrides, summary = build_provider_role_overrides(
            role_rows=[
                {"family": "base", "role": "capability_baseline_candidate"},
                {"family": "hard", "role": "hard_negative"},
            ],
            capability_audit_summary={
                "provider": "deepseek",
                "model_profile": "deepseek-v4-flash",
                "run_mode": "raw_only",
                "decision": "demote_capability_baseline_for_current_deepseek_harness",
            },
        )
        by_family = {row["family"]: row for row in overrides}
        self.assertEqual(by_family["base"]["effective_role"], "current_harness_blocked")
        self.assertEqual(by_family["hard"]["effective_role"], "hard_negative")
        self.assertEqual(summary["decision"], "no_current_deepseek_capability_baseline_available")
        self.assertEqual(summary["remaining_capability_baseline_candidate_count"], 0)

    def test_run_overrides_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roles = root / "roles.jsonl"
            audit = root / "audit.json"
            roles.write_text(json.dumps({"family": "base", "role": "capability_baseline_candidate"}) + "\n", encoding="utf-8")
            audit.write_text(
                json.dumps(
                    {
                        "provider": "deepseek",
                        "model_profile": "deepseek-v4-flash",
                        "run_mode": "raw_only",
                        "decision": "demote_capability_baseline_for_current_deepseek_harness",
                    }
                ),
                encoding="utf-8",
            )
            summary = run_provider_role_overrides(
                role_registry_path=roles,
                capability_audit_path=audit,
                out_dir=root / "out",
            )
            self.assertEqual(summary["status"], "PASS")
            self.assertTrue((root / "out" / "summary.json").exists())
            self.assertTrue((root / "out" / "provider_role_overrides.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
