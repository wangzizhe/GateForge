#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/planner_output_validate_demo"
mkdir -p "$OUT_DIR"

cat > "$OUT_DIR/planner_output_pass.json" <<'EOF'
{
  "intent": "demo_mock_pass",
  "proposal_id": "planner-output-pass-001",
  "overrides": {
    "risk_level": "low",
    "change_summary": "planner output validation pass case"
  }
}
EOF

cat > "$OUT_DIR/planner_output_fail.json" <<'EOF'
{
  "intent": "demo_mock_pass",
  "overrides": {
    "unsafe_key": true
  },
  "extra_top_level": "not-allowed"
}
EOF

python3 -m gateforge.planner_output_validate --in "$OUT_DIR/planner_output_pass.json" > "$OUT_DIR/pass_result.json"
set +e
python3 -m gateforge.planner_output_validate --in "$OUT_DIR/planner_output_fail.json" > "$OUT_DIR/fail_result.json"
FAIL_EXIT=$?
set -e

FAIL_EXIT="$FAIL_EXIT" python3 - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path("artifacts/planner_output_validate_demo")
pass_result = json.loads((out_dir / "pass_result.json").read_text(encoding="utf-8"))
fail_result = json.loads((out_dir / "fail_result.json").read_text(encoding="utf-8"))

summary = {
    "pass_case_status": pass_result.get("status"),
    "fail_case_status": fail_result.get("status"),
    "fail_case_exit_code": int(os.environ.get("FAIL_EXIT", "1")),
    "bundle_status": "PASS",
}
summary["result_flags"] = {
    "pass_case_expected_pass": "PASS" if summary["pass_case_status"] == "PASS" else "FAIL",
    "fail_case_expected_fail": "PASS" if summary["fail_case_status"] == "FAIL" else "FAIL",
}
summary["bundle_status"] = "PASS" if all(v == "PASS" for v in summary["result_flags"].values()) else "FAIL"

(out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out_dir / "summary.md").write_text(
    "\n".join(
        [
            "# Planner Output Validate Demo",
            "",
            f"- pass_case_status: `{summary['pass_case_status']}`",
            f"- fail_case_status: `{summary['fail_case_status']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- pass_case_expected_pass: `{summary['result_flags']['pass_case_expected_pass']}`",
            f"- fail_case_expected_fail: `{summary['result_flags']['fail_case_expected_fail']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": summary["bundle_status"]}))
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(Path("artifacts/planner_output_validate_demo/summary.json").read_text(encoding="utf-8"))
if summary.get("bundle_status") != "PASS":
    raise SystemExit(1)
PY
