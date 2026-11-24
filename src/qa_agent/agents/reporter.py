"""Reporter agent: one-page JSON summary of a graph run.

Writes reports/summary.json (reports/ is gitignored). The Allure HTML
report itself is still produced by pytest --alluredir on a full run.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def write_summary(summary: dict, path: str | Path | None = None) -> Path:
    """Write the run summary as JSON and return its path."""
    out = Path(path) if path else PROJECT_ROOT / "reports" / "summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return out
