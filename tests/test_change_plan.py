import unittest

from gateforge.change_plan import materialize_change_set_from_plan, validate_change_plan


class ChangePlanTests(unittest.TestCase):
    def test_validate_change_plan_pass(self) -> None:
        payload = {
            "schema_version": "0.1.0",
            "operations": [
                {
                    "kind": "replace_text",
                    "file": "examples/openmodelica/MinimalProbe.mo",
                    "old": "der(x) = -x;",
                    "new": "der(x) = -2*x;",
                    "reason": "improve damping",
                    "confidence": 0.9,
                }
            ],
        }
        validate_change_plan(payload)

    def test_materialize_change_set_from_plan(self) -> None:
        plan = {
            "schema_version": "0.1.0",
            "operations": [
                {
                    "kind": "replace_text",
                    "file": "examples/openmodelica/MinimalProbe.mo",
                    "old": "der(x) = -x;",
                    "new": "der(x) = -2*x;",
                    "reason": "improve damping",
                    "confidence": 0.9,
                }
            ],
        }
        change_set = materialize_change_set_from_plan(plan)
        self.assertEqual(change_set["schema_version"], "0.1.0")
        self.assertEqual(change_set["changes"][0]["op"], "replace_text")
        self.assertEqual(change_set["metadata"]["plan_confidence_min"], 0.9)


if __name__ == "__main__":
    unittest.main()
