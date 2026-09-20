import { test, expect } from "@playwright/test";

const password = "Capstone-Demo-2026!";

async function login(page: import("@playwright/test").Page, n: number) {
  await page.goto("/login");
  await page.getByLabel("이메일", {exact:true}).fill(`capstone${String(n).padStart(2,"0")}@example.com`);
  await page.getByLabel("비밀번호", {exact:true}).fill(password);
  await page.getByRole("button", {name:"로그인",exact:true}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.locator("h1")).toContainText(`참여자 ${String(n).padStart(2,"0")}`);
}

test("four professor demo scenarios, data parity, refresh and responsive UI", async ({page}) => {
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/login/);
  await login(page,1);
  await expect(page.getByText("+ 반도체", {exact:true})).toBeVisible();
  await expect(page.getByText("+ AI", {exact:true})).toBeVisible();
  const own = await (await page.request.get("/api/v1/me/comparison")).json();
  await expect(page.locator('[data-metric="excess_return"]')).toContainText(`${(own.metrics.excess_return*100).toFixed(2)}%p`);
  const values = await page.locator("[data-metric]").allTextContents();
  await expect(page.getByRole("region", {name:"Personalized Portfolio vs CORE NAV"}).locator(".recharts-wrapper > svg.recharts-surface")).toBeVisible();
  await expect(page.locator("path.recharts-line-curve")).toHaveCount(2);
  for (const path of await page.locator("path.recharts-line-curve").all()) {
    expect((await path.getAttribute("d"))?.length).toBeGreaterThan(1000);
  }
  await page.reload();
  await expect(page.locator('[data-metric="nav"]')).toContainText(own.metrics.nav.toFixed(2));
  await page.screenshot({path:"test-results/capstone-dashboard.png",fullPage:true});

  await page.getByRole("link", {name:"참여자 성과 비교"}).click();
  await expect(page.getByRole("region",{name:"순위표",exact:true}).locator("tbody tr")).toHaveCount((await (await page.request.get("/api/v1/comparison/rankings")).json()).total);
  for (const [basis, expected] of [["return","참여자 01"],["sharpe","참여자 03"],["mdd","참여자 13"],["volatility","참여자 13"],["excess","참여자 01"]]) {
    await page.getByLabel("정렬 기준").selectOption(basis);
    const top=(await (await page.request.get(`/api/v1/comparison/rankings?basis=${basis}`)).json()).items[0].display_name;
    await expect(page.getByRole("region",{name:"순위표",exact:true}).locator("tbody tr").first()).toContainText(top);
    await expect(page.getByRole("region",{name:"순위표",exact:true}).locator("tbody tr").first().locator("td").first()).toHaveText("01");
  }
  await page.screenshot({path:"test-results/capstone-ranking.png",fullPage:true});
  // Click the metric cell, not just the name link: the whole row must navigate.
  await page.getByRole("region",{name:"순위표",exact:true}).locator("tbody tr").filter({has:page.getByRole("link", {name:/참여자 02/})}).locator("td").last().click();
  await expect(page).toHaveURL(/\/participants\//);
  await expect(page.locator("h1")).toContainText("참여자 02");
  await expect(page.getByText("+ 방산",{exact:true})).toBeVisible();
  await expect(page.getByText("+ 원자력",{exact:true})).toBeVisible();
  await expect(page.getByRole("region", {name:"확정 Personalized Portfolio 구성"})).toBeVisible();
  await page.screenshot({path:"test-results/capstone-detail.png",fullPage:true});
  await page.goto(`/participants/${own.participant_id}`);
  await expect(page.locator("h1")).toContainText("참여자 01");
  expect(await page.locator("[data-metric]").allTextContents()).toEqual(values);
  await page.getByRole("button",{name:"로그아웃",exact:true}).click();
  await expect(page).toHaveURL(/\/login$/);
  await login(page,3);
  await page.reload();
  await expect(page.locator("h1")).toContainText("참여자 03");
  await expect(page.getByText("+ 전력망",{exact:true})).toBeVisible();
  const other = await (await page.request.get("/api/v1/me/comparison")).json();
  expect(other.participant_id).not.toBe(own.participant_id);
  await expect(page.locator('[data-metric="nav"]')).toContainText(other.metrics.nav.toFixed(2));

  await page.setViewportSize({width:390,height:844});
  await page.screenshot({path:"test-results/capstone-mobile.png",fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.getByRole("button", {name:"메뉴 열기"}).click();
  await page.getByRole("link",{name:"참여자 비교·랭킹",exact:true}).click();
  await expect(page.getByRole("region",{name:"순위표",exact:true}).locator("tbody tr")).toHaveCount((await (await page.request.get("/api/v1/comparison/rankings")).json()).total);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  expect(errors).toEqual([]);
});
