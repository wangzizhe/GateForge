---
name: gateforge-mvp-freeze-check
description: Perform GateForge MVP freeze validation and produce a concise readiness verdict. Use when asked to confirm that core governance flows are stable before demo, release, or pause point.
---

# GateForge MVP Freeze Check

Run from repository root.

## Validation Sequence

```bash
python3 -m unittest discover -s tests -v
bash scripts/demo_medium_pack_v1_dashboard.sh
bash scripts/demo_governance_policy_patch_dashboard.sh
bash scripts/demo_ci_matrix.sh --none --checker-demo --autopilot-dry-run --governance-policy-patch-dashboard-demo
```

## Readiness Rules

1. Unit tests must pass.
2. Medium dashboard demo must return bundle pass.
3. Policy patch dashboard demo must return bundle pass.
4. Targeted matrix run must return pass.

## Output Contract

Return one verdict:
- `MVP_FREEZE_PASS` or `MVP_FREEZE_FAIL`

If fail, include first blocking command and one-line remediation target.
