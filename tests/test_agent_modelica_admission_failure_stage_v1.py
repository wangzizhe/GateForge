from __future__ import annotations

import unittest

from gateforge.agent_modelica_admission_failure_stage_v1 import (
    classify_admission_failure_stage,
    count_admission_failure_stages,
)


class AgentModelicaAdmissionFailureStageV1Tests(unittest.TestCase):
    def test_classifies_coarse_run_stage(self) -> None:
        self.assertEqual(
            classify_admission_failure_stage(
                check_ok=False,
                simulate_ok=False,
                output="Too few equations, under-determined system.",
            ),
            "model_check",
        )
        self.assertEqual(
            classify_admission_failure_stage(
                check_ok=True,
                simulate_ok=False,
                output="simulate failed",
            ),
            "simulate",
        )
        self.assertEqual(
            classify_admission_failure_stage(
                check_ok=True,
                simulate_ok=True,
                output="ok",
            ),
            "already_pass",
        )
        self.assertEqual(
            classify_admission_failure_stage(
                check_ok=False,
                simulate_ok=False,
                output="permission denied while trying to connect to the docker API",
            ),
            "environment_blocked",
        )

    def test_counts_stages(self) -> None:
        self.assertEqual(
            count_admission_failure_stages(
                [
                    {"admission_failure_stage": "model_check"},
                    {"admission_failure_stage": "simulate"},
                    {"admission_failure_stage": "simulate"},
                    {},
                ]
            ),
            {"model_check": 1, "simulate": 2, "unknown": 1},
        )


if __name__ == "__main__":
    unittest.main()
