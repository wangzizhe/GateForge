#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_milestone_public_brief_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/checkpoint.json" <<'JSON'
{"status":"PASS","milestone_decision":"GO","checkpoint_score":85.0,"blockers":[]}
JSON
cat > "$OUT_DIR/scoreboard.json" <<'JSON'
{"moat_public_score":86.0}
JSON
cat > "$OUT_DIR/alignment.json" <<'JSON'
{"alignment_score":88.0}
JSON

python3 -m gateforge.dataset_milestone_public_brief_v1 \
  --milestone-checkpoint-summary "$OUT_DIR/checkpoint.json" \
  --moat-public-scoreboard-summary "$OUT_DIR/scoreboard.json" \
  --snapshot-moat-alignment-summary "$OUT_DIR/alignment.json" \
  --out "$OUT_DIR/brief.json" \
  --report-out "$OUT_DIR/brief.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_milestone_public_brief_v1_demo")
brief = json.loads((out / "brief.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if isinstance(brief.get("milestone_status"), str) else "FAIL",
    "headline_present": "PASS" if isinstance(brief.get("headline"), str) and brief.get("headline") else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
(out / "demo_summary.json").write_text(json.dumps({"brief_status": brief.get("milestone_status"), "bundle_status": bundle_status, "result_flags": flags}, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "brief_status": brief.get("milestone_status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
