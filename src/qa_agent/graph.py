"""LangGraph main graph: Planner -> Generator -> Executor -> Analyzer -> Reporter.

Day 3 wiring (Healer and Analyzer land Day 8-12). The graph is
deterministic and needs no LLM key: Planner derives equivalence classes
from a case YAML, Generator renders a parametrized pytest file, Executor
collects it (dry-run) or runs it (full run, needs Chromium), Analyzer
classifies any failures from the Executor output (green runs analyse to
zero failures), and Reporter writes reports/summary.json including the
flaky rate.

Run it:
    python -m qa_agent.graph --case cases/saucedemo-login.yaml --dry-run
    python -m qa_agent.graph --case cases/saucedemo-login.yaml   # full run
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from qa_agent.agents.analyzer import analyze, failures_from_results, write_analysis_summary
from qa_agent.agents.executor import run_pytest
from qa_agent.agents.generator import generate
from qa_agent.agents.planner import plan_from_yaml
from qa_agent.agents.reporter import write_summary

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASE = PROJECT_ROOT / "cases" / "saucedemo-login.yaml"
DEFAULT_OUT = PROJECT_ROOT / "tests" / "generated" / "test_saucedemo_login_generated.py"


class GraphState(TypedDict, total=False):
    case_path: str
    out_path: str
    dry_run: bool
    strategy: dict
    generated_files: list[str]
    results: dict
    analysis: dict
    analysis_path: str
    summary_path: str


def planner_node(state: GraphState) -> GraphState:
    return {"strategy": plan_from_yaml(state["case_path"])}


def generator_node(state: GraphState) -> GraphState:
    out = generate(state["strategy"], state["out_path"])
    return {"generated_files": [str(out)]}


def executor_node(state: GraphState) -> GraphState:
    return {"results": run_pytest(state["generated_files"], dry_run=state["dry_run"])}


def analyzer_node(state: GraphState) -> GraphState:
    """Classify Executor failures; a green run analyses to zero failures."""
    analysis = analyze(failures_from_results(state["results"]))
    path = write_analysis_summary(analysis, PROJECT_ROOT / "reports" / "analysis-summary.json")
    return {"analysis": analysis, "analysis_path": str(path)}


def reporter_node(state: GraphState) -> GraphState:
    summary = {
        "case": state["case_path"],
        "strategy_classes": [c["id"] for c in state["strategy"]["classes"]],
        "generated_files": state["generated_files"],
        "results": state["results"],
        "analysis": {
            "total": state["analysis"]["total"],
            "by_category": state["analysis"]["by_category"],
            "flaky_rate": state["analysis"]["flaky_rate"],
        },
        "analysis_path": state["analysis_path"],
    }
    path = write_summary(summary)
    return {"summary_path": str(path)}


def build_graph():
    """Build and compile the Planner -> Generator -> Executor -> Analyzer -> Reporter graph."""
    graph = StateGraph(GraphState)
    graph.add_node("planner", planner_node)
    graph.add_node("generator", generator_node)
    graph.add_node("executor", executor_node)
    graph.add_node("analyzer", analyzer_node)
    graph.add_node("reporter", reporter_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "generator")
    graph.add_edge("generator", "executor")
    graph.add_edge("executor", "analyzer")
    graph.add_edge("analyzer", "reporter")
    graph.add_edge("reporter", END)
    return graph.compile()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the qa-agent graph.")
    parser.add_argument("--case", default=str(DEFAULT_CASE))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="collect-only: verify generated code without a browser",
    )
    args = parser.parse_args()
    result = build_graph().invoke(
        {"case_path": args.case, "out_path": args.out, "dry_run": args.dry_run}
    )
    print(f"generated: {result['generated_files']}")
    print(
        f"executor: mode={result['results']['mode']} returncode={result['results']['returncode']}"
    )
    print(
        f"analyzer: total={result['analysis']['total']} "
        f"by_category={result['analysis']['by_category']} "
        f"flaky_rate={result['analysis']['flaky_rate']:.2f}"
    )
    print(f"summary: {result['summary_path']}")


if __name__ == "__main__":
    main()
