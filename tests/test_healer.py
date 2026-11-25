"""Healer unit tests — fake page, no browser needed.

The fake page's DOM is the set of selectors that 'exist', so a broken
primary is simulated by leaving the data-test selector out of the set.
"""

import json

import pytest

from qa_agent.agents.healer import (
    LOGIN_LOCATORS,
    _FakePage,
    demo_summary,
    heal,
    heal_login,
    heal_rate,
    resolve,
    write_heal_summary,
)


def _page_with(*present: str) -> _FakePage:
    return _FakePage(set(present))


def test_primary_works_no_healing_needed():
    page = _page_with(*LOGIN_LOCATORS["username"])
    record = heal(page, "username")
    assert record["success"] is True
    assert record["healed_with"] == '[data-test="username"]'
    assert record["attempts"] == 1


def test_broken_primary_heals_via_id():
    present = [s for s in LOGIN_LOCATORS["username"] if not s.startswith('[data-test="')]
    page = _page_with(*present)
    record = heal(page, "username")
    assert record["success"] is True
    assert record["healed_with"] == "#user-name"
    assert record["tried"] == ['[data-test="username"]', "#user-name"]
    assert record["attempts"] == 2


def test_button_falls_through_to_role():
    # Only the role candidate survives: data-test, id, value and text gone.
    page = _page_with('role=button[name="Login"]')
    record = heal(page, "login-button")
    assert record["success"] is True
    assert record["healed_with"] == 'role=button[name="Login"]'
    assert record["attempts"] == 5


def test_nothing_matches_records_failure():
    page = _page_with()
    record = heal(page, "password")
    assert record["success"] is False
    assert record["healed_with"] is None
    assert record["attempts"] == len(LOGIN_LOCATORS["password"])
    assert record["tried"] == LOGIN_LOCATORS["password"]


def test_resolve_returns_first_matching_locator():
    page = _page_with("#user-name")
    selector, locator, tried = resolve(page, LOGIN_LOCATORS["username"])
    assert selector == "#user-name"
    assert locator.count() == 1
    assert tried == ['[data-test="username"]', "#user-name"]


def test_heal_rate_two_of_three():
    records = [
        {"success": True},
        {"success": True},
        {"success": False},
    ]
    assert heal_rate(records) == pytest.approx(2 / 3)
    assert heal_rate([]) == 0.0


def test_heal_login_demo_all_broken_data_test():
    # data-test attributes removed from the page: all three heal via #id.
    present = {
        sel
        for candidates in LOGIN_LOCATORS.values()
        for sel in candidates
        if not sel.startswith('[data-test="')
    }
    records = heal_login(_FakePage(present))
    assert len(records) == 3
    assert all(r["success"] for r in records)
    assert [r["healed_with"] for r in records] == [
        "#user-name",
        "#password",
        "#login-button",
    ]
    assert heal_rate(records) == 1.0


def test_write_heal_summary_is_json_safe(tmp_path):
    present = {
        sel
        for candidates in LOGIN_LOCATORS.values()
        for sel in candidates
        if not sel.startswith('[data-test="')
    }
    records = heal_login(_FakePage(present))
    path = write_heal_summary(records, tmp_path / "heal-summary.json")
    summary = json.loads(path.read_text(encoding="utf-8"))
    assert summary["healed"] == 3
    assert summary["total"] == 3
    assert summary["heal_rate"] == 1.0
    assert summary["records"][0]["element"] == "username"
    assert "locator" not in summary["records"][0]


def test_demo_summary_writes_file(tmp_path):
    result = demo_summary(tmp_path / "heal-summary.json")
    assert result["heal_rate"] == 1.0
    assert result["records"][0]["healed_with"] == "#user-name"
