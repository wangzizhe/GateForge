---
name: gateforge-policy-patch-approval
description: Execute GateForge policy patch proposal and human approval flow, including single/dual reviewer profiles. Use when asked to validate or apply policy threshold patch changes with governance controls.
---

# GateForge Policy Patch Approval

Run from repository root.

## Execute Demo Flow

```bash
bash scripts/demo_governance_policy_patch_apply.sh
```

## Check Approval Outcomes

1. No approval path should be `NEEDS_REVIEW`.
2. Reject path should be `FAIL`.
3. Approve without `--apply` should be `NEEDS_REVIEW`.
4. Approve with `--apply` should be `PASS` and write policy.

## Dual Reviewer Profile

Use `--approval-profile dual_reviewer` to require two unique approvers.

## Output Contract

Return:
- proposal_id
- final_status by path
- whether policy write happened
