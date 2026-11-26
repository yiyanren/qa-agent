"""Graph wiring tests — Executor failure -> Analyzer -> Reporter flaky rate.

No browser needed: the parser and the analyzer node are fed canned
Executor result dicts (the shape run_pytest() returns). One test runs
the real graph in dry-run mode (collect-only) to prove the new edge
does not break the Day 3 loop.
"""

from qa_agent.agents.analyzer import extract_failures, failures_from_results
from qa_agent.graph import analyzer_node, build_graph

CASE = "cases/saucedemo-login.yaml"
TEST_ID = "tests/test_saucedemo_login.py::test_login_success"


def _failed_results(output: str, returncode: int = 1) -> dict:
    return {"mode": "run", "returncode": returncode, "output_tail": output}


def test_extract_product_bug_from_failed_line():
    failures = extract_failures(
        f"FAILED {TEST_ID} - AssertionError: "
        "expect(page.locator('.title')).to_have_text('Products') failed"
    )
    assert len(failures) == 1
    assert failures[0]["test"] == TEST_ID
    assert failures[0]["error_type"] == "AssertionError"
    analysis = analyzer_node(
        {
            "results": _failed_results(
                f"FAILED {TEST_ID} - AssertionError: "
                "expect(page.locator('.title')).to_have_text('Products') failed"
            )
        }
    )["analysis"]
    assert analysis["total"] == 1
    assert analysis["by_category"]["product_bug"] == 1
    assert analysis["flaky_rate"] == 0.0


def test_extract_script_bug_and_environment():
    output = (
        f"FAILED {TEST_ID} - TimeoutError: "
        "Timeout 30000ms exceeded waiting for locator('[data-test=\"username\"]')\n"
        "FAILED tests/test_saucedemo_login.py::test_login_locked_out - Error: "
        "net::ERR_NAME_NOT_RESOLVED at https://www.saucedemo.com/\n"
    )
    analysis = analyzer_node({"results": _failed_results(output)})["analysis"]
    assert analysis["total"] == 2
    assert analysis["by_category"]["script_bug"] == 1
    assert analysis["by_category"]["environment"] == 1


def test_extract_dedupes_repeated_failed_lines():
    output = (
        f"FAILED {TEST_ID} - AssertionError: to_have_text failed\n"
        f"FAILED {TEST_ID} - AssertionError: to_have_text failed\n"
    )
    assert len(extract_failures(output)) == 1


def test_extract_failed_line_without_summary_is_unknown():
    failures = extract_failures(f"FAILED {TEST_ID}\n")
    assert len(failures) == 1
    assert failures[0]["error"] == ""
    analysis = analyzer_node({"results": _failed_results(f"FAILED {TEST_ID}\n")})["analysis"]
    assert analysis["by_category"]["unknown"] == 1


def test_green_run_has_zero_failures():
    assert failures_from_results({"mode": "run", "returncode": 0, "output_tail": ""}) == []
    analysis = analyzer_node({"results": {"mode": "run", "returncode": 0, "output_tail": ""}})[
        "analysis"
    ]
    assert analysis["total"] == 0
    assert analysis["flaky_rate"] == 0.0
    assert all(v == 0 for v in analysis["by_category"].values())


def test_failed_run_without_failed_lines_is_one_unknown():
    analysis = analyzer_node(
        {"results": _failed_results("ERROR: collection failed, no tests ran\n")}
    )["analysis"]
    assert analysis["total"] == 1
    assert analysis["by_category"]["unknown"] == 1
    assert analysis["records"][0]["error"] == "ERROR: collection failed, no tests ran"


def test_graph_dry_run_reports_zero_failures(tmp_path):
    out = tmp_path / "test_saucedemo_login_generated.py"
    result = build_graph().invoke({"case_path": CASE, "out_path": str(out), "dry_run": True})
    assert result["results"]["returncode"] == 0
    assert result["analysis"]["total"] == 0
    assert result["analysis"]["flaky_rate"] == 0.0
    assert result["summary_path"].endswith("summary.json")
    assert result["analysis_path"].endswith("analysis-summary.json")
