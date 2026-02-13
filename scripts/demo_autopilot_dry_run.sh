#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/autopilot

cat > artifacts/autopilot/demo_dry_run_context.json <<'EOF'
{
  "risk_level": "high",
  "change_summary": "Dry-run review checklist demo"
}
EOF

python3 -m gateforge.autopilot \
  --goal "run medium oscillator flow with strict review" \
  --planner-backend rule \
  --context-json artifacts/autopilot/demo_dry_run_context.json \
  --proposal-id autopilot-dry-run-demo-001 \
  --dry-run \
  --out artifacts/autopilot/autopilot_dry_run_demo.json \
  --report artifacts/autopilot/autopilot_dry_run_demo.md

cat artifacts/autopilot/autopilot_dry_run_demo.json
cat artifacts/autopilot/autopilot_dry_run_demo.md
