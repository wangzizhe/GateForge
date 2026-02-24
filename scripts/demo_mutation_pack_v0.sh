#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND="${MUTATION_BACKEND:-openmodelica_docker}"
COUNT="${MUTATION_COUNT:-20}"
OUT_ROOT="artifacts/mutation_pack_v0"
MUT_DIR="examples/mutants/v0"

mkdir -p "$OUT_ROOT"
rm -f "$OUT_ROOT"/*.json "$OUT_ROOT"/*.md "$OUT_ROOT"/*.log

python3 -m gateforge.mutate \
  --out-dir "$MUT_DIR" \
  --manifest-out "$OUT_ROOT/manifest.json" \
  --pack-out "$OUT_ROOT/pack.json" \
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

python3 - <<'PY'
import json
from pathlib import Path

root = Path("artifacts/mutation_pack_v0")
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))

mutation_counts = {}
for row in manifest.get("cases", []):
    k = str(row.get("mutation_type") or "unknown")
    mutation_counts[k] = mutation_counts.get(k, 0) + 1

flags = {
    "manifest_case_count_matches": "PASS"
    if int(manifest.get("total_cases", -1)) == int(summary.get("total_cases", -2))
    else "FAIL",
    "benchmark_pass_count_matches_total": "PASS"
    if int(summary.get("pass_count", -1)) == int(summary.get("total_cases", -2))
    else "FAIL",
    "has_mutation_types": "PASS" if len(mutation_counts) >= 3 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
demo = {
    "pack_id": manifest.get("pack_id"),
    "backend": manifest.get("backend"),
    "total_cases": manifest.get("total_cases"),
    "pass_count": summary.get("pass_count"),
    "fail_count": summary.get("fail_count"),
    "mutation_type_counts": mutation_counts,
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(root / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
(root / "demo_summary.md").write_text(
    "\n".join(
        [
            "# GateForge Mutation Pack v0 Demo",
            "",
            f"- pack_id: `{demo['pack_id']}`",
            f"- backend: `{demo['backend']}`",
            f"- total_cases: `{demo['total_cases']}`",
            f"- pass_count: `{demo['pass_count']}`",
            f"- fail_count: `{demo['fail_count']}`",
            f"- bundle_status: `{demo['bundle_status']}`",
            "",
            "## Mutation Type Counts",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(mutation_counts.items())],
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

cat "$OUT_ROOT/demo_summary.json"
cat "$OUT_ROOT/demo_summary.md"
