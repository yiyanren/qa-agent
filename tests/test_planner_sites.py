"""Planner / Generator site-awareness (Day 13-14): no browser needed.

Guards the two things a second site can silently break: the Planner
must not hand the-internet the SauceDemo credentials, locators and
error strings, and the Generator must not render [data-test=...]
locators or an /inventory.html expectation for a page that has neither.
"""

from qa_agent.agents.generator import render_login_tests
from qa_agent.agents.planner import plan_from_yaml

SAUCEDEMO_CASE = "cases/saucedemo-login.yaml"
THE_INTERNET_CASE = "cases/the-internet-login.yaml"


def test_plan_saucedemo_unchanged():
    strategy = plan_from_yaml(SAUCEDEMO_CASE)
    assert strategy["site"] == "saucedemo"
    assert [c["id"] for c in strategy["classes"]] == [
        "login_success",
        "login_wrong_password",
        "login_locked_out",
        "login_empty_username",
    ]
    success = strategy["classes"][0]
    assert (success["username"], success["password"]) == ("standard_user", "secret_sauce")
    assert success["expected_url"] == "https://www.saucedemo.com/inventory.html"
    assert strategy["locators"]["username"] == '[data-test="username"]'


def test_plan_the_internet_classes():
    strategy = plan_from_yaml(THE_INTERNET_CASE)
    assert strategy["site"] == "the-internet"
    assert [c["id"] for c in strategy["classes"]] == [
        "login_success",
        "login_wrong_password",
        "login_wrong_username",
        "login_empty_username",
    ]
    success = strategy["classes"][0]
    assert (success["username"], success["password"]) == (
        "tomsmith",
        "SuperSecretPassword!",
    )
    assert success["expected_url"] == "https://the-internet.herokuapp.com/secure"
    assert strategy["success_flash"] == "You logged into a secure area!"
    by_id = {c["id"]: c for c in strategy["classes"]}
    assert by_id["login_wrong_password"]["expected_error"] == "Your password is invalid!"
    assert by_id["login_wrong_username"]["expected_error"] == "Your username is invalid!"
    assert by_id["login_empty_username"]["expected_error"] == "Your username is invalid!"
    assert strategy["locators"] == {
        "username": "#username",
        "password": "#password",
        "submit": "button[type=submit]",
        "error": "#flash",
    }


def test_generator_renders_the_internet_locators_and_flash():
    rendered = render_login_tests(plan_from_yaml(THE_INTERNET_CASE))
    assert "#username" in rendered and "button[type=submit]" in rendered
    assert "to_contain_text" in rendered
    assert "data-test" not in rendered and "inventory.html" not in rendered
    assert "You logged into a secure area!" in rendered


def test_generator_renders_saucedemo_exactly_as_before():
    rendered = render_login_tests(plan_from_yaml(SAUCEDEMO_CASE))
    assert '[data-test="username"]' in rendered
    assert "to_have_text(expected_error)" in rendered
    assert "the-internet" not in rendered
