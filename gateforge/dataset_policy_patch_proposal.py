from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


DATASET_POLICY_DIR = Path("policies/dataset")


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(path: str, payload: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _default_md_path(out_json: str) -> str:
    out = Path(out_json)
    if out.suffix == ".json":
        return str(out.with_suffix(".md"))
    return f"{out_json}.md"


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _resolve_policy_path(policy_path: str | None, policy_profile: str | None) -> str:
    if policy_path and policy_profile:
        raise ValueError("Use either --policy-path or --policy-profile, not both")
    if policy_profile:
        profile = policy_profile if policy_profile.endswith(".json") else f"{policy_profile}.json"
        resolved = DATASET_POLICY_DIR / profile
        if not resolved.exists():
            raise ValueError(f"Dataset policy profile not found: {resolved}")
        return str(resolved)
    if policy_path:
        return policy_path
    return str(DATASET_POLICY_DIR / "default.json")


def _build_changes(before: dict, after: dict) -> list[dict]:
    keys = sorted(set(before.keys()) | set(after.keys()))
    rows: list[dict] = []
    for key in keys:
        old = before.get(key)
        new = after.get(key)
        if old != new:
            rows.append({"key": key, "old": old, "new": new})
    return rows


def _write_markdown(path: str, proposal: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GateForge Dataset Policy Patch Proposal",
        "",
        f"- proposal_id: `{proposal.get('proposal_id')}`",
        f"- source_advisor_path: `{proposal.get('source_advisor_path')}`",
        f"- target_policy_path: `{proposal.get('target_policy_path')}`",
        f"- change_count: `{proposal.get('change_count')}`",
        f"- requires_human_approval: `{proposal.get('requires_human_approval')}`",
        "",
        "## Changes",
        "",
    ]
    changes = proposal.get("changes") if isinstance(proposal.get("changes"), list) else []
    if changes:
        for c in changes:
            lines.append(f"- `{c.get('key')}`: `{c.get('old')}` -> `{c.get('new')}`")
    else:
        lines.append("- `none`")
    lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create dataset policy patch proposal from dataset policy advisor")
    parser.add_argument("--advisor-summary", required=True, help="Path to dataset_policy_advisor JSON")
    parser.add_argument("--policy-path", default=None, help="Target dataset policy path")
    parser.add_argument("--policy-profile", default=None, help="Target dataset policy profile name")
    parser.add_argument("--proposal-id", default=None, help="Optional proposal id")
    parser.add_argument("--out", default="artifacts/dataset_policy_patch/proposal.json", help="Output proposal JSON")
    parser.add_argument("--report", default=None, help="Output proposal markdown")
    args = parser.parse_args()

    advisor = _load_json(args.advisor_summary)
    advice = advisor.get("advice", {}) if isinstance(advisor.get("advice"), dict) else {}
    patch = advice.get("threshold_patch", {}) if isinstance(advice.get("threshold_patch"), dict) else {}

    policy_path = _resolve_policy_path(args.policy_path, args.policy_profile)
    before = _load_json(policy_path)
    after = dict(before)

    for key in ("min_deduplicated_cases", "min_failure_case_rate"):
        if key in patch and patch.get(key) is not None:
            after[key] = patch[key]

    changes = _build_changes(before, after)
    proposal_id = args.proposal_id or f"dataset-policy-patch-{int(datetime.now(timezone.utc).timestamp())}"

    proposal = {
        "proposal_id": proposal_id,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_advisor_path": args.advisor_summary,
        "target_policy_path": policy_path,
        "target_policy_profile": args.policy_profile,
        "advisor_suggested_action": advice.get("suggested_action"),
        "advisor_suggested_policy_profile": advice.get("suggested_policy_profile"),
        "advisor_confidence": advice.get("confidence"),
        "advisor_reasons": advice.get("reasons", []),
        "before_hash": _stable_hash(before),
        "after_hash": _stable_hash(after),
        "change_count": len(changes),
        "changes": changes,
        "policy_before": before,
        "policy_after": after,
        "requires_human_approval": True,
        "approval_status": "PENDING",
    }
    _write_json(args.out, proposal)
    _write_markdown(args.report or _default_md_path(args.out), proposal)
    print(json.dumps({"proposal_id": proposal_id, "change_count": len(changes)}))


if __name__ == "__main__":
    main()
