import { test, expect } from "@playwright/test";

const EMAIL = `e2e-${Date.now()}@example.com`;
const PASSWORD = "e2e-test-passphrase-123";

test("login → dashboard → weekly view submit → portfolio → logout", async ({ page }) => {
  // unauthenticated root redirects to login
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);

  // register (demo policy) then login via the UI form
  await page.goto("/login");
  await page.getByLabel(/Email/i).fill(EMAIL);
  await page.getByLabel(/Password/i).fill(PASSWORD);
  // registration happens out-of-band through the API (no public signup UI)
  const reg = await page.request.post("http://localhost:3000/api/v1/auth/register", {
    data: { email: EMAIL, password: PASSWORD, display_name: "E2E User" },
  });
  expect(reg.status()).toBe(201);
  await page.getByRole("button", { name: "로그인" }).click();
  // New users are redirected to setup, then to dashboard after selection
  await page.waitForURL(/\/(dashboard|setup\/portfolio)/, { timeout: 60000 });
  if (page.url().includes("/setup/portfolio")) {
    await expect(page.locator("h1", { hasText: "Portfolio Setup" })).toBeVisible();
    // Move slider a bit and select
    const slider = page.getByLabel("위험 수준");
    await slider.fill("25");
    await page.getByRole("button", { name: "이 포트폴리오로 시작" }).click();
    await page.getByRole("button", { name: "설정" }).click();
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 60000 });
  } else {
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 60000 });
  }

  // dashboard renders (pre-launch empty states are acceptable)
  await expect(page.locator("h1", { hasText: "Dashboard" })).toBeVisible();

  // weekly view: select a theme and submit (if themes available)
  await page.goto("/views");
  await expect(page.locator("h1", { hasText: "Weekly View" })).toBeVisible({ timeout: 15000 });
  const ai = page.getByRole("button", { name: /^AI/ });
  if (await ai.count() > 0) {
    await ai.first().click();
    await page.getByPlaceholder(/이유를 간단히 입력/).fill("e2e reason");
    await page.getByRole("button", { name: "View 제출" }).click();
    await expect(page.getByText("제출 완료")).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/cycle \d{4}\.\d{2}\.\d{2}/)).toBeVisible();
  }

  // portfolio renders allocation
  await page.goto("/portfolio");
  await expect(page.locator("h1", { hasText: "Portfolio" })).toBeVisible();

  // logout returns to login
  await page.goto("/account");
  await page.getByRole("button", { name: "Logout" }).click();
  await expect(page).toHaveURL(/\/login/);
});
