import tempfile
import unittest
from pathlib import Path

from gateforge.change_apply import apply_change_set, load_change_set


class ChangeApplyTests(unittest.TestCase):
    def test_load_change_set(self) -> None:
        payload = load_change_set("examples/changesets/minimalprobe_x_to_2.json")
        self.assertEqual(payload["schema_version"], "0.1.0")
        self.assertEqual(payload["changes"][0]["op"], "replace_text")

    def test_apply_change_set_success(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = Path("examples")
            dst = root / "examples"
            # Keep fixture layout identical to proposal file paths.
            import shutil

            shutil.copytree(src, dst)
            result = apply_change_set(
                path="examples/changesets/minimalprobe_x_to_2.json",
                workspace_root=root,
            )
            self.assertTrue(result["change_set_hash"])
            self.assertEqual(len(result["applied_changes"]), 1)
            patched = (root / "examples/openmodelica/MinimalProbe.mo").read_text(encoding="utf-8")
            self.assertIn("der(x) = -2*x;", patched)

    def test_apply_change_set_fails_when_old_text_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = Path("examples")
            dst = root / "examples"
            import shutil

            shutil.copytree(src, dst)
            with self.assertRaises(ValueError):
                apply_change_set(
                    path="examples/changesets/minimalprobe_bad_old_text.json",
                    workspace_root=root,
                )


if __name__ == "__main__":
    unittest.main()
