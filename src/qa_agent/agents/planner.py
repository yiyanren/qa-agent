"""Planner agent (Day 3-4): requirement / case YAML -> test strategy.

Deterministic, no LLM call: it derives equivalence classes from the
case file (cases/*.yaml) plus the known SauceDemo login behaviour.
The strategy is a plain dict so Generator can render it without guessing.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# Error strings shown by https://www.saucedemo.com/ — verified against
# public write-ups (e.g. sqatools.in Playwright fixtures lesson and the
# dev.to AI-reporter walkthrough, both quoting the exact strings).
ERROR_WRONG_CREDENTIALS = (
    "Epic sadface: Username and password do not match any user in this service"
)
ERROR_LOCKED_OUT = "Epic sadface: Sorry, this user has been locked out."
ERROR_USERNAME_REQUIRED = "Epic sadface: Username is required"


def load_case(path: str | Path) -> dict:
    """Read one case YAML file (target_url / requirement / expected)."""
    with open(path, encoding="utf-8") as fh:
        case = yaml.safe_load(fh) or {}
    if not case.get("target_url"):
        raise ValueError(f"{path}: case YAML is missing target_url")
    return case


def plan(case: dict) -> dict:
    """Build a login test strategy from a case dict.

    Equivalence classes for the SauceDemo login form:
    valid credentials, wrong password, locked-out user, empty username.
    """
    target_url = case["target_url"]
    return {
        "target_url": target_url,
        "requirement": case.get("requirement", "").strip(),
        "expected": case.get("expected", "").strip(),
        "feature": "login",
        "classes": [
            {
                "id": "login_success",
                "username": "standard_user",
                "password": "secret_sauce",
                "expected_url": f"{target_url.rstrip('/')}/inventory.html",
                "expected_error": None,
            },
            {
                "id": "login_wrong_password",
                "username": "standard_user",
                "password": "wrong_password",
                "expected_url": None,
                "expected_error": ERROR_WRONG_CREDENTIALS,
            },
            {
                "id": "login_locked_out",
                "username": "locked_out_user",
                "password": "secret_sauce",
                "expected_url": None,
                "expected_error": ERROR_LOCKED_OUT,
            },
            {
                "id": "login_empty_username",
                "username": "",
                "password": "secret_sauce",
                "expected_url": None,
                "expected_error": ERROR_USERNAME_REQUIRED,
            },
        ],
    }


def plan_from_yaml(path: str | Path) -> dict:
    """Load a case YAML file and return its strategy."""
    return plan(load_case(path))
