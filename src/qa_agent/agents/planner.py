"""Planner agent (Day 3-4): requirement / case YAML -> test strategy.

Deterministic, no LLM call: it derives equivalence classes from the
case file (cases/*.yaml) plus the known login behaviour of the target
site. The strategy is a plain dict so Generator can render it without
guessing.

Day 13-14: the Planner is site-aware. SauceDemo and the-internet share
the login shape (username + password + submit, success URL + error
message) but differ in every concrete value — credentials, locators,
success page and error strings — so plan() dispatches on the case's
target_url and each strategy carries its own locators and messages.
A new site means a new branch here, not a new YAML alone: running the
old SauceDemo-only plan against the-internet would have generated
[data-test=...] locators and an /inventory.html expectation for a page
that has neither.
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

SAUCEDEMO_LOCATORS = {
    "username": '[data-test="username"]',
    "password": '[data-test="password"]',
    "submit": '[data-test="login-button"]',
    "error": '[data-test="error"]',
}

# Messages shown by https://the-internet.herokuapp.com/login — verified
# 2026-11-27 against several independent public write-ups (Robot
# Framework data-driven login, qable.io Playwright run, noalabs Cypress
# and AI-testing guides, all quoting the same strings). The flash bar
# (#flash) carries the message plus a trailing "×" close button, so the
# Generator asserts with to_contain_text, never an exact match.
THE_INTERNET_ERROR_USERNAME_INVALID = "Your username is invalid!"
THE_INTERNET_ERROR_PASSWORD_INVALID = "Your password is invalid!"
THE_INTERNET_SUCCESS_FLASH = "You logged into a secure area!"

THE_INTERNET_LOCATORS = {
    "username": "#username",
    "password": "#password",
    "submit": "button[type=submit]",
    "error": "#flash",
}


def load_case(path: str | Path) -> dict:
    """Read one case YAML file (target_url / requirement / expected)."""
    with open(path, encoding="utf-8") as fh:
        case = yaml.safe_load(fh) or {}
    if not case.get("target_url"):
        raise ValueError(f"{path}: case YAML is missing target_url")
    return case


def plan_saucedemo(case: dict) -> dict:
    """Login strategy for SauceDemo (the original Day 3-4 site)."""
    target_url = case["target_url"]
    return {
        "site": "saucedemo",
        "target_url": target_url,
        "requirement": case.get("requirement", "").strip(),
        "expected": case.get("expected", "").strip(),
        "feature": "login",
        "locators": dict(SAUCEDEMO_LOCATORS),
        "success_flash": None,
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


def plan_the_internet(case: dict) -> dict:
    """Login strategy for the-internet.herokuapp.com (Day 13-14 site).

    Equivalence classes for this login form: valid credentials, wrong
    password, unknown username, empty username. This site has no locked
    user, so the unknown-username class takes that slot. A failed login
    stays on /login; a success lands on /secure with a flash message.
    """
    target_url = case["target_url"]
    base_url = target_url.rstrip("/").removesuffix("/login")
    return {
        "site": "the-internet",
        "target_url": target_url,
        "requirement": case.get("requirement", "").strip(),
        "expected": case.get("expected", "").strip(),
        "feature": "login",
        "locators": dict(THE_INTERNET_LOCATORS),
        "success_flash": THE_INTERNET_SUCCESS_FLASH,
        "classes": [
            {
                "id": "login_success",
                "username": "tomsmith",
                "password": "SuperSecretPassword!",
                "expected_url": f"{base_url}/secure",
                "expected_error": None,
            },
            {
                "id": "login_wrong_password",
                "username": "tomsmith",
                "password": "wrong_password",
                "expected_url": None,
                "expected_error": THE_INTERNET_ERROR_PASSWORD_INVALID,
            },
            {
                "id": "login_wrong_username",
                "username": "wrong_user",
                "password": "SuperSecretPassword!",
                "expected_url": None,
                "expected_error": THE_INTERNET_ERROR_USERNAME_INVALID,
            },
            {
                "id": "login_empty_username",
                "username": "",
                "password": "SuperSecretPassword!",
                "expected_url": None,
                "expected_error": THE_INTERNET_ERROR_USERNAME_INVALID,
            },
        ],
    }


def plan(case: dict) -> dict:
    """Build a login test strategy from a case dict.

    Dispatches on target_url: the-internet.herokuapp.com gets its own
    credentials, locators and messages; anything else keeps the
    SauceDemo strategy (the Day 3-4 default).
    """
    if "the-internet.herokuapp.com" in case.get("target_url", ""):
        return plan_the_internet(case)
    return plan_saucedemo(case)


def plan_from_yaml(path: str | Path) -> dict:
    """Load a case YAML file and return its strategy."""
    return plan(load_case(path))
