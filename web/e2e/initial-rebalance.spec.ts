import {test,expect} from "@playwright/test";
import {readFileSync} from "node:fs";
import path from "node:path";

for (const [name, index, viewport] of [
  ["desktop",3,{width:1440,height:1000}], ["mobile",4,{width:390,height:844}],
] as const) {
  test(`${name}: initial cycle survives theme, back, confirmation, refresh and login`,async({page})=>{
    const directory=process.env.E2E_OPERATIONS_DATA_DIR!;
    if (!directory?.startsWith('/private/tmp/robo-initial-rebalance-')) throw new Error('Require a disposable frequency test directory.');
    expect(JSON.parse(readFileSync(path.join(directory,'monday-fixture.json'),'utf8')).data_kind).toBe('TEST_FIXTURE');
    const account=JSON.parse(readFileSync(path.join(directory,'accounts.json'),'utf8')).accounts[index+Number(process.env.E2E_ACCOUNT_OFFSET??0)];
    const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
    await page.setViewportSize(viewport);
    const login=async()=>{
      await page.goto('/login');await page.getByLabel('이메일',{exact:true}).fill(account.email);
      await page.getByLabel('비밀번호',{exact:true}).fill(account.password);
      await page.getByRole('button',{name:'로그인',exact:true}).click();
      await expect(page).toHaveURL(/\/(dashboard|setup\/portfolio)$/);
    };
    await login();await page.goto('/setup/portfolio?step=risk');
    await expect(page.getByRole('radio',{name:'매월'})).toBeChecked();
    await page.getByRole('radio',{name:'매분기'}).check();
    await expect(page.getByText(/18% 미만 또는 22% 초과/)).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:path.join(directory,`${name}-initial.png`),fullPage:true});
    await page.getByRole('button',{name:'다음: 투자 인사이트 반영'}).click();
    await page.getByRole('button',{name:'인공지능 선택',exact:true}).click();
    await page.getByRole('button',{name:'위험 수준 다시 보기'}).click();
    await expect(page.getByRole('radio',{name:'매분기'})).toBeChecked();
    await page.getByRole('button',{name:'다음: 투자 인사이트 반영'}).click();
    await expect(page.getByRole('button',{name:'인공지능 선택 해제',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'다음: 변경 전·후 비교'}).click();
    await expect(page.getByLabel('확정 전 리밸런싱 주기')).toContainText('매분기');
    expect(await page.getByRole('radio').count()).toBe(0);
    await expect(page.getByRole('region',{name:'테마 적용 전후 Efficient Frontier 위치'})).toBeVisible();
    await page.reload();await expect(page.getByLabel('확정 전 리밸런싱 주기')).toContainText('매분기');
    const draft=await(await page.request.get('/api/v1/me/onboarding/draft')).json();
    expect(draft.rebalance_frequency).toBe('quarterly');expect(draft.theme_ids).toContain('ai');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:path.join(directory,`${name}-review.png`),fullPage:true});
    await page.getByRole('button',{name:'포트폴리오 확정 · 성과 확인'}).click();
    await expect(page).toHaveURL(/\/portfolio$/);
    await expect(page.getByLabel('저장된 리밸런싱 주기')).toContainText('매분기');
    const decisions=await(await page.request.get('/api/v1/me/decisions')).json();
    expect(decisions.items[0].provenance.rebalance_frequency).toBe('quarterly');
    await page.reload();await expect(page.getByLabel('저장된 리밸런싱 주기')).toContainText('매분기');
    if (name==='mobile') await page.getByRole('button',{name:'메뉴 열기',exact:true}).click();
    await page.getByRole('button',{name:'로그아웃',exact:true}).click();await expect(page).toHaveURL(/\/login$/);
    await login();await page.goto('/portfolio');
    await expect(page.getByLabel('저장된 리밸런싱 주기')).toContainText('매분기');
    await page.goto('/setup/portfolio?step=risk');await expect(page.getByRole('radio',{name:'매분기'})).toBeChecked();
    expect(errors).toEqual([]);
  });
}
