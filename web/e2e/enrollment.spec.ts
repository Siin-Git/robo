import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { randomBytes } from "node:crypto";

test("two real signups, persistence, common CORE, comparison and mobile", async ({browser})=>{
  const source=process.env.E2E_INVITE_FILE;
  if(!source)throw new Error("Prepare two fresh slots and set E2E_INVITE_FILE outside repository.");
  const invitations=JSON.parse(readFileSync(source,"utf8")).invitations as {email:string;invitation_code:string}[];
  expect(invitations).toHaveLength(2);
  const reports=[];
  for(let i=0;i<2;i++) {
    const context=await browser.newContext({viewport:i?{width:390,height:844}:{width:1440,height:1000}});
    const page=await context.newPage();const errors:string[]=[];
    page.on("pageerror",e=>errors.push(e.message));
    const password=randomBytes(24).toString("base64url");
    await page.goto("/signup");
    await page.getByLabel("이메일",{exact:true}).fill(invitations[i].email);
    await page.getByLabel("표시 이름").fill(`신규 시연 ${i+1}`);
    await page.getByLabel("비밀번호",{exact:true}).fill(password);
    await page.getByLabel("비밀번호 확인",{exact:true}).fill(password);
    await page.getByLabel("시연 초대 코드").fill(invitations[i].invitation_code);
    await page.getByRole("button",{name:"계정 만들기",exact:true}).click();
    await expect(page).toHaveURL(/\/setup\/portfolio$/);
    await expect(page.getByRole("heading",{name:"공통 CORE에서 나의 투자 관점으로"})).toBeVisible();
    await page.getByRole("button",{name:"공통 CORE 확인 · 다음"}).click();
    await page.getByRole("button",{name:i?"방산·항공우주 선택":"반도체 선택",exact:true}).click();
    await page.getByRole("button",{name:i?"원자력·우라늄 선택":"인공지능 선택",exact:true}).click();
    const reason=`시연 ${i+1}의 독립된 선택 이유`;
    await page.getByLabel("선택 이유",{exact:true}).fill(reason);
    await expect(page.getByRole("status",{name:"설정 저장 상태"})).toHaveText("서버에 저장됨");
    await page.reload();
    await expect(page.getByLabel("선택 이유",{exact:true})).toHaveValue(reason);
    await expect(page.getByText("2 / 2",{exact:true})).toBeVisible();
    await page.getByRole("button",{name:"구성·비중 확인"}).click();
    await expect(page.getByText(`선택 이유: ${reason}`,{exact:true})).toBeVisible();
    await page.getByRole("button",{name:"포트폴리오 생성",exact:true}).click();
    await expect(page).toHaveURL(/\/portfolio\?created=1$/);
    await expect(page.getByRole("heading",{name:`신규 시연 ${i+1}의 투자 구성`})).toBeVisible();
    await expect(page.getByText(`선택 이유: ${reason}`,{exact:true})).toBeVisible();
    const report=await (await page.request.get("/api/v1/me/comparison")).json();reports.push(report);
    expect(report.data_source).toBe("DEMO_SCENARIO_ASSIGNED");
    const status=await (await page.request.get("/api/v1/me/experiment")).json();
    expect(status.registered).toBe(12+i);
    await page.getByRole("link",{name:"내 성과 대시보드",exact:true}).click();
    await expect(page.locator('[data-metric="cumulative_return"]')).toContainText((report.metrics.cumulative_return*100).toFixed(2));
    await page.getByRole("link",{name:"참여자 성과 비교",exact:true}).click();
    const ranking=page.getByRole("region",{name:"순위표",exact:true});
    await expect(ranking.locator("tbody tr")).toHaveCount(12+i);
    await expect(page.getByRole("region",{name:"Portfolio Race",exact:true}).locator(".recharts-wrapper")).toBeVisible();
    await expect(page.getByRole("region",{name:"Risk–Return Map",exact:true}).locator(".recharts-wrapper")).toBeVisible();
    for(const metric of ["return","mdd","volatility","sharpe","te","ir"]) {
      await page.getByLabel("정렬 기준").selectOption(metric);
      await expect(ranking.locator("tbody tr")).toHaveCount(12+i);
      await expect(ranking.locator(".analytics-my-row")).toHaveCount(1);
    }
    await page.screenshot({path:`/private/tmp/robo-unified-ranking-${i}.png`,fullPage:true});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.getByLabel("참가자 상세 선택").selectOption(report.participant_id);
    await expect(page).toHaveURL(new RegExp(`/participants/${report.participant_id}$`));
    await expect(page.locator('[data-metric="nav"]')).toContainText(report.metrics.nav.toFixed(2));
    await page.getByText("상대 순위 · 기준 주간 · 추가 분석",{exact:true}).click();
    await expect(page.getByText("최근 데이터 기준 주간",{exact:true})).toBeVisible();
    await page.screenshot({path:`/private/tmp/robo-unified-detail-${i}.png`,fullPage:true});
    if(i) await page.getByRole("button",{name:"메뉴 열기",exact:true}).click();
    await page.getByRole("button",{name:"로그아웃",exact:true}).filter({visible:true}).click();
    await expect(page).toHaveURL(/\/login$/);
    await page.getByLabel("이메일",{exact:true}).fill(invitations[i].email);
    await page.getByLabel("비밀번호",{exact:true}).fill(password);
    await page.getByRole("button",{name:"로그인",exact:true}).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.locator("h1")).toContainText(`신규 시연 ${i+1}`);
    if(i===1) {
      await page.getByRole("button",{name:"메뉴 열기",exact:true}).click();
      await page.getByRole("button",{name:"로그아웃",exact:true}).filter({visible:true}).click();
      await expect(page).toHaveURL(/\/login$/);
      await page.getByLabel("이메일",{exact:true}).fill("capstone13@example.com");
      await page.getByLabel("비밀번호",{exact:true}).fill("Capstone-Demo-2026!");
      await page.getByRole("button",{name:"로그인",exact:true}).click();
      await expect(page).toHaveURL(/\/dashboard$/);
      await expect(page.locator("h1")).toContainText("참여자 13");
      await expect(page.getByText(`선택 이유: ${reason}`,{exact:true})).toHaveCount(0);
    }
    expect(errors).toEqual([]);
    await context.close();
  }
  expect(reports[0].themes).not.toEqual(reports[1].themes);
  expect(reports[0].metrics).not.toEqual(reports[1].metrics);
  expect(reports[0].core_allocation).toEqual(reports[1].core_allocation);
});
