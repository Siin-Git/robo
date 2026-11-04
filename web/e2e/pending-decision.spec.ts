import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import path from 'node:path';

test('future revision preserves dashboard and aligns all comparison scopes',async({page})=>{
  const directory=process.env.E2E_OPERATIONS_DATA_DIR!;
  const account=JSON.parse(readFileSync(path.join(directory,'accounts.json'),'utf8')).accounts[0];
  const original=JSON.parse(readFileSync(path.join(directory,'pending-fixture.json'),'utf8')).original;
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/login');await page.getByLabel('이메일',{exact:true}).fill(account.email);await page.getByLabel('비밀번호',{exact:true}).fill(account.password);await page.getByRole('button',{name:'로그인',exact:true}).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  const before=await(await page.request.get('/api/v1/me/performance/dashboard')).json();expect(before.observations).toBe(2);
  await expect(page.getByRole('region',{name:'성과 적용 판단'})).toContainText('현재 운용 판단: v1');
  await page.getByRole('link',{name:'최초 예상·실제 검토',exact:true}).click();
  await expect(page.getByText('유지·조정 선택은 주문 승인·거절 기능이 아닙니다.',{exact:false})).toBeVisible();
  await expect(page.getByText(/관측 기간이 지나도 자동으로 비교가 완성되지 않습니다/)).toBeVisible();
  await page.getByLabel('선택 이유').fill('SYNTHETIC fixture: inspect a future revision');await page.getByRole('button',{name:'조정 검토 · 재설계',exact:true}).click();
  await expect(page.getByRole('slider',{name:'위험 수준'})).toBeVisible();await page.getByRole('button',{name:'다음: 투자 인사이트 반영'}).click();await page.getByRole('button',{name:'바이오테크 선택',exact:true}).click();await page.getByRole('button',{name:'다음: 변경 전·후 비교'}).click();await page.getByRole('button',{name:'포트폴리오 확정 · 성과 확인'}).click();await expect(page).toHaveURL(/\/portfolio$/);
  const decisions=(await(await page.request.get('/api/v1/me/decisions')).json()).items;expect(decisions).toHaveLength(2);expect(decisions[1]).toEqual(original);
  await page.getByRole('link',{name:'운용 성과 확인',exact:true}).click();await expect(page).toHaveURL(/\/dashboard$/);const panel=page.getByRole('region',{name:'성과 적용 판단'});
  await expect(panel).toContainText('현재 운용 판단: v1');await expect(panel).toContainText('적용 대기 판단: v2');await expect(panel).toContainText('평가일 2개');
  const after=await(await page.request.get('/api/v1/me/performance/dashboard')).json();expect(after.observations).toBe(2);expect(after.metrics).toEqual(before.metrics);expect(after.decision_context.report_decision_id).toBe(original.decision_id);
  const contribution=await(await page.request.get('/api/v1/me/performance/contributions')).json();expect(contribution.decision_context).toEqual(after.decision_context);expect(contribution.start).toBe(after.start);expect(contribution.end).toBe(after.end);expect(contribution.reconciliation.reconciled).toBe(true);
  for(const c of after.comparators){expect(c.decision_id).toBe(original.decision_id);expect(c.start).toBe(after.start);expect(c.end).toBe(after.end);}
  await page.setViewportSize({width:390,height:844});await expect(panel).toContainText('적용 대기 판단: v2');expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'/private/tmp/robo-pending-browser/dashboard-mobile.png',fullPage:true});
  await panel.getByRole('link',{name:'대기 판단 상세 보기'}).click();await expect(page.getByRole('heading',{name:'확정 당시 판단 · v2'})).toBeVisible();
  await expect(page.getByText(/기록 부족: 두 평가일 이상/)).toBeVisible();
  await page.goto(`/review?decision_id=${original.decision_id}`);await expect(page.getByRole('heading',{name:'확정 당시 판단 · v1'})).toBeVisible();await expect(page.getByText(/평가일 2개/)).toBeVisible();await expect(page.getByRole('button',{name:'구성 유지 선택'})).toHaveCount(0);
  expect(errors).toEqual([]);
});
