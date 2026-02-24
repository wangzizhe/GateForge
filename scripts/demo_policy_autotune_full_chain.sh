#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/policy_autotune_full_chain_demo"
mkdir -p "$OUT_DIR"

bash scripts/demo_policy_autotune.sh >/dev/null
bash scripts/demo_policy_autotune_history.sh >/dev/null
bash scripts/demo_policy_autotune_governance.sh >/dev/null
bash scripts/demo_policy_autotune_governance_dashboard.sh >/dev/null
bash scripts/demo_policy_autotune_governance_advisor.sh >/dev/null
bash scripts/demo_policy_autotune_governance_advisor_history.sh >/dev/null
bash scripts/demo_governance_snapshot_with_advisor_history.sh >/dev/null

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/policy_autotune_full_chain_demo")

autotune = json.loads(Path("artifacts/policy_autotune_demo/summary.json").read_text(encoding="utf-8"))
history = json.loads(Path("artifacts/policy_autotune_history_demo/demo_summary.json").read_text(encoding="utf-8"))
governance = json.loads(Path("artifacts/policy_autotune_governance_demo/summary.json").read_text(encoding="utf-8"))
advisor = json.loads(Path("artifacts/policy_autotune_governance_advisor_demo/summary.json").read_text(encoding="utf-8"))
advisor_history = json.loads(
    Path("artifacts/policy_autotune_governance_advisor_history_demo/demo_summary.json").read_text(encoding="utf-8")
)
snapshot = json.loads(
    Path("artifacts/governance_snapshot_advisor_history_demo/demo_summary.json").read_text(encoding="utf-8")
)

flags = {
    "autotune_bundle_pass": "PASS" if autotune.get("bundle_status") == "PASS" else "FAIL",
    "history_bundle_pass": "PASS" if history.get("bundle_status") == "PASS" else "FAIL",
    "governance_bundle_pass": "PASS" if governance.get("bundle_status") == "PASS" else "FAIL",
    "advisor_bundle_pass": "PASS" if advisor.get("bundle_status") == "PASS" else "FAIL",
    "advisor_history_bundle_pass": "PASS" if advisor_history.get("bundle_status") == "PASS" else "FAIL",
    "snapshot_bundle_pass": "PASS" if snapshot.get("bundle_status") == "PASS" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "bundle_status": bundle_status,
    "autotune_decision": autotune.get("decision"),
    "autotune_suggested_profile": autotune.get("suggested_profile"),
    "advisor_action": advisor.get("advisor_action"),
    "advisor_suggested_profile": advisor.get("advisor_profile"),
    "advisor_history_trend_status": advisor_history.get("trend_status"),
    "snapshot_status": snapshot.get("status"),
    "snapshot_advisor_trend_status": snapshot.get("advisor_trend_status"),
    "result_flags": flags,
}

(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Policy Auto-Tune Full Chain Demo",
            "",
            f"- bundle_status: `{summary['bundle_status']}`",
            f"- autotune_decision: `{summary['autotune_decision']}`",
            f"- autotune_suggested_profile: `{summary['autotune_suggested_profile']}`",
            f"- advisor_action: `{summary['advisor_action']}`",
            f"- advisor_suggested_profile: `{summary['advisor_suggested_profile']}`",
            f"- advisor_history_trend_status: `{summary['advisor_history_trend_status']}`",
            f"- snapshot_status: `{summary['snapshot_status']}`",
            f"- snapshot_advisor_trend_status: `{summary['snapshot_advisor_trend_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "advisor_action": summary["advisor_action"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
