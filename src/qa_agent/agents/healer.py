"""Healer agent (Day 8-10): on locator failure, retry with another strategy.

A locator breaks when the page changes under a test — e.g. a `data-test`
attribute is renamed. The Healer does not guess: it walks an ordered
candidate list for the same element (data-test -> id/name -> placeholder
or text -> role) and takes the first one that actually matches something
on the page. Every attempt is recorded, before and after, so the run can
report a self-heal rate instead of silently passing.

Verification, two levels:
- In this VM (no browser): `python -m qa_agent.agents.healer --demo`
  runs the broken-locator scenario against a fake page and writes
  `reports/heal-summary.json`; `tests/test_healer.py` covers the same
  logic with unit tests.
- On ren's machine / CI (real Chromium): `tests/test_healer_live.py`
  deliberately drops the `data-test` primaries, heals to the `#id`
  fallbacks, and still logs in — the deliberately-broken-locator proof.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TARGET_URL = "https://www.saucedemo.com/"

# Ordered candidates per login element. First entry is the primary the
# generated tests use; the rest are the fallback chain, most stable first.
# The ids / placeholders / button text below are the real saucedemo DOM
# (same page the hand-written test logs into).
LOGIN_LOCATORS: dict[str, list[str]] = {
    "username": [
        '[data-test="username"]',
        "#user-name",
        'input[name="user-name"]',
        'input[placeholder="Username"]',
        'role=textbox[name="Username"]',
    ],
    "password": [
        '[data-test="password"]',
        "#password",
        'input[name="password"]',
        'input[placeholder="Password"]',
        'role=textbox[name="Password"]',
    ],
    "login-button": [
        '[data-test="login-button"]',
        "#login-button",
        'input[value="Login"]',
        "text=Login",
        'role=button[name="Login"]',
    ],
}


class HealingFailed(Exception):
    """No candidate locator matched anything on the page."""

    def __init__(self, element: str, tried: list[str]) -> None:
        super().__init__(f"healing failed for {element!r}: tried {tried}")
        self.element = element
        self.tried = tried


def resolve(page, candidates: list[str]):
    """Return (locator_str, locator) for the first candidate that matches.

    `page` is duck-typed: anything with `.locator(sel).count()`, so a fake
    page works in unit tests and a real Playwright page works live.
    `count()` does not wait, so a missing candidate costs nothing.
    """
    tried: list[str] = []
    for candidate in candidates:
        tried.append(candidate)
        try:
            locator = page.locator(candidate)
            if locator.count() > 0:
                return candidate, locator, tried
        except PlaywrightError:
            # This candidate errored on the live page (e.g. strict-mode
            # violation); the next fallback still gets its chance.
            continue
    raise HealingFailed(candidates[0] if candidates else "", tried)


def heal(page, element: str, candidates: list[str] | None = None) -> dict:
    """Try to find `element` on `page`; return the before/after record."""
    candidates = list(candidates if candidates is not None else LOGIN_LOCATORS[element])
    record: dict = {
        "element": element,
        "primary": candidates[0] if candidates else None,
        "tried": [],
        "healed_with": None,
        "success": False,
        "attempts": 0,
    }
    try:
        healed_with, locator, tried = resolve(page, candidates)
        record.update(
            {
                "tried": tried,
                "healed_with": healed_with,
                "success": True,
                "attempts": len(tried),
                "locator": locator,
            }
        )
    except HealingFailed as exc:
        record.update({"tried": exc.tried, "attempts": len(exc.tried)})
    return record


def heal_login(page, broken: tuple[str, ...] = ()) -> list[dict]:
    """Heal the three saucedemo login elements on the live login page.

    `broken` names elements whose primary locator is treated as gone —
    the deliberately-broken scenario. Returns one record per element.
    """
    page.goto(TARGET_URL)
    records = []
    for element, candidates in LOGIN_LOCATORS.items():
        usable = candidates[1:] if element in broken else candidates
        record = heal(page, element, usable)
        # The primary stays the data-test locator even when the broken
        # scenario skips it — that is the locator that failed.
        record["primary"] = candidates[0]
        records.append(record)
    return records


def heal_rate(records: list[dict]) -> float:
    """Share of records that healed (0.0 when there is nothing to heal)."""
    if not records:
        return 0.0
    return sum(1 for r in records if r["success"]) / len(records)


def public_record(record: dict) -> dict:
    """A JSON-safe copy of a heal record (drops the live locator object)."""
    return {k: v for k, v in record.items() if k != "locator"}


def write_heal_summary(records: list[dict], path: str | Path) -> Path:
    """Write records + heal rate to JSON; return the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "healed": sum(1 for r in records if r["success"]),
        "total": len(records),
        "heal_rate": heal_rate(records),
        "records": [public_record(r) for r in records],
    }
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


class _FakeLocator:
    """Minimal stand-in for a Playwright locator: matches iff present."""

    def __init__(self, present: bool) -> None:
        self._present = present

    def count(self) -> int:
        return 1 if self._present else 0


class _FakePage:
    """Fake page whose DOM is just the set of selectors that 'exist'."""

    def __init__(self, present: set[str]) -> None:
        self._present = present

    def goto(self, url: str) -> None:
        self.url = url

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(selector in self._present)


def demo_summary(out_path: str | Path) -> dict:
    """Simulate all three data-test attributes removed; heal and report."""
    present = {
        sel
        for candidates in LOGIN_LOCATORS.values()
        for sel in candidates
        if not sel.startswith('[data-test="')
    }
    records = heal_login(_FakePage(present))
    path = write_heal_summary(records, out_path)
    return {"summary_path": str(path), "heal_rate": heal_rate(records), "records": records}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Healer demo (fake page).")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="run the broken-locator demo against a fake page (default mode)",
    )
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "reports" / "heal-summary.json"),
        help="where to write the heal summary JSON",
    )
    args = parser.parse_args()
    result = demo_summary(args.out)
    for record in result["records"]:
        print(
            f"{record['element']}: primary={record['primary']} "
            f"healed_with={record['healed_with']} attempts={record['attempts']}"
        )
    print(f"heal_rate={result['heal_rate']:.2f} summary={result['summary_path']}")


if __name__ == "__main__":
    main()
