"""Executor agent: run generated cases via pytest.

Dry-run mode runs `pytest --collect-only` (no browser needed) so the
graph can be verified in environments without Chromium — including this
VM, where `playwright install chromium` cannot download a browser.
A full run (`dry_run=False`) launches the browser and is for ren's
machine or CI, where Chromium is installed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def run_pytest(paths: list[str | Path], dry_run: bool = False) -> dict:
    """Run pytest over paths; return returncode, mode and output tail."""
    cmd = (
        [sys.executable, "-m", "pytest", "--collect-only", "-q"]
        if dry_run
        else [
            sys.executable,
            "-m",
            "pytest",
            "-v",
            "--alluredir=reports/allure-results",
        ]
    )
    cmd += [str(p) for p in paths]
    proc = subprocess.run(
        cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=600, check=False
    )
    output = (proc.stdout + proc.stderr)[-4000:]
    return {
        "mode": "collect-only" if dry_run else "run",
        "returncode": proc.returncode,
        "passed_collect": dry_run and proc.returncode == 0,
        "output_tail": output,
    }
