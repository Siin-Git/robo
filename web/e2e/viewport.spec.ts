import { test, expect } from "@playwright/test";

const EMAIL = `vp-${Date.now()}@example.com`;
const PASSWORD = "viewport-passphrase-123";

const WIDTHS = [1440, 1024, 768, 390];
const PAGES = ["/dashboard", "/portfolio", "/views", "/performance", "/ranking", "/login"];

test("no horizontal page overflow at 1440/1024/768/390", async ({ page }) => {
  test.setTimeout(240_000);
  await page.goto("/login");
  await page.request.post("http://localhost:3000/api/v1/auth/register", {
    data: { email: EMAIL, password: PASSWORD, display_name: "Viewport" },
  });
  await page.getByLabel(/Email/i).fill(EMAIL);
  await page.getByLabel(/Password/i).fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 60000 });
  for (const w of WIDTHS) {
    await page.setViewportSize({ width: w, height: 900 });
    for (const p of PAGES) {
      await page.goto(p, { waitUntil: "domcontentloaded", timeout: 45000 });
      await page.waitForLoadState("networkidle", { timeout: 30000 }).catch(() => {});
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${p} @${w}px`).toBeLessThanOrEqual(1);
    }
  }
});
