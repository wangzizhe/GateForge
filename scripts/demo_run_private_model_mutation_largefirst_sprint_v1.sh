#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/run_private_model_mutation_largefirst_sprint_v1_demo"
MODEL_DIR="$OUT_DIR/private_models"
BATCH_DIR="$OUT_DIR/batch"
mkdir -p "$MODEL_DIR"
rm -rf "$BATCH_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$MODEL_DIR"/*.mo

python3 - <<'PY'
from pathlib import Path

root = Path("artifacts/run_private_model_mutation_largefirst_sprint_v1_demo/private_models")
root.mkdir(parents=True, exist_ok=True)

for idx in range(1, 5):
    large_lines = [f"model LargePlant{idx}", "  Real x;", "  Real y;", "  Real z;"]
    for i in range(1, 170):
        large_lines.append(f"  parameter Real p{i}={i};")
    large_lines.extend(
        [
            "equation",
            "  der(x)=p1-p2+p3-p4+p5-p6+p7;",
            "  der(y)=p8-p9+p10-p11+p12-p13+p14;",
            "  der(z)=p15-p16+p17-p18+p19-p20+p21;",
            f"end LargePlant{idx};",
        ]
    )
    (root / f"LargePlant{idx}.mo").write_text("\n".join(large_lines) + "\n", encoding="utf-8")

for idx in range(1, 3):
    medium_lines = [f"model MediumPlant{idx}", "  Real x;"]
    for i in range(1, 90):
        medium_lines.append(f"  parameter Real k{i}={i};")
    medium_lines.extend(
        [
            "equation",
            "  der(x)=k1-k2+k3-k4+k5;",
            f"end MediumPlant{idx};",
        ]
    )
    (root / f"MediumPlant{idx}.mo").write_text("\n".join(medium_lines) + "\n", encoding="utf-8")
PY

GATEFORGE_PRIVATE_MODEL_ROOTS="$MODEL_DIR" \
GATEFORGE_PRIVATE_BATCH_OUT_DIR="$BATCH_DIR" \
GATEFORGE_MIN_DISCOVERED_MODELS=6 \
GATEFORGE_MIN_ACCEPTED_MODELS=6 \
GATEFORGE_MIN_ACCEPTED_LARGE_MODELS=4 \
GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT=60 \
GATEFORGE_MIN_GENERATED_MUTATIONS=120 \
GATEFORGE_MIN_MUTATION_PER_MODEL=8 \
GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS=100 \
bash scripts/run_private_model_mutation_largefirst_sprint_v1.sh >/dev/null

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/run_private_model_mutation_largefirst_sprint_v1_demo")
batch = out / "batch"
summary = json.loads((batch / "summary.json").read_text(encoding="utf-8"))
flags = {
    "scale_gate_pass": "PASS" if summary.get("scale_gate_status") == "PASS" else "FAIL",
    "profile_large_first": "PASS" if summary.get("model_scale_profile") == "large_first" else "FAIL",
    "large_ratio_pass": "PASS" if float(summary.get("accepted_large_ratio_pct", 0.0) or 0.0) >= 60.0 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

demo = {
    "bundle_status": bundle_status,
    "scale_gate_status": summary.get("scale_gate_status"),
    "model_scale_profile": summary.get("model_scale_profile"),
    "accepted_models": summary.get("accepted_models"),
    "accepted_large_models": summary.get("accepted_large_models"),
    "accepted_large_ratio_pct": summary.get("accepted_large_ratio_pct"),
    "generated_mutations": summary.get("generated_mutations"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "scale_gate_status": summary.get("scale_gate_status")}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
