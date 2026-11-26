"""Agent stubs — one file per role, implemented across the 2-week MVP.

Planner: test strategy from requirements (equivalence classes, boundaries, exceptions).
Generator: strategy -> executable pytest + Playwright code (only saved once it passes).
Executor: runs cases via Playwright MCP, keeps trace / screenshots / video.
Healer: on failure, retries with a different locator strategy (max 2), logs before/after.
  Implemented Day 8: ordered fallback chain (data-test -> id/name ->
  placeholder/text -> role) with a recorded heal rate; see agents/healer.py.
Analyzer: classifies failures as product bug / script bug / environment / flaky, with evidence.
  Implemented Day 11: ordered deterministic rules (flaky on retry pass ->
  environment -> script bug -> product bug -> unknown), with a recorded
  flaky rate; see agents/analyzer.py. Wired into graph.py (Executor failure
  -> Analyzer -> Reporter flaky rate) on 2026-11-26; see tests/test_graph_analyzer.py.
Reporter: Allure report + one-page metrics (pass rate, self-heal rate, flaky rate).
"""
