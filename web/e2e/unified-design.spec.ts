import { test, expect } from "@playwright/test";
import { randomBytes } from "node:crypto";

test("v1 frontier, saved design, weekly view, dashboard and frozen comparison coexist", async ({page}) => {
  const capstone = process.env.NEXT_PUBLIC_CAPSTONE_DEMO === "1";
  const email = capstone ? "capstone01@example.com" : "v1-regression@example.com";
  const password = capstone ? "Capstone-Demo-2026!" : randomBytes(24).toString("base64url");
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  if (!capstone) {
    await page.goto("/signup");
    await page.getByLabel("이메일", {exact:true}).fill(email);
    await page.getByLabel("표시 이름").fill("기존 설계 회귀 사용자");
    await page.getByLabel("비밀번호", {exact:true}).fill(password);
    await page.getByLabel("비밀번호 확인", {exact:true}).fill(password);
    await page.getByRole("button", {name:"계정 만들기",exact:true}).click();
    await expect(page).toHaveURL(/\/(dashboard|setup\/portfolio)$/);
  } else {
    await page.goto("/login");
    await page.getByLabel("이메일", {exact:true}).fill(email);
    await page.getByLabel("비밀번호", {exact:true}).fill(password);
    await page.getByRole("button", {name:"로그인",exact:true}).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  }
  const frozen = capstone ? await (await page.request.get("/api/v1/me/comparison")).json() : null;
  await page.getByRole("link", {name:"포트폴리오 설계",exact:true}).first().click();
  await expect(page.getByRole("heading", {name:"위험 수준에 맞는 기본 포트폴리오를 설계하세요"})).toBeVisible();
  const frontier = await (await page.request.get("/api/v1/me/frontier")).json();
  const slider = page.getByRole("slider", {name:"위험 수준"});
  await slider.fill("0");
  const low = await slider.getAttribute("aria-valuetext");
  await slider.fill(String(frontier.points.length-1));
  expect(await slider.getAttribute("aria-valuetext")).not.toBe(low);
  const selected = frontier.points.findIndex((p:{frontier_id:string})=>p.frontier_id===frontier.benchmark_frontier_id);
  await slider.fill(String(selected));
  await page.getByRole("button", {name:"다음: 투자 인사이트 반영"}).click();
  await page.getByRole("button", {name:"인공지능 선택",exact:true}).click();
  await page.getByRole("button", {name:"바이오테크 선택",exact:true}).click();
  await page.getByRole("button", {name:"다음: 변경 전·후 비교"}).click();
  await expect(page.getByRole("heading", {name:"인사이트가 포트폴리오를 어떻게 바꿨나요?"})).toBeVisible();
  await page.reload();
  const draft = await (await page.request.get("/api/v1/me/onboarding/draft")).json();
  expect(draft.theme_ids.sort()).toEqual(["ai","biotech"]);
  const preview = await (await page.request.post("/api/v1/me/onboarding/preview", {data:{frontier_id:draft.frontier_id,theme_ids:draft.theme_ids}})).json();
  expect(preview.risk_comparison.base_volatility).toBeGreaterThan(0);
  expect(preview.risk_comparison.personalized_volatility).toBeGreaterThan(0);
  await page.getByRole("button", {name:"포트폴리오 확정 · 성과 확인"}).click();
  await expect(page).toHaveURL(capstone ? /\/portfolio\?workspace=design$/ : /\/portfolio$/);
  await expect(page.getByRole("heading", {name:"나의 자산 구성"})).toBeVisible();
  const saved = await (await page.request.get("/api/v1/me/portfolio/summary")).json();
  // The v1 summary DTO removes the theme: prefix and adds display metadata.
  const weights = (rows:{asset_id:string;weight:number}[]) => Object.fromEntries(
    rows.map(w=>[w.asset_id.replace(/^theme:/,""),w.weight]));
  expect(weights(saved.personalized.weights)).toEqual(weights(preview.personalized.weights));
  await page.getByRole("link", {name:"운용 성과 확인",exact:true}).click();
  await expect(page.getByRole("heading", {name:"포트폴리오 운용 성과",exact:true,level:1})).toBeVisible();
  await expect(page.getByText("포트폴리오는 저장되어 있어요",{exact:true})).toBeVisible();
  await page.getByRole("link",{name:"저장된 포트폴리오 확인"}).click();
  await expect(page).toHaveURL(capstone ? /\/portfolio\?workspace=design$/ : /\/portfolio$/);
  await page.getByRole("link", {name:"주간 투자 의견",exact:true}).click();
  await page.getByRole("button", {name:/Artificial Intelligence|^AI /}).first().click();
  await page.getByPlaceholder("이번 주 이 산업을 긍정적으로 보는 이유를 간단히 입력하세요.").fill("자유 설계의 주간 의견");
  await page.getByRole("button", {name:"View 제출",exact:true}).click();
  await expect(page.getByText("제출 완료",{exact:false})).toBeVisible();
  if (capstone) {
    expect(await (await page.request.get("/api/v1/me/comparison")).json()).toEqual(frozen);
    await page.getByRole("link",{name:"참여자 비교·랭킹",exact:true}).click();
    await expect(page.getByRole("region",{name:"순위표",exact:true}).locator("tbody tr")).toHaveCount(13);
  }
  await page.getByRole("button",{name:"로그아웃",exact:true}).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("이메일",{exact:true}).fill(email);
  await page.getByLabel("비밀번호",{exact:true}).fill(password);
  await page.getByRole("button",{name:"로그인",exact:true}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  expect((await (await page.request.get("/api/v1/me/portfolio/summary")).json()).personalized.weights).toEqual(saved.personalized.weights);
  expect(errors).toEqual([]);
});
