#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_provider_role_overrides_v0_27_12 import (  # noqa: E402
    DEFAULT_CAPABILITY_AUDIT,
    DEFAULT_OUT_DIR,
    DEFAULT_ROLE_REGISTRY,
    run_provider_role_overrides,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.27.12 provider/harness role overrides.")
    parser.add_argument("--role-registry", default=str(DEFAULT_ROLE_REGISTRY))
    parser.add_argument("--capability-audit", default=str(DEFAULT_CAPABILITY_AUDIT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = run_provider_role_overrides(
        role_registry_path=Path(args.role_registry),
        capability_audit_path=Path(args.capability_audit),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} decision={decision} blocked={current_harness_blocked_count} "
        "remaining_capability={remaining_capability_baseline_candidate_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
