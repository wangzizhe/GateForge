#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_replay_bundle_demo
rm -f artifacts/governance_replay_bundle_demo/*.json artifacts/governance_replay_bundle_demo/*.md

bash scripts/demo_governance_replay.sh >/dev/null
bash scripts/demo_governance_replay_history.sh >/dev/null

python3 -m gateforge.governance_replay_compare \
  --compare-summary artifacts/governance_replay_demo/compare_source.json \
  --profiles default industrial_strict \
  --out artifacts/governance_replay_bundle_demo/replay_compare.json \
  --report artifacts/governance_replay_bundle_demo/replay_compare.md

python3 -m gateforge.governance_replay_query \
  --ledger artifacts/governance_replay_history_demo/history.jsonl \
  --mismatch-code apply_policy_hash_mismatch \
  --out artifacts/governance_replay_bundle_demo/replay_query.json \
  --report artifacts/governance_replay_bundle_demo/replay_query.md \
  --export-out artifacts/governance_replay_bundle_demo/replay_query_rows.json

python3 -m gateforge.governance_replay_risk \
  --ledger artifacts/governance_replay_history_demo/history.jsonl \
  --out artifacts/governance_replay_bundle_demo/replay_risk.json \
  --report artifacts/governance_replay_bundle_demo/replay_risk.md

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/governance_replay_bundle_demo")
replay = json.loads(Path("artifacts/governance_replay_demo/summary.json").read_text(encoding="utf-8"))
history = json.loads(Path("artifacts/governance_replay_history_demo/demo_summary.json").read_text(encoding="utf-8"))
compare = json.loads((root / "replay_compare.json").read_text(encoding="utf-8"))
query = json.loads((root / "replay_query.json").read_text(encoding="utf-8"))
risk = json.loads((root / "replay_risk.json").read_text(encoding="utf-8"))

flags = {
    "replay_expected_pass": "PASS" if replay.get("bundle_status") == "PASS" else "FAIL",
    "history_expected_pass": "PASS" if history.get("bundle_status") == "PASS" else "FAIL",
    "compare_has_best_profile": "PASS" if isinstance(compare.get("best_profile"), str) else "FAIL",
    "query_has_rows": "PASS" if int(query.get("total_rows", 0)) >= 1 else "FAIL",
    "risk_level_present": "PASS" if isinstance(risk.get("risk", {}).get("level"), str) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "replay_bundle_status": replay.get("bundle_status"),
    "history_bundle_status": history.get("bundle_status"),
    "compare_status": compare.get("status"),
    "compare_best_profile": compare.get("best_profile"),
    "query_total_rows": query.get("total_rows"),
    "risk_score": risk.get("risk", {}).get("score"),
    "risk_level": risk.get("risk", {}).get("level"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}

(root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(root / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Replay Bundle Demo",
            "",
            f"- replay_bundle_status: `{summary['replay_bundle_status']}`",
            f"- history_bundle_status: `{summary['history_bundle_status']}`",
            f"- compare_status: `{summary['compare_status']}`",
            f"- compare_best_profile: `{summary['compare_best_profile']}`",
            f"- query_total_rows: `{summary['query_total_rows']}`",
            f"- risk_score: `{summary['risk_score']}`",
            f"- risk_level: `{summary['risk_level']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- replay_expected_pass: `{flags['replay_expected_pass']}`",
            f"- history_expected_pass: `{flags['history_expected_pass']}`",
            f"- compare_has_best_profile: `{flags['compare_has_best_profile']}`",
            f"- query_has_rows: `{flags['query_has_rows']}`",
            f"- risk_level_present: `{flags['risk_level_present']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat artifacts/governance_replay_bundle_demo/summary.json
cat artifacts/governance_replay_bundle_demo/summary.md
