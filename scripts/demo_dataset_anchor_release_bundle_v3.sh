#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_anchor_release_bundle_v3_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/anchor_benchmark_pack_v2_summary.json" <<'JSON'
{"status": "PASS", "anchor_ready": true, "anchor_pack_score": 84.5}
JSON
cat > "$OUT_DIR/open_source_intake_summary.json" <<'JSON'
{"status": "PASS", "accepted_count": 3}
JSON
cat > "$OUT_DIR/mutation_validator_summary.json" <<'JSON'
{"status": "PASS", "validated_count": 10, "expected_match_ratio_pct": 88.0}
JSON
cat > "$OUT_DIR/failure_distribution_benchmark_v2_summary.json" <<'JSON'
{"status": "PASS", "failure_type_drift": 0.22}
JSON
cat > "$OUT_DIR/gateforge_vs_plain_ci_summary.json" <<'JSON'
{"status": "PASS", "verdict": "GATEFORGE_ADVANTAGE", "advantage_score": 8}
JSON

python3 -m gateforge.dataset_anchor_release_bundle_v3 \
  --anchor-benchmark-pack-v2-summary "$OUT_DIR/anchor_benchmark_pack_v2_summary.json" \
  --open-source-intake-summary "$OUT_DIR/open_source_intake_summary.json" \
  --mutation-validator-summary "$OUT_DIR/mutation_validator_summary.json" \
  --failure-distribution-benchmark-v2-summary "$OUT_DIR/failure_distribution_benchmark_v2_summary.json" \
  --gateforge-vs-plain-ci-summary "$OUT_DIR/gateforge_vs_plain_ci_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_anchor_release_bundle_v3_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "release_score_present": "PASS" if isinstance(summary.get("release_score"), (int, float)) else "FAIL",
    "playbook_present": "PASS" if isinstance(summary.get("reproducible_playbook"), list) and len(summary.get("reproducible_playbook")) >= 5 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "release_bundle_status": summary.get("status"),
    "release_ready": summary.get("release_ready"),
    "release_score": summary.get("release_score"),
    "release_bundle_id": summary.get("release_bundle_id"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "release_bundle_status": summary_out["release_bundle_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
