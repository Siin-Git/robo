import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import path from 'node:path';
const fixture=process.env.E2E_OPERATIONS_DATA_DIR;
if(!fixture)throw new Error('Set isolated E2E_OPERATIONS_DATA_DIR; never production.');
const accounts=JSON.parse(readFileSync(path.join(fixture,'accounts.json'),'utf8')).accounts;
async function login(page:import('@playwright/test').Page,n:number){await page.goto('/login');await page.getByLabel('이메일',{exact:true}).fill(accounts[n].email);await page.getByLabel('비밀번호',{exact:true}).fill(accounts[n].password);await page.getByRole('button',{name:'로그인',exact:true}).click();}
async function configure(page:import('@playwright/test').Page,theme:string){
  await expect(page.getByRole('slider',{name:'위험 수준'})).toBeVisible();await page.getByRole('button',{name:'다음: 투자 인사이트 반영'}).click();await page.getByRole('button',{name:theme,exact:true}).click();await page.getByRole('button',{name:'다음: 변경 전·후 비교'}).click();
  await expect(page.getByRole('region',{name:'테마 적용 전후 Efficient Frontier 위치'})).toBeVisible();
  const draft=await(await page.request.get('/api/v1/me/onboarding/draft')).json();const p=await(await page.request.post('/api/v1/me/onboarding/preview',{data:draft})).json();expect(p.personalized.expected_return).not.toBeNull();expect(p.frontier_position.personalized.expected_return).not.toBeNull();
  await page.getByRole('button',{name:'포트폴리오 확정 · 성과 확인'}).click();await expect(page).toHaveURL(/\/portfolio$/);
}
test('new user, keep, redesign, recorded ledger and revision review',async({page,browser})=>{
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await login(page,0);await expect(page).toHaveURL(/\/setup\/portfolio/);await configure(page,'인공지능 선택');
  await page.goto('/dashboard');await expect(page.getByRole('region',{name:'운용 원장'})).toContainText('첫 체결·평가 대기');await page.getByRole('link',{name:'최초 예상·실제 검토',exact:true}).click();
  await expect(page.getByRole('heading',{name:'확정 당시 판단 · v1'})).toBeVisible();await expect(page.getByText('期間 미도달'.replace('期間','기간'),{exact:false})).toHaveCount(2);
  await page.getByLabel('선택 이유').fill('밴드 리밸런싱을 계속하며 구성 유지');await page.getByRole('button',{name:'구성 유지 선택',exact:true}).click();await expect(page.getByRole('status')).toContainText('유지 선택을 저장');
  const original=(await(await page.request.get('/api/v1/me/decisions')).json()).items[0];
  await page.getByLabel('선택 이유').fill('위험 근거를 검토하고 새 버전 설계');await page.getByRole('button',{name:'조정 검토 · 재설계',exact:true}).click();await expect(page).toHaveURL(/adjustment_choice_id=/);await configure(page,'바이오테크 선택');
  const ds=(await(await page.request.get('/api/v1/me/decisions')).json()).items;expect(ds).toHaveLength(2);expect(ds[1]).toEqual(original);expect(ds[0].previous_decision_id).toBe(original.decision_id);expect(ds[0].provenance.adjustment_choice_id).toBeTruthy();
  const root=path.resolve(process.cwd(),'..');execFileSync(path.join(root,'.venv/bin/python'),[path.join(root,'scripts/seed_integration_fixture.py'),'--database',path.join(fixture!,'portfolio_design.db'),'--account',ds[0].account_id],{cwd:root,env:{...process.env,DATABASE_BACKEND:'sqlite',APP_PROFILE:'validation',DATABASE_URL:'',CAPSTONE_DESIGN_DATABASE_URL:'',CAPSTONE_DEMO:'0'}});
  await page.goto('/dashboard');await expect(page.getByRole('region',{name:'운용 원장'})).toContainText('검증용 합성 데이터');await page.getByText(/주문 History/).click();await page.getByText(/체결 History/).click();await expect(page.getByRole('region',{name:'운용 원장'})).toContainText('executed');await expect(page.getByText('조정 없음',{exact:true}).first()).toBeVisible();
  await expect(page.getByRole('region',{name:'같은 기간 비교'})).toContainText('기준 포트폴리오 정의 미정');const c=await(await page.request.get('/api/v1/me/performance/contributions')).json();expect(c.reconciliation.reconciled).toBe(true);expect(c.start).toBe(ds[0].target_effective_date);
  await page.getByRole('link',{name:'최초 예상·실제 검토',exact:true}).click();await expect(page.getByRole('heading',{name:'관측 결과와 검토 근거'})).toBeVisible();await expect(page.getByText('비교 불가',{exact:false}).first()).toBeVisible();await expect(page.getByText('기간 미도달',{exact:false})).toHaveCount(2);await page.screenshot({path:'/private/tmp/robo-operations-e2e/review.png',fullPage:true});
  await page.getByLabel('판단 버전').selectOption(original.decision_id);await expect(page.getByRole('heading',{name:'확정 당시 판단 · v1'})).toBeVisible();await expect(page.getByRole('button',{name:'구성 유지 선택'})).toHaveCount(0);
  const ctx=await browser.newContext({viewport:{width:390,height:844}}),other=await ctx.newPage();await login(other,1);await expect(other).toHaveURL(/\/setup\/portfolio/);await other.goto('/dashboard');await expect(other.getByRole('region',{name:'운용 원장'})).toContainText('첫 체결·평가 대기');expect((await other.request.get(`/api/v1/me/decisions/${ds[0].decision_id}/review`)).status()).toBe(404);await ctx.close();expect(errors).toEqual([]);
});
