"""Run tests with isolated scratch space inside this checkout."""

import subprocess
import sys
import uuid
from pathlib import Path

root = Path(__file__).resolve().parents[1]
scratch = (root / ".tools/test-runs" / uuid.uuid4().hex).resolve()
if not scratch.is_relative_to(root / ".tools/test-runs") or scratch.exists():
    raise RuntimeError("Test scratch path must be new and inside this checkout")
scratch.parent.mkdir(parents=True, exist_ok=True)
raise SystemExit(
    subprocess.call(
        [sys.executable, "-m", "pytest", "--basetemp", str(scratch), "--tb=short", *sys.argv[1:]],
        cwd=root,
    )
)
