"""Analyzer unit tests — plain failure dicts, no browser needed.

Each test feeds one representative failure record (shaped like a real
saucedemo login failure) and asserts the category, confidence and
evidence the rule should produce.
"""

import json

import pytest

from qa_agent.agents.analyzer import (
    analyze,
    classify,
    demo_failures,
    demo_summary,
)


def _failure(error: str, error_type: str = "AssertionError", **extra) -> dict:
    return {
        "test": "tests/test_saucedemo_login.py::test_login_success",
        "error_type": error_type,
        "error": error,
        **extra,
    }


def test_product_bug_text_mismatch():
    record = classify(
        _failure(
            "expect(page.locator('.title')).to_have_text('Products') failed: "
            "expected 'Products', actual 'Swag Labs'"
        )
    )
    assert record["category"] == "product_bug"
    assert record["confidence"] == "medium"
    assert "spec" in record["reason"]
    assert record["suggestion"]


def test_product_bug_url_mismatch():
    record = classify(
        _failure("expect(page).to_have_url('https://www.saucedemo.com/inventory.html') failed")
    )
    assert record["category"] == "product_bug"
    assert record["confidence"] == "medium"


def test_script_bug_locator_timeout():
    record = classify(
        _failure(
            "Timeout 30000ms exceeded waiting for locator('[data-test=\"username\"]')",
            error_type="TimeoutError",
        )
    )
    assert record["category"] == "script_bug"
    assert record["confidence"] == "high"
    assert "locator" in record["reason"]


def test_script_bug_strict_mode_violation():
    record = classify(
        _failure(
            "strict mode violation: locator('.inventory_item') resolved to 6 elements",
            error_type="Error",
        )
    )
    assert record["category"] == "script_bug"
    assert record["confidence"] == "high"


def test_script_bug_test_code_name_error():
    record = classify(_failure("name 'standard_user' is not defined", error_type="NameError"))
    assert record["category"] == "script_bug"
    assert record["confidence"] == "high"


def test_environment_dns_failure():
    record = classify(
        _failure("net::ERR_NAME_NOT_RESOLVED at https://www.saucedemo.com/", error_type="Error")
    )
    assert record["category"] == "environment"
    assert record["confidence"] == "high"


def test_environment_browser_not_installed():
    record = classify(
        _failure(
            "Executable doesn't exist at ~/.cache/ms-playwright/chromium-1181/chrome-linux/chrome",
            error_type="Error",
        )
    )
    assert record["category"] == "environment"
    assert record["confidence"] == "high"


def test_environment_navigation_timeout_beats_locator_rule():
    # A TimeoutError on goto is the environment's fault, not the test's:
    # the navigation rule must win over any locator wording in the text.
    record = classify(
        _failure(
            "Timeout 30000ms exceeded waiting for page.goto('https://www.saucedemo.com/')",
            error_type="TimeoutError",
        )
    )
    assert record["category"] == "environment"


def test_flaky_passed_on_retry_beats_error_text():
    # Same product-looking assertion, but it passed on retry unchanged:
    # flaky wins over the error text.
    record = classify(
        _failure(
            "expect(page).to_have_url('https://www.saucedemo.com/inventory.html') failed",
            passed_on_retry=True,
        )
    )
    assert record["category"] == "flaky"
    assert record["confidence"] == "high"
    assert record["evidence"] == "passed_on_retry=true"


def test_unknown_when_no_rule_matches():
    record = classify(_failure("something unexpected happened", error_type="RuntimeError"))
    assert record["category"] == "unknown"
    assert record["confidence"] == "low"
    assert record["suggestion"]


def test_empty_failure_is_unknown():
    assert classify({})["category"] == "unknown"
    assert classify({"test": "x", "error": ""})["category"] == "unknown"


def test_analyze_counts_and_flaky_rate():
    analysis = analyze(demo_failures())
    assert analysis["total"] == 5
    assert analysis["by_category"] == {
        "product_bug": 1,
        "script_bug": 1,
        "environment": 1,
        "flaky": 1,
        "unknown": 1,
    }
    assert analysis["flaky_rate"] == pytest.approx(1 / 5)
    assert analyze([]) == {
        "total": 0,
        "by_category": {
            c: 0 for c in ("product_bug", "script_bug", "environment", "flaky", "unknown")
        },
        "flaky_rate": 0.0,
        "records": [],
    }


def test_demo_summary_writes_file(tmp_path):
    result = demo_summary(tmp_path / "analysis-summary.json")
    assert result["total"] == 5
    assert result["flaky_rate"] == pytest.approx(1 / 5)
    summary = json.loads((tmp_path / "analysis-summary.json").read_text(encoding="utf-8"))
    assert summary["by_category"]["product_bug"] == 1
    assert summary["records"][0]["category"] == "product_bug"
    assert summary["records"][0]["suggestion"]
