"""First executable case for the second site (Day 13-14): the-internet login succeeds.

Target: https://the-internet.herokuapp.com/login — tomsmith / SuperSecretPassword!.
The flash bar (#flash) carries the message plus a trailing "×" close button,
so the success message is asserted with to_contain_text, not an exact match.
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.smoke
def test_login_success(page: Page):
    page.goto("https://the-internet.herokuapp.com/login")
    page.locator("#username").fill("tomsmith")
    page.locator("#password").fill("SuperSecretPassword!")
    page.locator("button[type=submit]").click()
    expect(page).to_have_url("https://the-internet.herokuapp.com/secure")
    expect(page.locator("#flash")).to_contain_text("You logged into a secure area!")
