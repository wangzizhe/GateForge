from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_submit_checkpoint_probe_summary_v0_63_0 import (
    DEFAULT_ATTRIBUTION,
    DEFAULT_OUT_DIR,
    DEFAULT_REMAINING_SLICE,
    DEFAULT_SUBMIT_SLICE,
    run_submit_checkpoint_probe_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize the transparent submit checkpoint probe.")
    parser.add_argument("--attribution", type=Path, default=DEFAULT_ATTRIBUTION)
    parser.add_argument("--submit-slice-dir", type=Path, default=DEFAULT_SUBMIT_SLICE)
    parser.add_argument("--remaining-slice-dir", type=Path, default=DEFAULT_REMAINING_SLICE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_submit_checkpoint_probe_summary(
        attribution_path=args.attribution,
        submit_slice_dir=args.submit_slice_dir,
        remaining_slice_dir=args.remaining_slice_dir,
        out_dir=args.out_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
