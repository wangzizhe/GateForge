#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/runtime_decision_ledger_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

python3 -m gateforge.run \
  --proposal examples/proposals/proposal_demo_mock.json \
  --baseline baselines/mock_minimal_probe_baseline.json \
  --out "$OUT_DIR/run_summary.json" \
  --decision-ledger "$OUT_DIR/decision_ledger.jsonl" \
  --decision-ledger-summary-out "$OUT_DIR/ledger_summary.json"

python3 -m gateforge.autopilot \
  --goal "run demo mock pass" \
  --proposal-id runtime-ledger-demo-001 \
  --baseline baselines/mock_minimal_probe_baseline.json \
  --out "$OUT_DIR/autopilot_summary.json" \
  --decision-ledger "$OUT_DIR/decision_ledger.jsonl" \
  --decision-ledger-summary-out "$OUT_DIR/ledger_summary.json"

python3 -m gateforge.runtime_ledger \
  --ledger "$OUT_DIR/decision_ledger.jsonl" \
  --summary-out "$OUT_DIR/ledger_summary.json" \
  --report-out "$OUT_DIR/ledger_summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/runtime_decision_ledger_demo")
summary = json.loads((out / "ledger_summary.json").read_text(encoding="utf-8"))
run_summary = json.loads((out / "run_summary.json").read_text(encoding="utf-8"))
autopilot_summary = json.loads((out / "autopilot_summary.json").read_text(encoding="utf-8"))

flags = {
    "records_at_least_two": "PASS" if int(summary.get("total_records", 0)) >= 2 else "FAIL",
    "run_append_status_ok": "PASS" if run_summary.get("decision_ledger_append_status") == "appended" else "FAIL",
    "autopilot_append_status_ok": "PASS"
    if autopilot_summary.get("decision_ledger_append_status") == "appended"
    else "FAIL",
    "source_counts_contains_run": "PASS" if int(summary.get("source_counts", {}).get("run", 0)) >= 1 else "FAIL",
    "source_counts_contains_autopilot": "PASS"
    if int(summary.get("source_counts", {}).get("autopilot", 0)) >= 1
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

payload = {
    "total_records": summary.get("total_records"),
    "status_counts": summary.get("status_counts", {}),
    "source_counts": summary.get("source_counts", {}),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Runtime Decision Ledger Demo",
            "",
            f"- total_records: `{payload['total_records']}`",
            f"- source_counts: `{payload['source_counts']}`",
            f"- bundle_status: `{payload['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- records_at_least_two: `{flags['records_at_least_two']}`",
            f"- run_append_status_ok: `{flags['run_append_status_ok']}`",
            f"- autopilot_append_status_ok: `{flags['autopilot_append_status_ok']}`",
            f"- source_counts_contains_run: `{flags['source_counts_contains_run']}`",
            f"- source_counts_contains_autopilot: `{flags['source_counts_contains_autopilot']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
