"""Healer live test — real Chromium, deliberately broken locators.

Runs on ren's machine or in CI (where Chromium is installed), not in
this VM. All three `data-test` primaries are skipped on purpose; the
Healer must recover each element through its `#id` fallback and the
login must still succeed — that is the deliberately-broken proof.
"""

from playwright.sync_api import Page, expect

from qa_agent.agents.healer import heal_login, heal_rate


def test_healed_login(page: Page):
    records = heal_login(page, broken=("username", "password", "login-button"))
    assert heal_rate(records) == 1.0, records
    assert [r["healed_with"] for r in records] == [
        "#user-name",
        "#password",
        "#login-button",
    ]

    by_element = {r["element"]: r["locator"] for r in records}
    by_element["username"].fill("standard_user")
    by_element["password"].fill("secret_sauce")
    by_element["login-button"].click()
    expect(page).to_have_url("https://www.saucedemo.com/inventory.html")
    expect(page.locator(".title")).to_have_text("Products")
    expect(page.locator(".inventory_item").first).to_be_visible()
