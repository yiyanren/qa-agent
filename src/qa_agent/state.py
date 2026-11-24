"""Global state shared by the six agents.

Day 1: plain dataclass, no LangGraph dependency yet — the graph wiring
lands in graph.py on Day 3 once Planner -> Generator is built.
"""
from dataclasses import dataclass, field


@dataclass
class TestState:
    requirement: str = ""
    target_url: str = ""
    strategy: str = ""
    cases: list[str] = field(default_factory=list)
    results: list[dict] = field(default_factory=list)
    fixes: list[dict] = field(default_factory=list)
