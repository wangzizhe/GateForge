#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_v0_3_12_block_b_runner import main  # noqa: E402


if __name__ == "__main__":
    sys.exit(main())
