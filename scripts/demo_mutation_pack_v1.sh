#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND="${MUTATION_BACKEND:-mock}"
COUNT="${MUTATION_COUNT:-24}"
OUT_ROOT="artifacts/mutation_pack_v1"
MUT_DIR="examples/mutants/v1"

mkdir -p "$OUT_ROOT"
rm -f "$OUT_ROOT"/*.json "$OUT_ROOT"/*.md "$OUT_ROOT"/*.log

python3 -m gateforge.mutate \
  --out-dir "$MUT_DIR" \
  --manifest-out "$OUT_ROOT/manifest.json" \
  --pack-out "$OUT_ROOT/pack.json" \
  --pack-id mutation_pack_v1 \
  --pack-version v1 \
  --backend "$BACKEND" \
  --count "$COUNT"

set +e
python3 -m gateforge.benchmark \
  --pack "$OUT_ROOT/pack.json" \
  --out-dir "$OUT_ROOT/cases" \
  --summary-out "$OUT_ROOT/summary.json" \
  --report-out "$OUT_ROOT/summary.md" >"$OUT_ROOT/benchmark.log" 2>&1
BENCH_RC=$?
set -e

python3 -m gateforge.mutation_metrics \
  --manifest "$OUT_ROOT/manifest.json" \
  --summary "$OUT_ROOT/summary.json" \
  --out "$OUT_ROOT/metrics.json" \
  --report-out "$OUT_ROOT/metrics.md"

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/mutation_pack_v1")
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))

flags = {
    "manifest_case_count_matches": "PASS"
    if int(manifest.get("total_cases", -1)) == int(summary.get("total_cases", -2))
    else "FAIL",
    "metrics_match_rate_present": "PASS" if isinstance(metrics.get("expected_vs_actual_match_rate"), float) else "FAIL",
    "metrics_distribution_present": "PASS" if isinstance(metrics.get("failure_type_distribution"), dict) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "pack_id": manifest.get("pack_id"),
    "pack_version": manifest.get("pack_version"),
    "backend": manifest.get("backend"),
    "total_cases": manifest.get("total_cases"),
    "pass_count": summary.get("pass_count"),
    "fail_count": summary.get("fail_count"),
    "metrics_path": "artifacts/mutation_pack_v1/metrics.json",
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(root / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
(root / "demo_summary.md").write_text(
    "\n".join(
        [
            "# GateForge Mutation Pack v1 Demo",
            "",
            f"- pack_id: `{demo['pack_id']}`",
            f"- pack_version: `{demo['pack_version']}`",
            f"- backend: `{demo['backend']}`",
            f"- total_cases: `{demo['total_cases']}`",
            f"- pass_count: `{demo['pass_count']}`",
            f"- fail_count: `{demo['fail_count']}`",
            f"- metrics_path: `{demo['metrics_path']}`",
            f"- bundle_status: `{demo['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "total_cases": demo["total_cases"], "fail_count": demo["fail_count"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

if [[ "$BENCH_RC" -ne 0 ]]; then
  echo "benchmark exited non-zero: $BENCH_RC" >&2
  cat "$OUT_ROOT/benchmark.log"
  exit 1
fi

cat "$OUT_ROOT/metrics.json"
cat "$OUT_ROOT/demo_summary.json"
cat "$OUT_ROOT/demo_summary.md"
