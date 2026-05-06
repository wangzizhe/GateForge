from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_benchmark_expansion_v0_71_0 import (  # noqa: E402
    DEFAULT_NON_CONNECTOR_OUT_DIR,
    build_non_connector_seed_candidates,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.71 non-connector benchmark seed candidates.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_NON_CONNECTOR_OUT_DIR)
    args = parser.parse_args()
    summary = build_non_connector_seed_candidates(out_dir=args.out_dir)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
