#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_pipeline_demo"
IN_DIR="$OUT_DIR/inputs"
mkdir -p "$IN_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl "$IN_DIR"/*.json

cat > "$IN_DIR/benchmark_summary.json" <<'JSON'
{
  "pack_id": "pack_v0",
  "proposal_id": null,
  "cases": [
    {
      "name": "bench-pass",
      "backend": "mock",
      "script": "examples/openmodelica/minimal_probe.mos",
      "result": "PASS",
      "failure_type": "none",
      "mismatches": [],
      "json_path": "artifacts/benchmark_v0/bench-pass.json"
    }
  ]
}
JSON

cat > "$IN_DIR/mutation_summary.json" <<'JSON'
{
  "pack_id": "mutation_pack_v1",
  "proposal_id": null,
  "cases": [
    {
      "name": "mut-fail",
      "backend": "mock",
      "script": "examples/mutants/v0/mut-fail.mos",
      "result": "PASS",
      "failure_type": "script_parse_error",
      "mismatches": [],
      "json_path": "artifacts/mutation_pack_v1/mut-fail.json"
    }
  ]
}
JSON

cat > "$IN_DIR/run_summary.json" <<'JSON'
{
  "proposal_id": "run-demo-001",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "PASS",
  "policy_decision": "PASS",
  "fail_reasons": [],
  "risk_level": "low",
  "policy_reasons": [],
  "required_human_checks": []
}
JSON

cat > "$IN_DIR/autopilot_summary.json" <<'JSON'
{
  "proposal_id": "autopilot-demo-001",
  "backend": "mock",
  "model_script": "examples/openmodelica/minimal_probe.mos",
  "status": "FAIL",
  "policy_decision": "NEEDS_REVIEW",
  "fail_reasons": ["runtime_regression:1.0000s>0.6000s"],
  "risk_level": "medium",
  "policy_reasons": ["runtime_regression:1.0000s>0.6000s"],
  "required_human_checks": ["Check runtime regression context"]
}
JSON

python3 -m gateforge.dataset_build \
  --benchmark-summary "$IN_DIR/benchmark_summary.json" \
  --mutation-summary "$IN_DIR/mutation_summary.json" \
  --run-summary "$IN_DIR/run_summary.json" \
  --autopilot-summary "$IN_DIR/autopilot_summary.json" \
  --out-dir "$OUT_DIR/build"

python3 -m gateforge.dataset_quality_gate \
  --build-summary "$OUT_DIR/build/summary.json" \
  --quality "$OUT_DIR/build/quality_report.json" \
  --distribution "$OUT_DIR/build/distribution.json" \
  --out "$OUT_DIR/build/quality_gate.json" \
  --report-out "$OUT_DIR/build/quality_gate.md" \
  --min-total-cases 4 \
  --min-failure-type-coverage 1 \
  --min-oracle-match-rate 0.0 \
  --min-replay-stable-rate 0.0 \
  --max-duplicate-rate 0.5

python3 -m gateforge.dataset_freeze \
  --dataset-jsonl "$OUT_DIR/build/dataset_cases.jsonl" \
  --distribution-json "$OUT_DIR/build/distribution.json" \
  --quality-json "$OUT_DIR/build/quality_report.json" \
  --quality-gate "$OUT_DIR/build/quality_gate.json" \
  --freeze-id "freeze_v1_demo" \
  --out-dir "$OUT_DIR/freeze" \
  --min-cases 4 \
  --min-failure-case-rate 0.2

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_pipeline_demo")
build = json.loads((out / "build" / "summary.json").read_text(encoding="utf-8"))
quality = json.loads((out / "build" / "quality_report.json").read_text(encoding="utf-8"))
quality_gate = json.loads((out / "build" / "quality_gate.json").read_text(encoding="utf-8"))
freeze = json.loads((out / "freeze" / "summary.json").read_text(encoding="utf-8"))

flags = {
    "build_case_count_ok": "PASS" if int(build.get("deduplicated_cases", 0)) >= 4 else "FAIL",
    "quality_failure_rate_ok": "PASS" if float(quality.get("failure_case_rate", 0.0)) >= 0.2 else "FAIL",
    "quality_gate_status_pass": "PASS" if quality_gate.get("status") == "PASS" else "FAIL",
    "freeze_status_pass": "PASS" if freeze.get("status") == "PASS" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "build_deduplicated_cases": build.get("deduplicated_cases"),
    "quality_failure_case_rate": quality.get("failure_case_rate"),
    "quality_gate_status": quality_gate.get("status"),
    "freeze_status": freeze.get("status"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Pipeline Demo",
            "",
            f"- build_deduplicated_cases: `{summary['build_deduplicated_cases']}`",
            f"- quality_failure_case_rate: `{summary['quality_failure_case_rate']}`",
            f"- quality_gate_status: `{summary['quality_gate_status']}`",
            f"- freeze_status: `{summary['freeze_status']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
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
