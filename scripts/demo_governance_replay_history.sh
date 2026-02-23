#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_replay_history_demo
rm -f artifacts/governance_replay_history_demo/*.json artifacts/governance_replay_history_demo/*.md artifacts/governance_replay_history_demo/*.jsonl

bash scripts/demo_governance_replay.sh >/dev/null

python3 - <<'PY'
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path("artifacts/governance_replay_history_demo")
src = Path("artifacts/governance_replay_demo")
base = datetime(2026, 2, 23, 10, 0, 0, tzinfo=timezone.utc)

rows = []
mapping = [
    ("replay_pass.json", 0),
    ("replay_needs_review.json", 5),
    ("replay_strict_fail.json", 10),
]
for filename, minutes in mapping:
    payload = json.loads((src / filename).read_text(encoding="utf-8"))
    payload["recorded_at_utc"] = (base + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")
    rows.append(payload)

(root / "history.jsonl").write_text(
    "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n",
    encoding="utf-8",
)
PY

python3 -m gateforge.governance_replay_history \
  --ledger artifacts/governance_replay_history_demo/history.jsonl \
  --last-n 3 \
  --mismatch-threshold 1 \
  --non-pass-streak-threshold 2 \
  --out artifacts/governance_replay_history_demo/summary.json \
  --report artifacts/governance_replay_history_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/governance_replay_history_demo/summary.json").read_text(encoding="utf-8"))
flags = {
    "latest_expected_fail": "PASS" if payload.get("latest_decision") == "FAIL" else "FAIL",
    "mismatch_alert_expected": "PASS" if "mismatch_volume_high" in (payload.get("alerts") or []) else "FAIL",
    "streak_alert_expected": "PASS" if "replay_non_pass_streak_detected" in (payload.get("alerts") or []) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "latest_decision": payload.get("latest_decision"),
    "mismatch_total": payload.get("mismatch_total"),
    "alerts": payload.get("alerts", []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
Path("artifacts/governance_replay_history_demo/demo_summary.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
Path("artifacts/governance_replay_history_demo/demo_summary.md").write_text(
    "\n".join(
        [
            "# Governance Replay History Demo",
            "",
            f"- latest_decision: `{summary.get('latest_decision')}`",
            f"- mismatch_total: `{summary.get('mismatch_total')}`",
            f"- alerts: `{','.join(summary.get('alerts') or []) or 'none'}`",
            f"- bundle_status: `{summary.get('bundle_status')}`",
            "",
            "## Result Flags",
            "",
            f"- latest_expected_fail: `{flags['latest_expected_fail']}`",
            f"- mismatch_alert_expected: `{flags['mismatch_alert_expected']}`",
            f"- streak_alert_expected: `{flags['streak_alert_expected']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/governance_replay_history_demo/demo_summary.json
cat artifacts/governance_replay_history_demo/demo_summary.md
