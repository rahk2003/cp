#!/usr/bin/env python3
"""
واجهة قديمة — تفويض كامل إلى run_local_oil_llm.py (نفس المنطق والقالب).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    here = Path(__file__).resolve().parent
    target = here / "run_local_oil_llm.py"
    argv = [sys.executable, str(target), *sys.argv[1:]]
    raise SystemExit(subprocess.call(argv, env=os.environ.copy(), cwd=str(here)))


if __name__ == "__main__":
    main()
