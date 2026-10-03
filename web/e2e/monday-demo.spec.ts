import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import path from 'node:path';

test('synthetic Monday: current/pending, truthful shortage, preserved prior history',async({page})=>{
  const directory=process.env.E2E_OPERATIONS_DATA_DIR!;
  const accounts=JSON.parse(readFileSync(path.join(directory,'accounts.json'),'utf8')).accounts;
  const fixture=JSON.parse(readFileSync(path.join(directory,'monday-fixture.json'),'utf8'));
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  for(const scenario of fixture.cases){
    await page.context().clearCookies();
    await page.goto('/login');
    await page.getByLabel('이메일',{exact:true}).fill(accounts[scenario.account_index].email);
    await page.getByLabel('비밀번호',{exact:true}).fill(accounts[scenario.account_index].password);
    await page.getByRole('button',{name:'로그인',exact:true}).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    const report=await(await page.request.get('/api/v1/me/performance/dashboard')).json();
    expect(report.decision_context.as_of).toBe('2026-10-05');
    expect(report.observations).toBe(scenario.expected_observations);
    const panel=page.getByRole('region',{name:'성과 적용 판단'});
    await expect(panel).toContainText(`현재 운용 판단: v${scenario.expected_active_version}`);
    await expect(panel).toContainText(`적용 대기 판단: v${scenario.expected_pending_version}`);
    await expect(panel).toContainText(`평가일 ${scenario.expected_observations}개`);
    await expect(page.getByText(/검증용 합성 데이터 · 실제 운용 기록 아님/).first()).toBeVisible();
    const contribution=await(await page.request.get('/api/v1/me/performance/contributions')).json();
    expect(contribution.decision_context).toEqual(report.decision_context);
    expect([contribution.start,contribution.end]).toEqual([report.start,report.end]);
    for(const comparator of report.comparators){
      expect(comparator.decision_id).toBe(report.decision_context.report_decision_id);
      expect([comparator.start,comparator.end]).toEqual([report.start,report.end]);
    }
    if(scenario.expected_observations===0){
      expect(report.status).toBe('INSUFFICIENT_HISTORY');
      expect(report.metrics.cumulative_return).toBeNull();
      await expect(panel).toContainText('현재 판단의 평가 기록이 부족합니다.');
      await panel.getByRole('link',{name:'이전 판단 v1 성과 상세 보기'}).click();
    }else{
      expect(contribution.reconciliation.reconciled).toBe(true);
      await page.goto(`/review?decision_id=${scenario.original_decision_id}`);
    }
    await expect(page.getByRole('heading',{name:'확정 당시 판단 · v1'})).toBeVisible();
    await expect(page.getByText(/평가일 2개/)).toBeVisible();
    const old=await(await page.request.get(`/api/v1/me/decisions/${scenario.original_decision_id}/review`)).json();
    expect(old.actual.observations).toBe(2);
    for(const comparison of old.comparisons){expect(comparison.status).toBe('NOT_COMPARABLE');expect(comparison.difference).toBeNull();}
    await page.goto('/dashboard');await page.setViewportSize({width:390,height:844});
    await expect(panel).toContainText(`현재 운용 판단: v${scenario.expected_active_version}`);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:`/private/tmp/robo-monday-case-${scenario.account_index}.png`,fullPage:true});
    await page.setViewportSize({width:1440,height:1000});
  }
  expect(errors).toEqual([]);
});
