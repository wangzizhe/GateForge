from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_structural_ambiguity_benchmark_v0_72_0 import (  # noqa: E402
    DEFAULT_SECOND_GEN_OUT_DIR,
    build_second_generation_structural_ambiguity_variants,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.74 second-generation structural ambiguity variants.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_SECOND_GEN_OUT_DIR)
    args = parser.parse_args()
    summary = build_second_generation_structural_ambiguity_variants(out_dir=args.out_dir)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
