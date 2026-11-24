"""First executable case (Milestone 1): saucedemo login succeeds.

Target: https://www.saucedemo.com/ — standard_user / secret_sauce.
Keeps a screenshot in reports/ on failure; trace is recorded via
pytest-playwright when run with --tracing on (see README).
"""
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.smoke
def test_login_success(page: Page):
    page.goto("https://www.saucedemo.com/")
    page.locator('[data-test="username"]').fill("standard_user")
    page.locator('[data-test="password"]').fill("secret_sauce")
    page.locator('[data-test="login-button"]').click()
    expect(page).to_have_url("https://www.saucedemo.com/inventory.html")
    expect(page.locator(".title")).to_have_text("Products")
    expect(page.locator(".inventory_item").first).to_be_visible()
