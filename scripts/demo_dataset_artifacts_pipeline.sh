#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_artifacts_pipeline_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl

# Ensure at least minimal artifacts exist so the pipeline is always runnable.
if [[ ! -f "artifacts/benchmark_v0/summary.json" ]]; then
  bash scripts/demo_dataset_pipeline.sh >/dev/null
fi

python3 -m gateforge.dataset_collect \
  --root artifacts \
  --out "$OUT_DIR/collect_summary.json" \
  --report-out "$OUT_DIR/collect_summary.md"

python3 -m gateforge.dataset_build \
  --collect-summary "$OUT_DIR/collect_summary.json" \
  --out-dir "$OUT_DIR/build"

python3 -m gateforge.dataset_quality_gate \
  --build-summary "$OUT_DIR/build/summary.json" \
  --quality "$OUT_DIR/build/quality_report.json" \
  --distribution "$OUT_DIR/build/distribution.json" \
  --out "$OUT_DIR/build/quality_gate.json" \
  --report-out "$OUT_DIR/build/quality_gate.md" \
  --min-total-cases 1 \
  --min-failure-type-coverage 1 \
  --min-oracle-match-rate 0.0 \
  --min-replay-stable-rate 0.0 \
  --max-duplicate-rate 1.0

python3 -m gateforge.dataset_freeze \
  --dataset-jsonl "$OUT_DIR/build/dataset_cases.jsonl" \
  --distribution-json "$OUT_DIR/build/distribution.json" \
  --quality-json "$OUT_DIR/build/quality_report.json" \
  --quality-gate "$OUT_DIR/build/quality_gate.json" \
  --freeze-id "freeze_v1_artifacts_demo" \
  --out-dir "$OUT_DIR/freeze" \
  --min-cases 1 \
  --min-failure-case-rate 0.0

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_artifacts_pipeline_demo")
collect = json.loads((out / "collect_summary.json").read_text(encoding="utf-8"))
build = json.loads((out / "build" / "summary.json").read_text(encoding="utf-8"))
gate = json.loads((out / "build" / "quality_gate.json").read_text(encoding="utf-8"))
freeze = json.loads((out / "freeze" / "summary.json").read_text(encoding="utf-8"))

counts = collect.get("counts", {})
flags = {
    "has_any_input_summary": "PASS"
    if (counts.get("benchmark_summary_count", 0) + counts.get("mutation_summary_count", 0) + counts.get("run_summary_count", 0) + counts.get("autopilot_summary_count", 0)) > 0
    else "FAIL",
    "build_deduplicated_nonzero": "PASS" if int(build.get("deduplicated_cases", 0)) > 0 else "FAIL",
    "quality_gate_pass": "PASS" if gate.get("status") == "PASS" else "FAIL",
    "freeze_pass": "PASS" if freeze.get("status") == "PASS" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "collect_counts": counts,
    "build_deduplicated_cases": build.get("deduplicated_cases"),
    "quality_gate_status": gate.get("status"),
    "freeze_status": freeze.get("status"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Artifacts Pipeline Demo",
            "",
            f"- build_deduplicated_cases: `{summary['build_deduplicated_cases']}`",
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
