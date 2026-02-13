import unittest

from gateforge.intent import validate_intent_request


class IntentTests(unittest.TestCase):
    def test_validate_intent_request_pass(self) -> None:
        payload = {
            "intent": "demo_mock_pass",
            "proposal_id": "intent-1",
            "overrides": {"risk_level": "low"},
            "change_plan": {
                "schema_version": "0.1.0",
                "operations": [
                {
                    "kind": "replace_text",
                    "file": "examples/openmodelica/MinimalProbe.mo",
                    "old": "der(x) = -x;",
                    "new": "der(x) = -2*x;",
                    "reason": "improve damping",
                    "confidence": 0.8,
                }
            ],
        },
        }
        validate_intent_request(payload)

    def test_validate_intent_request_fails_on_unknown_intent(self) -> None:
        with self.assertRaises(ValueError):
            validate_intent_request({"intent": "unknown"})


if __name__ == "__main__":
    unittest.main()
