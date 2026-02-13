import unittest

from gateforge.demo_bundle import validate_demo_bundle_summary


def _valid_payload() -> dict:
    return {
        "flow_exit_code": 0,
        "checker_exit_code": 0,
        "proposal_flow_status": "PASS",
        "checker_demo_status": "FAIL",
        "checker_demo_policy_decision": "FAIL",
        "result_flags": {
            "proposal_flow": "PASS",
            "checker_demo_expected_fail": "PASS",
        },
        "artifacts": [
            "artifacts/proposal_run_demo.json",
            "artifacts/checker_demo_summary.md",
        ],
        "bundle_status": "PASS",
    }


class DemoBundleTests(unittest.TestCase):
    def test_validate_demo_bundle_summary_pass(self) -> None:
        payload = _valid_payload()
        validate_demo_bundle_summary(payload)

    def test_validate_demo_bundle_summary_missing_key(self) -> None:
        payload = _valid_payload()
        payload.pop("bundle_status")
        with self.assertRaises(ValueError):
            validate_demo_bundle_summary(payload)

    def test_validate_demo_bundle_summary_bad_flag(self) -> None:
        payload = _valid_payload()
        payload["result_flags"]["proposal_flow"] = "MAYBE"
        with self.assertRaises(ValueError):
            validate_demo_bundle_summary(payload)


if __name__ == "__main__":
    unittest.main()
