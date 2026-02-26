import unittest
from pathlib import Path


class DatasetDemoChainFastContractTests(unittest.TestCase):
    def test_chain_scripts_use_fast_aware_dependency_wrapper(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        scripts = [
            "scripts/demo_dataset_history.sh",
            "scripts/demo_dataset_governance.sh",
            "scripts/demo_dataset_policy_lifecycle.sh",
            "scripts/demo_dataset_governance_history.sh",
            "scripts/demo_dataset_strategy_autotune.sh",
            "scripts/demo_dataset_strategy_autotune_apply.sh",
            "scripts/demo_dataset_strategy_autotune_apply_history.sh",
            "scripts/demo_dataset_promotion_candidate.sh",
            "scripts/demo_dataset_promotion_candidate_apply.sh",
            "scripts/demo_dataset_promotion_candidate_history.sh",
            "scripts/demo_dataset_promotion_candidate_apply_history.sh",
            "scripts/demo_dataset_promotion_effectiveness.sh",
            "scripts/demo_dataset_promotion_effectiveness_history.sh",
            "scripts/demo_dataset_governance_snapshot_trend.sh",
        ]

        missing_wrapper = []
        direct_chain_calls = []
        for rel_path in scripts:
            content = (repo_root / rel_path).read_text(encoding="utf-8")
            if "run_dep_script()" not in content:
                missing_wrapper.append(rel_path)
            if "bash scripts/demo_dataset_" in content:
                direct_chain_calls.append(rel_path)

        self.assertFalse(
            missing_wrapper,
            msg="chain demo scripts must define run_dep_script wrapper: " + ", ".join(missing_wrapper),
        )
        self.assertFalse(
            direct_chain_calls,
            msg=(
                "chain demo scripts must avoid direct nested dataset demo calls; "
                "use run_dep_script for FAST-aware reuse: " + ", ".join(direct_chain_calls)
            ),
        )


if __name__ == "__main__":
    unittest.main()
