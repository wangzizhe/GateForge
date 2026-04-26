#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_public_private_boundary_v0_25_4 import (
    DEFAULT_OUT_DIR,
    build_public_private_boundary_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.25.4 public/private boundary audit.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = build_public_private_boundary_audit(out_dir=Path(args.out_dir))
    print("status={status} findings={finding_count} manifest={manifest_finding_count} changelog={changelog_finding_count}".format(**summary))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
