from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_full_registry_baseline_v0_70_0 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_REGISTRY,
    build_full_registry_task_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a v0.70 full registry repair task bundle.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = build_full_registry_task_bundle(registry_path=args.registry, out_dir=args.out_dir)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
