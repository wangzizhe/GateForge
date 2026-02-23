#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_policy_advisor_bundle_demo
rm -f artifacts/governance_policy_advisor_bundle_demo/*.json artifacts/governance_policy_advisor_bundle_demo/*.md

bash scripts/demo_governance_replay_bundle.sh >/dev/null

cat > artifacts/governance_policy_advisor_bundle_demo/previous_snapshot.json <<'JSON'
{
  "status": "PASS",
  "kpis": {
    "latest_mismatch_count": 0,
    "history_mismatch_total": 1,
    "risk_score": 10,
    "compare_profile_count": 1
  },
  "risks": []
}
JSON

set +e
python3 -m gateforge.governance_replay_snapshot \
  --replay-ledger artifacts/governance_replay_history_demo/history.jsonl \
  --replay-history-summary artifacts/governance_replay_history_demo/summary.json \
  --replay-risk-summary artifacts/governance_replay_bundle_demo/replay_risk.json \
  --replay-compare-summary artifacts/governance_replay_bundle_demo/replay_compare.json \
  --out artifacts/governance_policy_advisor_bundle_demo/replay_snapshot.json \
  --report artifacts/governance_policy_advisor_bundle_demo/replay_snapshot.md
SNAPSHOT_RC=$?

python3 -m gateforge.governance_replay_snapshot_trend \
  --summary artifacts/governance_policy_advisor_bundle_demo/replay_snapshot.json \
  --previous-summary artifacts/governance_policy_advisor_bundle_demo/previous_snapshot.json \
  --out artifacts/governance_policy_advisor_bundle_demo/replay_snapshot_trend.json \
  --report artifacts/governance_policy_advisor_bundle_demo/replay_snapshot_trend.md
TREND_RC=$?
set -e

if [[ "$SNAPSHOT_RC" -ne 0 && "$SNAPSHOT_RC" -ne 1 ]]; then
  echo "unexpected replay snapshot exit code: $SNAPSHOT_RC" >&2
  exit 1
fi
if [[ "$TREND_RC" -ne 0 && "$TREND_RC" -ne 1 ]]; then
  echo "unexpected replay snapshot trend exit code: $TREND_RC" >&2
  exit 1
fi

python3 -m gateforge.governance_policy_advisor \
  --snapshot artifacts/governance_policy_advisor_bundle_demo/replay_snapshot.json \
  --trend artifacts/governance_policy_advisor_bundle_demo/replay_snapshot_trend.json \
  --out artifacts/governance_policy_advisor_bundle_demo/policy_advice.json \
  --report artifacts/governance_policy_advisor_bundle_demo/policy_advice.md

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/governance_policy_advisor_bundle_demo")
snapshot = json.loads((root / "replay_snapshot.json").read_text(encoding="utf-8"))
trend = json.loads((root / "replay_snapshot_trend.json").read_text(encoding="utf-8"))
advice = json.loads((root / "policy_advice.json").read_text(encoding="utf-8"))
advice_payload = advice.get("advice", {})

flags = {
    "snapshot_status_present": "PASS" if snapshot.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "trend_status_transition_present": "PASS" if isinstance((trend.get("trend") or {}).get("status_transition"), str) else "FAIL",
    "advice_profile_present": "PASS" if isinstance(advice_payload.get("suggested_policy_profile"), str) else "FAIL",
    "advice_confidence_present": "PASS" if isinstance(advice_payload.get("confidence"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "snapshot_status": snapshot.get("status"),
    "trend_status_transition": (trend.get("trend") or {}).get("status_transition"),
    "suggested_policy_profile": advice_payload.get("suggested_policy_profile"),
    "advice_confidence": advice_payload.get("confidence"),
    "advice_reasons_count": len(advice_payload.get("reasons") or []),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(root / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Policy Advisor Bundle Demo",
            "",
            f"- snapshot_status: `{summary['snapshot_status']}`",
            f"- trend_status_transition: `{summary['trend_status_transition']}`",
            f"- suggested_policy_profile: `{summary['suggested_policy_profile']}`",
            f"- advice_confidence: `{summary['advice_confidence']}`",
            f"- advice_reasons_count: `{summary['advice_reasons_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- snapshot_status_present: `{flags['snapshot_status_present']}`",
            f"- trend_status_transition_present: `{flags['trend_status_transition_present']}`",
            f"- advice_profile_present: `{flags['advice_profile_present']}`",
            f"- advice_confidence_present: `{flags['advice_confidence_present']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/governance_policy_advisor_bundle_demo/summary.json
cat artifacts/governance_policy_advisor_bundle_demo/summary.md
