#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_modelica_moat_roadmap_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/evidence_chain_summary.json" <<'JSON'
{"status":"PASS","chain_health_score":82.0}
JSON

cat > "$OUT_DIR/failure_corpus_saturation_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","saturation_index":72.0,"total_gap_actions":3}
JSON

cat > "$OUT_DIR/large_coverage_push_v1_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","push_target_large_cases":2}
JSON

cat > "$OUT_DIR/anchor_public_release_v1_summary.json" <<'JSON'
{"status":"NEEDS_REVIEW","public_release_score":76.0,"public_release_ready":false}
JSON

python3 -m gateforge.dataset_modelica_moat_roadmap_v1 \
  --evidence-chain-summary "$OUT_DIR/evidence_chain_summary.json" \
  --failure-corpus-saturation-summary "$OUT_DIR/failure_corpus_saturation_summary.json" \
  --large-coverage-push-v1-summary "$OUT_DIR/large_coverage_push_v1_summary.json" \
  --anchor-public-release-v1-summary "$OUT_DIR/anchor_public_release_v1_summary.json" \
  --horizon-weeks 6 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_modelica_moat_roadmap_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
milestones = summary.get("milestones") if isinstance(summary.get("milestones"), list) else []
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if summary.get("roadmap_health_score") is not None else "FAIL",
    "milestones_present": "PASS" if len(milestones) >= 4 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "roadmap_status": summary.get("status"),
    "roadmap_health_score": summary.get("roadmap_health_score"),
    "high_priority_milestones": summary.get("high_priority_milestones"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "roadmap_status": payload["roadmap_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
