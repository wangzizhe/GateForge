#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_model_intake_board_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/candidate_catalog.json" <<'JSON'
{
  "candidates": [
    {"model_id":"mdl_a","license":"MIT","scale_hint":"medium","complexity_score":120,"source_url":"https://example.com/a.mo","repro_command":"python -c \"print('ok')\""},
    {"model_id":"mdl_b","license":"UNKNOWN","scale_hint":"large","complexity_score":130,"source_url":"https://example.com/b.mo","repro_command":""},
    {"model_id":"mdl_c","license":"Apache-2.0","scale_hint":"large","complexity_score":180,"source_url":"https://example.com/c.mo","repro_command":"python -c \"print('ok')\""}
  ]
}
JSON
cat > "$OUT_DIR/intake_summary.json" <<'JSON'
{"status":"PASS","accepted_count":2}
JSON
cat > "$OUT_DIR/intake_ledger.json" <<'JSON'
{"records":[{"model_id":"mdl_c","decision":"ACCEPT"},{"model_id":"mdl_b","decision":"REJECT"}]}
JSON

python3 -m gateforge.dataset_model_intake_board_v1 \
  --candidate-catalog "$OUT_DIR/candidate_catalog.json" \
  --intake-summary "$OUT_DIR/intake_summary.json" \
  --intake-ledger "$OUT_DIR/intake_ledger.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_model_intake_board_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "score_present": "PASS" if isinstance(summary.get("board_score"), (int, float)) else "FAIL",
    "ready_count_present": "PASS" if isinstance(summary.get("ready_count"), int) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "board_status": summary.get("status"),
    "board_score": summary.get("board_score"),
    "ready_count": summary.get("ready_count"),
    "blocked_count": summary.get("blocked_count"),
    "ingested_count": summary.get("ingested_count"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "board_status": payload["board_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
