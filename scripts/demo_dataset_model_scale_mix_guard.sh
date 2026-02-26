#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
OUT_DIR="artifacts/dataset_model_scale_mix_guard_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/failure_corpus_registry_summary.json" <<'JSON'
{"model_scale_counts": {"small": 14, "medium": 5, "large": 3}}
JSON
cat > "$OUT_DIR/failure_supply_plan.json" <<'JSON'
{"weekly_supply_target": 10}
JSON

python3 -m gateforge.dataset_model_scale_mix_guard \
  --failure-corpus-registry-summary "$OUT_DIR/failure_corpus_registry_summary.json" \
  --failure-supply-plan "$OUT_DIR/failure_supply_plan.json" \
  --out "$OUT_DIR/summary.json"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_model_scale_mix_guard_demo")
p = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {"status_present": "PASS" if p.get("status") in {"PASS","NEEDS_REVIEW","FAIL"} else "FAIL", "ratios_present": "PASS" if isinstance(p.get("medium_ratio_pct"), (int, float)) and isinstance(p.get("large_ratio_pct"), (int, float)) else "FAIL"}
summary = {"guard_status": p.get("status"), "medium_ratio_pct": p.get("medium_ratio_pct"), "large_ratio_pct": p.get("large_ratio_pct"), "result_flags": flags, "bundle_status": "PASS" if all(v=="PASS" for v in flags.values()) else "FAIL"}
(out / "demo_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"], "guard_status": summary["guard_status"]}))
if summary["bundle_status"] != "PASS":
  raise SystemExit(1)
PY
