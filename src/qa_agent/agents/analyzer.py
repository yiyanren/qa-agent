"""Analyzer agent (Day 11-12): classify failures — product bug / script bug / environment / flaky.

A failed test does not say why it failed, so the Analyzer reads the
failure record — test name, error type, error message, and whether it
passed on retry — and applies ordered, deterministic rules. No LLM, no
browser: the same input always gives the same category, so the
classification itself is testable with plain dicts.

Rule order (first match wins; the order is the point):
1. flaky — the same test passed on retry with nothing changed. A retry
   pass beats whatever the error text says, because the error did not
   reproduce.
2. environment — the run could not reach or start what it needed:
   DNS / connection errors, `net::ERR_*`, a navigation timeout, or a
   browser that failed to launch / was closed. Nothing about the test
   or the product can be concluded from these.
3. script bug — the test itself is wrong: a locator that matches
   nothing (timeout waiting for a selector/locator), a strict-mode
   violation (locator matches more than one element), or a test-code
   error (NameError / SyntaxError / missing import / missing fixture).
4. product bug — the page was reached and the element was found, but
   the app behaved differently from the expectation: `expect(...).to_have_text`,
   `to_have_url` or `to_be_visible` failed, or an `AssertionError` on
   app state. Confidence is medium here, not high: a wrong expectation
   written into the test looks identical, so the record says to check
   the expected value against the spec first.
5. unknown — nothing matched. Labelled honestly instead of forced into
   one of the four, with low confidence.

Each record carries its evidence (the pattern that matched) and a
suggested next step, so a human can disagree with the label by reading
one line instead of the whole traceback.

Verification, two levels (same split as Healer):
- In this VM (no browser): `python -m qa_agent.agents.analyzer --demo`
  classifies five representative failures (one per category plus an
  unknown) and writes `reports/analysis-summary.json`;
  `tests/test_analyzer.py` covers the same rules with unit tests.
- On ren's machine / CI (real runs): feed real pytest failures in —
  see `classify()`'s input shape — the rules are the same code.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Categories the Analyzer can return. "unknown" is a real outcome: it
# means no rule matched, and it is reported with low confidence rather
# than guessed.
CATEGORIES = ("product_bug", "script_bug", "environment", "flaky", "unknown")

# Next step per category, for the record and the report.
SUGGESTIONS = {
    "product_bug": "确认期望值与需求/页面实际行为是否一致，再提 Bug（附期望与实际）。",
    "script_bug": "修测试代码：定位器、断言期望或 fixture，修完本地重跑该用例。",
    "environment": "先修环境再重跑：网络、Chromium 安装、浏览器启动，不要改用例。",
    "flaky": "不改用例不改产品：多跑几次确认复现率，定位竞态/等待问题后再修。",
    "unknown": "贴完整报错人工看：先补全 error_type 与 error 再重新分类。",
}

# Each rule is (compiled pattern, category, confidence, reason).
# Patterns are matched against "error_type: error" lower-cased, so a
# bare message and a full traceback line classify the same way.
_ENVIRONMENT_PATTERNS = [
    (r"net::err_", "network error (net::ERR_*)"),
    (
        r"err_name_not_resolved|err_connection_refused|err_connection_reset|err_connection_timed_out",
        "network error (DNS / connection refused / reset)",
    ),
    (
        (
            r"connection refused|connection reset by peer|temporary failure in name resolution|"
            r"name or service not known|failed to establish a new connection"
        ),
        "network error (could not reach the site)",
    ),
    (
        (
            r"executable doesn't exist|browser executable|playwright install|"
            r"target page, context or browser has been closed|browser has been closed"
        ),
        "browser failed to launch or was closed",
    ),
    (r"timeout.*(goto|navigat|wait_for_load_state|page\.goto)", "navigation timed out"),
]

_SCRIPT_PATTERNS = [
    (
        (
            r"strict mode violation|locator.*resolved to (0|more than one)|"
            r"strict mode violation.*locator"
        ),
        "locator is ambiguous or matches nothing (strict mode)",
    ),
    (
        (
            r"waiting for (selector|locator)|timeout.*waiting for.*(selector|locator)|"
            r"locator\(.*\) .*not found|element is not attached"
        ),
        "locator matched nothing on the page",
    ),
    (r"fixture .*not found|no such fixture", "missing pytest fixture"),
    (
        r"nameerror|syntaxerror|indentationerror|modulenotfounderror|importerror",
        "test code error (name / syntax / import)",
    ),
]

# Product patterns only fire on expect()/assertion failures about app
# state — the page loaded and the element was found, but the value was
# wrong. A bare AssertionError with no expect() wording falls through
# to the generic product rule below (medium confidence).
_PRODUCT_PATTERNS = [
    (
        (
            r"to_have_text|to_have_url|to_be_visible|to_have_value|to_have_title|"
            r"to_contain_text|expected:.*actual:|assertionerror"
        ),
        "assertion on app behaviour failed (element found, value wrong)",
    ),
]


def _search_text(failure: dict) -> str:
    """One lower-cased string to match rules against."""
    error_type = str(failure.get("error_type") or "")
    error = str(failure.get("error") or "")
    return f"{error_type}: {error}".lower()


def _match(patterns: list[tuple[str, str]], text: str) -> tuple[str, str] | None:
    for pattern, reason in patterns:
        if re.search(pattern, text):
            return pattern, reason
    return None


def classify(failure: dict) -> dict:
    """Classify one failure record; return the record with a category.

    Input shape (all fields optional except the error text):
        {"test": "...", "error_type": "TimeoutError",
         "error": "...", "passed_on_retry": False}
    Output adds: category, confidence ("high" / "medium" / "low"),
    reason, evidence (the pattern that matched, or ""), suggestion.
    """
    test = str(failure.get("test") or "")
    text = _search_text(failure)
    record: dict = {
        "test": test,
        "error_type": str(failure.get("error_type") or ""),
        "error": str(failure.get("error") or ""),
        "passed_on_retry": bool(failure.get("passed_on_retry", False)),
        "category": "unknown",
        "confidence": "low",
        "reason": "no rule matched this failure",
        "evidence": "",
        "suggestion": SUGGESTIONS["unknown"],
    }
    if not text.strip(": "):
        return record

    # 1. Flaky beats the error text: it passed on retry unchanged.
    if record["passed_on_retry"]:
        record.update(
            {
                "category": "flaky",
                "confidence": "high",
                "reason": "failed, then passed on retry with nothing changed",
                "evidence": "passed_on_retry=true",
                "suggestion": SUGGESTIONS["flaky"],
            }
        )
        return record

    # 2. Environment: could not reach / start what the run needed.
    hit = _match(_ENVIRONMENT_PATTERNS, text)
    if hit:
        pattern, reason = hit
        record.update(
            {
                "category": "environment",
                "confidence": "high",
                "reason": reason,
                "evidence": pattern,
                "suggestion": SUGGESTIONS["environment"],
            }
        )
        return record

    # 3. Script bug: the test itself is wrong.
    hit = _match(_SCRIPT_PATTERNS, text)
    if hit:
        pattern, reason = hit
        record.update(
            {
                "category": "script_bug",
                "confidence": "high",
                "reason": reason,
                "evidence": pattern,
                "suggestion": SUGGESTIONS["script_bug"],
            }
        )
        return record

    # 4. Product bug: app state differed from the expectation. Medium
    # confidence — a wrong expectation in the test looks the same.
    hit = _match(_PRODUCT_PATTERNS, text)
    if hit:
        pattern, reason = hit
        record.update(
            {
                "category": "product_bug",
                "confidence": "medium",
                "reason": reason + " — check the expected value against the spec",
                "evidence": pattern,
                "suggestion": SUGGESTIONS["product_bug"],
            }
        )
        return record

    return record


def analyze(failures: list[dict]) -> dict:
    """Classify every failure; return records plus counts and flaky rate."""
    records = [classify(f) for f in failures]
    by_category = {c: 0 for c in CATEGORIES}
    for r in records:
        by_category[r["category"]] += 1
    total = len(records)
    return {
        "total": total,
        "by_category": by_category,
        "flaky_rate": (by_category["flaky"] / total) if total else 0.0,
        "records": records,
    }


def write_analysis_summary(analysis: dict, path: str | Path) -> Path:
    """Write an analysis result to JSON; return the path."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def demo_failures() -> list[dict]:
    """Five representative failures: one per category, plus an unknown.

    Each one is shaped like a real failure from this repo's saucedemo
    login tests, so the demo doubles as documentation of the rules.
    """
    return [
        {
            "test": "tests/test_saucedemo_login.py::test_login_success",
            "error_type": "AssertionError",
            "error": (
                "expect(page.locator('.title')).to_have_text('Products') "
                "failed: expected 'Products', actual 'Swag Labs'"
            ),
        },
        {
            "test": "tests/test_saucedemo_login.py::test_login_success",
            "error_type": "TimeoutError",
            "error": "Timeout 30000ms exceeded waiting for locator('[data-test=\"username\"]')",
        },
        {
            "test": "tests/test_saucedemo_login.py::test_login_success",
            "error_type": "Error",
            "error": "net::ERR_NAME_NOT_RESOLVED at https://www.saucedemo.com/",
        },
        {
            "test": "tests/test_saucedemo_login.py::test_login_success",
            "error_type": "AssertionError",
            "error": "expect(page).to_have_url('https://www.saucedemo.com/inventory.html') failed",
            "passed_on_retry": True,
        },
        {
            "test": "tests/test_saucedemo_login.py::test_login_success",
            "error_type": "RuntimeError",
            "error": "something unexpected happened with no matching rule",
        },
    ]


def demo_summary(out_path: str | Path) -> dict:
    """Classify the demo failures and write the summary JSON."""
    analysis = analyze(demo_failures())
    path = write_analysis_summary(analysis, out_path)
    return {"summary_path": str(path), **analysis}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Analyzer demo (no browser).")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="classify five representative failures (default mode)",
    )
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "reports" / "analysis-summary.json"),
        help="where to write the analysis summary JSON",
    )
    args = parser.parse_args()
    result = demo_summary(args.out)
    for record in result["records"]:
        print(
            f"{record['test'].split('::')[-1]}: {record['category']} "
            f"({record['confidence']}) — {record['reason']}"
        )
    print(
        f"total={result['total']} by_category={result['by_category']} "
        f"flaky_rate={result['flaky_rate']:.2f} summary={result['summary_path']}"
    )


if __name__ == "__main__":
    main()
