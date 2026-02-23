#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_replay_demo
rm -f artifacts/governance_replay_demo/*.json artifacts/governance_replay_demo/*.md

cat > artifacts/governance_replay_demo/snapshot.json <<'JSON'
{
  "status": "PASS",
  "risks": [],
  "kpis": {
    "recommended_profile": "default",
    "strict_non_pass_rate": 0.0,
    "strict_downgrade_rate": 0.0,
    "review_recovery_rate": 1.0,
    "fail_rate": 0.0
  }
}
JSON

python3 -m gateforge.governance_promote_compare \
  --snapshot artifacts/governance_replay_demo/snapshot.json \
  --profiles default industrial_strict \
  --out artifacts/governance_replay_demo/compare_source.json

python3 -m gateforge.governance_promote_apply \
  --compare-summary artifacts/governance_replay_demo/compare_source.json \
  --policy-profile default \
  --require-ranking-explanation-structure \
  --strict-ranking-explanation-structure \
  --out artifacts/governance_replay_demo/apply_source.json

python3 -m gateforge.governance_replay \
  --compare-summary artifacts/governance_replay_demo/compare_source.json \
  --apply-summary artifacts/governance_replay_demo/apply_source.json \
  --out artifacts/governance_replay_demo/replay_pass.json

python3 - <<'PY'
import json
from pathlib import Path

src = Path("artifacts/governance_replay_demo/apply_source.json")
payload = json.loads(src.read_text(encoding="utf-8"))
payload["policy_hash"] = "deadbeef"
Path("artifacts/governance_replay_demo/apply_tampered.json").write_text(
    json.dumps(payload, indent=2), encoding="utf-8"
)
PY

python3 -m gateforge.governance_replay \
  --compare-summary artifacts/governance_replay_demo/compare_source.json \
  --apply-summary artifacts/governance_replay_demo/apply_tampered.json \
  --out artifacts/governance_replay_demo/replay_needs_review.json

set +e
python3 -m gateforge.governance_replay \
  --compare-summary artifacts/governance_replay_demo/compare_source.json \
  --apply-summary artifacts/governance_replay_demo/apply_tampered.json \
  --strict \
  --out artifacts/governance_replay_demo/replay_strict_fail.json
STRICT_RC=$?
set -e

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/governance_replay_demo")
pass_payload = json.loads((root / "replay_pass.json").read_text(encoding="utf-8"))
review_payload = json.loads((root / "replay_needs_review.json").read_text(encoding="utf-8"))
fail_payload = json.loads((root / "replay_strict_fail.json").read_text(encoding="utf-8"))

flags = {
    "pass_expected_pass": "PASS" if pass_payload.get("decision") == "PASS" else "FAIL",
    "tampered_expected_needs_review": "PASS" if review_payload.get("decision") == "NEEDS_REVIEW" else "FAIL",
    "tampered_strict_expected_fail": "PASS" if fail_payload.get("decision") == "FAIL" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "pass_decision": pass_payload.get("decision"),
    "needs_review_decision": review_payload.get("decision"),
    "strict_fail_decision": fail_payload.get("decision"),
    "needs_review_mismatch_count": len(review_payload.get("mismatches") or []),
    "strict_fail_mismatch_count": len(fail_payload.get("mismatches") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(root / "summary.md").write_text(
    "\n".join(
        [
            "# Governance Replay Demo",
            "",
            f"- pass_decision: `{summary['pass_decision']}`",
            f"- needs_review_decision: `{summary['needs_review_decision']}`",
            f"- strict_fail_decision: `{summary['strict_fail_decision']}`",
            f"- needs_review_mismatch_count: `{summary['needs_review_mismatch_count']}`",
            f"- strict_fail_mismatch_count: `{summary['strict_fail_mismatch_count']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- pass_expected_pass: `{flags['pass_expected_pass']}`",
            f"- tampered_expected_needs_review: `{flags['tampered_expected_needs_review']}`",
            f"- tampered_strict_expected_fail: `{flags['tampered_strict_expected_fail']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

if [[ "$STRICT_RC" -ne 1 ]]; then
  echo "expected strict replay mismatch to exit 1, got $STRICT_RC" >&2
  exit 1
fi

cat artifacts/governance_replay_demo/summary.json
cat artifacts/governance_replay_demo/summary.md
