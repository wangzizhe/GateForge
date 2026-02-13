import tempfile
import unittest
from pathlib import Path

from gateforge.preflight import preflight_change_set


class PreflightTests(unittest.TestCase):
    def test_preflight_pass(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            target = root / "examples/openmodelica/MinimalProbe.mo"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("model MinimalProbe\n  Real x;\nend MinimalProbe;\n", encoding="utf-8")
            change_set = {
                "schema_version": "0.1.0",
                "changes": [
                    {
                        "op": "replace_text",
                        "file": "examples/openmodelica/MinimalProbe.mo",
                        "old": "Real x;",
                        "new": "Real x(start=1);",
                    }
                ],
            }
            result = preflight_change_set(change_set=change_set, workspace_root=root)
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "passed")

    def test_preflight_disallowed_path(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            change_set = {
                "schema_version": "0.1.0",
                "changes": [
                    {
                        "op": "replace_text",
                        "file": "examples/not_allowed/Bad.mo",
                        "old": "x",
                        "new": "y",
                    }
                ],
            }
            result = preflight_change_set(change_set=change_set, workspace_root=root)
            self.assertFalse(result["ok"])
            self.assertIn("change_preflight_disallowed_path", result["reasons"])


if __name__ == "__main__":
    unittest.main()

