import {test, expect, type Page, type BrowserContext} from "@playwright/test";
import fs from "node:fs";

type Account = {number:number;email:string;password:string};
const accounts:Account[] = JSON.parse(fs.readFileSync(process.env.E2E_LAB_ACCOUNTS!,"utf8")).accounts;

async function signIn(page:Page, account:Account) {
  await page.goto("/login");
  await page.getByLabel("이메일",{exact:true}).fill(account.email);
  await page.getByLabel("비밀번호",{exact:true}).fill(account.password);
  await page.getByRole("button",{name:"로그인",exact:true}).click();
  await expect(page).toHaveURL(/\/setup\/portfolio$/);
}
async function choose(page:Page, label:string) {
  await page.getByRole("button",{name:"다음: 투자 인사이트 반영"}).click();
  await page.getByRole("button",{name:`${label} 선택`,exact:true}).click();
  await page.getByRole("button",{name:"다음: 변경 전·후 비교"}).click();
  await page.getByRole("button",{name:"포트폴리오 확정 · 성과 확인"}).click();
  await expect(page).toHaveURL(/\/portfolio$/);
}
async function csrf(context:BrowserContext) {
  return {"X-CSRF-Token":(await context.cookies()).find(c=>c.name==="ra_csrf")!.value};
}

test("13 isolated sessions select concurrently and see updated rankings",async({browser})=>{
  const contexts = await Promise.all(accounts.map((_,i)=>browser.newContext({
    baseURL:process.env.E2E_BASE_URL, viewport:i===12?{width:390,height:844}:{width:1440,height:1000},
  })));
  const errors:string[]=[];
  try {
    const presenter = await contexts[0].newPage();
    presenter.on("pageerror",e=>errors.push(e.message));
    await signIn(presenter,accounts[0]);
    await presenter.goto("/ranking");
    await expect(presenter.getByText("구성 완료 0 / 13명",{exact:true})).toBeVisible();
    await expect(presenter.getByText("아직 비교할 참여자가 없습니다.",{exact:true})).toBeVisible();
    const desktop = await contexts[0].newPage();
    desktop.on("pageerror",e=>errors.push(e.message));
    await desktop.goto("/setup/portfolio");
    await choose(desktop,"인공지능");
    const rows=presenter.getByRole("region",{name:"순위표",exact:true}).locator("tbody tr");
    await expect(rows).toHaveCount(1);
    const mobile=await contexts[12].newPage();
    mobile.on("pageerror",e=>errors.push(e.message));
    await signIn(mobile,accounts[12]);
    await choose(mobile,"바이오테크");
    expect(await mobile.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    const themeIds=["semiconductor","defense","power_grid","nuclear","robotics","cloud_data_center","cybersecurity","ai","biotech","defense","semiconductor"];
    const started=Date.now();
    await Promise.all(contexts.slice(1,12).map(async(context,i)=>{
      const account=accounts[i+1];
      const login=await context.request.post("/api/v1/auth/login",{data:{email:account.email,password:account.password}});
      expect(login.status()).toBe(200);
      expect((await login.json()).user.email).toBe(account.email);
      const headers=await csrf(context);
      const frontier=await (await context.request.get("/api/v1/me/frontier")).json();
      const data={frontier_id:frontier.benchmark_frontier_id,theme_ids:[themeIds[i]],current_step:"review"};
      const draft=await context.request.put("/api/v1/me/onboarding/draft",{data,headers});
      expect(draft.status()).toBe(200);
      const preview=await context.request.post("/api/v1/me/onboarding/preview",{data});
      expect(preview.status()).toBe(200);
      const saved=await context.request.post("/api/v1/me/onboarding/complete",{data,headers});
      expect(saved.status()).toBe(200);
      const report=await (await context.request.get("/api/v1/me/comparison")).json();
      expect(report.themes).toEqual(data.theme_ids);
      expect(report.data_source).toBe("MARKET_PRICE_REPLAY");
    }));
    console.log(`11 simultaneous login/draft/preview/complete/report flows: ${(Date.now()-started)/1000}s`);
    await expect(rows).toHaveCount(13);
    await expect(presenter.getByText("구성 완료 13 / 13명",{exact:true})).toBeVisible();
    const ranks=await (await contexts[0].request.get("/api/v1/comparison/rankings")).json();
    expect(ranks.total).toBe(13);
    const reports=await (await contexts[0].request.get("/api/v1/comparison/analytics")).json();
    expect(new Set(reports.reports.map((r:{participant_id:string})=>r.participant_id)).size).toBe(13);
    const original=reports.reports.find((r:{display_name:string})=>r.display_name==="참여자 02");
    const frontier=await (await contexts[1].request.get("/api/v1/me/frontier")).json();
    const updated=await contexts[1].request.post("/api/v1/me/onboarding/complete",{headers:await csrf(contexts[1]),
      data:{frontier_id:frontier.min_variance_frontier_id,theme_ids:["ai","biotech"]}});
    expect(updated.status()).toBe(200);
    await expect(rows.filter({hasText:"참여자 02"})).toContainText("AI바이오");
    const after=await (await contexts[1].request.get("/api/v1/me/comparison")).json();
    expect(after.metrics).not.toEqual(original.metrics);
    for(const basis of ["mdd","volatility","sharpe","return"]) {
      await presenter.getByRole("region",{name:"순위표",exact:true}).getByLabel("정렬 기준").selectOption(basis);
      await expect(rows).toHaveCount(13);
    }
    await mobile.goto("/ranking");
    await expect(mobile.getByRole("region",{name:"순위표",exact:true}).locator("tbody tr")).toHaveCount(13);
    expect(await mobile.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await presenter.screenshot({path:`${process.env.E2E_OUTPUT_DIR}/ranking-desktop.png`,fullPage:true});
    await mobile.screenshot({path:`${process.env.E2E_OUTPUT_DIR}/ranking-mobile.png`,fullPage:true});
    expect(errors).toEqual([]);
    // All sessions hit the same populated comparison at once, as during discussion.
    await Promise.all(contexts.map(async c=>{
      const r=await c.request.get("/api/v1/comparison/rankings");
      expect(r.status()).toBe(200);
      expect((await r.json()).total).toBe(13);
    }));
  } finally { await Promise.all(contexts.map(c=>c.close())); }
});
