import {test,expect, type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import path from 'node:path';

const directory=process.env.E2E_OPERATIONS_DATA_DIR!;
async function signIn(page:Page,index:number){
 const account=JSON.parse(readFileSync(path.join(directory,'accounts.json'),'utf8')).accounts[index];
 await page.context().clearCookies();await page.goto('/login');
 await page.getByLabel('이메일',{exact:true}).fill(account.email);
 await page.getByLabel('비밀번호',{exact:true}).fill(account.password);
 await page.getByRole('button',{name:'로그인',exact:true}).click();
 await expect(page).not.toHaveURL(/\/login/);
}
async function report(page:Page,suffix='') {return (await page.request.get('/api/v1/me/performance/dashboard'+suffix)).json();}
for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
 test(`ledger screens 0/1/multiple and common period ${viewport.width}`,async({page})=>{
  await page.setViewportSize(viewport);
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await signIn(page,0);await page.goto('/dashboard');
  const own=await report(page);expect(own.observations).toBe(3);
  await expect(page.getByRole('region',{name:'성과 적용 판단'})).toContainText('현재 운용 판단: v1');
  await expect(page.getByRole('region',{name:'성과 적용 판단'})).toContainText('적용 대기 판단: v2');
  await expect(page.getByRole('region',{name:'기록된 평가액'})).toContainText('원화');
  await expect(page.getByRole('heading',{name:'내 수익은 어디에서 나왔을까요?'})).toBeVisible();
  await page.goto('/performance');
  await expect(page.getByRole('heading',{name:'포트폴리오 운용 성과',exact:true,level:1})).toBeVisible();
  expect((await report(page)).metrics).toEqual(own.metrics);
  await page.goto('/ranking');
  const comparison=await(await page.request.get('/api/v1/me/performance/comparison')).json();
  expect(comparison.data_source).toBe('ACCOUNT_LEDGER');expect(comparison.dates).toEqual(['2026-10-02','2026-10-05']);expect(comparison.ranked).toBeGreaterThanOrEqual(2);
  await expect(page.getByRole('region',{name:'참여자와 CORE 지수 그래프'})).toContainText('원화 평가금액이 아닙니다.');
  const me=await(await page.request.get('/api/v1/me')).json();
  const myRow=comparison.items.find((r:{participant_id:string})=>r.participant_id===me.participant_id);
  await expect(page.getByRole('region',{name:'운용 기록 참여자 순위'})).toContainText('참여자 01');
  const row=page.getByRole('row').filter({has:page.getByRole('button',{name:'참여자 06',exact:true})});
  if(comparison.ranked===2){
    await expect(row).toContainText('평가 기록 없음');
    execFileSync(path.resolve('../.venv/bin/python'),[path.resolve('../scripts/append_ledger_comparison_fixture.py'),'--directory',directory],{stdio:'pipe'});
    await expect(row).toContainText('공통 기간 비교 가능',{timeout:25_000});
    const updated=await(await page.request.get('/api/v1/me/performance/comparison')).json();
    expect(updated.ranked).toBe(3);expect(updated.dates).toEqual(comparison.dates);
  }
  await page.screenshot({path:path.join(directory,`ranking-${viewport.width}.png`),fullPage:true});
  await page.getByRole('link',{name:'공통 기간의 내 성과·기여도'}).click();
  const common=await report(page,'?comparison=common');expect(common.metrics).toEqual(myRow.metrics);
  const attr=await(await page.request.get('/api/v1/me/performance/contributions?comparison=common')).json();
  expect(attr.cumulative_return).toBe(common.metrics.cumulative_return);expect(attr.reconciliation.reconciled).toBe(true);
  await expect(page.getByText(/참여자 비교와 같은 공통 관측 기간/)).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:path.join(directory,`common-${viewport.width}.png`),fullPage:true});
  await page.goto(`/review?decision_id=${own.decision_context.report_decision_id}`);
  await expect(page.getByRole('heading',{name:'확정 당시 판단 · v1'})).toBeVisible();
  await page.goto('/ranking?source=demo');
  await expect(page.getByText('과거 가격 기준 · 실제 운용 성과 아님',{exact:true})).toBeVisible();
  const legacy=(await(await page.request.get('/api/v1/comparison/rankings')).json()).items[0];
  if(legacy){await page.goto(`/participants/${legacy.participant_id}?source=demo`);await expect(page.getByText(/Excess는|과거 가격 기준/).first()).toBeVisible();}
  await signIn(page,1);await page.goto('/dashboard');
  expect((await report(page)).observations).toBe(0);
  await expect(page.getByRole('region',{name:'성과 적용 판단'})).toContainText('이전 판단 v1 성과 상세 보기');
  await expect(page.getByRole('img',{name:/누적수익률:/})).toHaveCount(0);
  await page.getByRole('region',{name:'성과 적용 판단'}).getByRole('link',{name:'이전 판단 v1 성과 상세 보기'}).click();
  await expect(page.getByRole('heading',{name:'확정 당시 판단 · v1'})).toBeVisible();
  await signIn(page,2);await page.goto('/dashboard');
  const one=await report(page);expect(one.observations).toBe(1);expect(one.metrics.cumulative_return).toBeNull();
  await expect(page.getByRole('region',{name:'기록된 평가액'})).toContainText('기준 100 지수 100.00');
  await expect(page.getByText(/첫 평가 기록 1건/)).toBeVisible();
  await expect(page.getByRole('img',{name:/누적수익률:/})).toHaveCount(0);
  await page.goto('/ranking');await expect(page.getByRole('region',{name:'선택 참여자 성과'})).toContainText('평가 기록 1건');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:path.join(directory,`one-${viewport.width}.png`),fullPage:true});
  await signIn(page,4);await page.goto('/ranking');
  await expect(page.getByRole('region',{name:'선택 참여자 성과'})).toContainText('포트폴리오 확정 기록 없음');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  expect(errors).toEqual([]);
 });
}
