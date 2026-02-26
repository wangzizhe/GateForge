#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_external_anchor_release_gate_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/anchor_public_release_summary.json" <<'JSON'
{"status":"PASS","public_release_score":87.0}
JSON

cat > "$OUT_DIR/moat_public_scoreboard_summary.json" <<'JSON'
{"status":"PASS","moat_public_score":85.0}
JSON

cat > "$OUT_DIR/large_model_benchmark_pack_summary.json" <<'JSON'
{"status":"PASS","pack_readiness_score":84.0}
JSON

cat > "$OUT_DIR/modelica_library_provenance_guard_summary.json" <<'JSON'
{"status":"PASS","provenance_completeness_pct":98.0,"unknown_license_ratio_pct":1.0}
JSON

cat > "$OUT_DIR/optional_ci_contract_summary.json" <<'JSON'
{"status":"PASS","fail_count":0}
JSON

python3 -m gateforge.dataset_external_anchor_release_gate_v1 \
  --anchor-public-release-summary "$OUT_DIR/anchor_public_release_summary.json" \
  --moat-public-scoreboard-summary "$OUT_DIR/moat_public_scoreboard_summary.json" \
  --large-model-benchmark-pack-summary "$OUT_DIR/large_model_benchmark_pack_summary.json" \
  --modelica-library-provenance-guard-summary "$OUT_DIR/modelica_library_provenance_guard_summary.json" \
  --optional-ci-contract-summary "$OUT_DIR/optional_ci_contract_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_external_anchor_release_gate_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "decision_present": "PASS" if summary.get("gate_decision") in {"ALLOW", "NEEDS_REVIEW", "BLOCK"} else "FAIL",
    "score_present": "PASS" if summary.get("release_readiness_score") is not None else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "gate_status": summary.get("status"),
    "gate_decision": summary.get("gate_decision"),
    "release_readiness_score": summary.get("release_readiness_score"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "gate_status": payload["gate_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
