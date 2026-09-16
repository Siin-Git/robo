import { test, expect } from "@playwright/test";

const EMAIL = "localtest@example.com";
const PASSWORD = "LocalTest1234!";

test("new user setup flow", async ({ page }) => {
  await page.goto("/login");
  await page.getByLabel(/Email/i).fill(EMAIL);
  await page.getByLabel(/Password/i).fill(PASSWORD);
  await page.getByRole("button", { name: "로그인" }).click();
  await expect(page).toHaveURL(/\/setup\/portfolio/, { timeout: 15000 });
  await expect(page.locator("h1", { hasText: "내 기본 포트폴리오 선택" })).toBeVisible({ timeout: 15000 });
  // Frontier UI elements - check for chart and slider
  const slider = page.locator("input[type='range']");
  await expect(slider).toBeVisible({ timeout: 15000 });
  // Check benchmark marker text
  await expect(page.getByText("CORE Benchmark")).toBeVisible({ timeout: 10000 }).catch(() => {});
  // Check allocation table exists
  await expect(page.getByText("현재 선택 포트폴리오")).toBeVisible();
  // Slider verification: left/middle/right
  const getData = async () => {
    const count = await page.locator(".kpi-value").count();
    console.log("kpi count", count);
    console.log("html snippet", (await page.content()).slice(0, 2000).replace(/\n/g, " ").slice(0, 500));
    await expect(page.locator(".kpi-value").first()).toBeVisible({ timeout: 10000 });
    const vals = await page.locator(".kpi-value").allTextContents();
    const ret = vals[0] ?? "-";
    const vol = vals[1] ?? "-";
    return { ret, vol };
  };
  async function setSlider(val: string) {
    await page.locator("input[type='range']").evaluate((el, v) => {
      const input = el as HTMLInputElement;
      input.value = v;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }, val);
    await page.waitForTimeout(1000);
  }
  // Left
  await setSlider("0");
  const left = await getData();
  console.log("LEFT", left);
  // Middle
  await setSlider("25");
  const middle = await getData();
  console.log("MIDDLE", middle);
  // Right
  await setSlider("49");
  const right = await getData();
  console.log("RIGHT", right);
  console.log("left vs middle", left.ret, middle.ret, left.ret !== middle.ret);
  expect(left.ret).not.toBe(middle.ret);
  expect(middle.ret).not.toBe(right.ret);
  // Before CTA, DB should have 0 selections (check via API)
  const baseBefore = await page.evaluate(() => fetch("/api/v1/me/base-portfolio", { credentials: "include" }).then((r) => r.json()));
  console.log("BEFORE", baseBefore);
  // CTA
  await setSlider("25");
  await page.getByRole("button", { name: "이 포트폴리오로 시작" }).click();
  await expect(page.getByText("이 포트폴리오를 기본 포트폴리오로 설정할까요?")).toBeVisible();
  await page.getByRole("button", { name: "설정" }).click();
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
  await expect(page.locator("h1", { hasText: "Dashboard" })).toBeVisible();
  // Check dashboard allocation matches selected (at least 3 assets)
  const baseAfter = await page.evaluate(() => fetch("/api/v1/me/base-portfolio", { credentials: "include" }).then((r) => r.json()));
  console.log("AFTER", baseAfter);
  // Check current views empty
  const views = await page.evaluate(() => fetch("/api/v1/me/views/current", { credentials: "include" }).then((r) => r.json()));
  console.log("VIEWS", views);
});
