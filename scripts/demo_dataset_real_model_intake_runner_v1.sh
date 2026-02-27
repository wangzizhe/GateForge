#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_intake_runner_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl "$OUT_DIR"/*.mo

cat > "$OUT_DIR/small_ok.mo" <<'MODEL'
model SmallOk
  Real x;
equation
  der(x) = -x;
end SmallOk;
MODEL

cat > "$OUT_DIR/medium_ok.mo" <<'MODEL'
model MediumOk
  Real p;
  Real q;
equation
  der(p) = q;
  der(q) = -p;
end MediumOk;
MODEL

cat > "$OUT_DIR/large_ok.mo" <<'MODEL'
model LargeOk
  Real a;
  Real b;
  Real c;
equation
  der(a) = b;
  der(b) = c;
  der(c) = -a;
end LargeOk;
MODEL

cat > "$OUT_DIR/broken.txt" <<'TXT'
not a modelica file
TXT

cat > "$OUT_DIR/queue.jsonl" <<'JSONL'
{"candidate_id":"d1","source_url":"https://example.org/m/small_ok.mo","license":"MIT","domain":"pressure","expected_scale":"small","model_path":"artifacts/dataset_real_model_intake_runner_v1_demo/small_ok.mo","version_hint":"v1"}
{"candidate_id":"d2","source_url":"https://example.org/m/medium_ok.mo","license":"Apache-2.0","domain":"pressure","expected_scale":"medium","model_path":"artifacts/dataset_real_model_intake_runner_v1_demo/medium_ok.mo","version_hint":"v1"}
{"candidate_id":"d3","source_url":"https://example.org/m/large_ok.mo","license":"BSD-3-Clause","domain":"powertrain","expected_scale":"large","model_path":"artifacts/dataset_real_model_intake_runner_v1_demo/large_ok.mo","version_hint":"v1"}
{"candidate_id":"d4","source_url":"https://example.org/m/large_ok_copy.mo","license":"MIT","domain":"powertrain","expected_scale":"large","model_path":"artifacts/dataset_real_model_intake_runner_v1_demo/large_ok.mo","version_hint":"v2"}
{"candidate_id":"d5","source_url":"https://example.org/m/broken.txt","license":"MIT","domain":"pressure","expected_scale":"small","model_path":"artifacts/dataset_real_model_intake_runner_v1_demo/broken.txt","version_hint":"v1"}
{"candidate_id":"d6","source_url":"https://example.org/m/missing.mo","license":"UNKNOWN","domain":"pressure","expected_scale":"medium","model_path":"artifacts/dataset_real_model_intake_runner_v1_demo/missing.mo","version_hint":"v1"}
JSONL

python3 -m gateforge.dataset_real_model_intake_runner_v1 \
  --intake-queue-jsonl "$OUT_DIR/queue.jsonl" \
  --min-weekly-accepted 3 \
  --min-weekly-large-accepted 1 \
  --max-weekly-reject-rate-pct 45 \
  --accepted-out "$OUT_DIR/accepted.json" \
  --rejected-out "$OUT_DIR/rejected.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_real_model_intake_runner_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "accepted_count_present": "PASS" if isinstance(summary.get("accepted_count"), int) else "FAIL",
    "weekly_target_status_present": "PASS" if summary.get("weekly_target_status") in {"PASS", "NEEDS_REVIEW"} else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "intake_status": summary.get("status"),
    "accepted_count": summary.get("accepted_count"),
    "accepted_large_count": summary.get("accepted_large_count"),
    "reject_rate_pct": summary.get("reject_rate_pct"),
    "weekly_target_status": summary.get("weekly_target_status"),
    "bundle_status": bundle_status,
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "intake_status": demo["intake_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
