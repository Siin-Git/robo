import {test,expect,type Page} from '@playwright/test';
import {readFileSync} from 'node:fs';
import path from 'node:path';

const directory=process.env.E2E_OPERATIONS_DATA_DIR!;
async function signIn(page:Page,index=0){
  const account=JSON.parse(readFileSync(path.join(directory,'accounts.json'),'utf8')).accounts[index];
  await page.goto('/login');
  await page.getByLabel('이메일',{exact:true}).fill(account.email);
  await page.getByLabel('비밀번호',{exact:true}).fill(account.password);
  await page.getByRole('button',{name:'로그인',exact:true}).click();
  await expect(page).not.toHaveURL(/\/login/);
}

for(const [index,viewport] of [[6,{width:1440,height:1000}],[7,{width:390,height:844}]] as const){
  test(`existing ETF frontier and confirmation after research ${viewport.width}`,async({page})=>{
    expect(JSON.parse(readFileSync(path.join(directory,'monday-fixture.json'),'utf8')).data_kind).toBe('TEST_FIXTURE');
    await page.setViewportSize(viewport);
    await signIn(page,index);
    expect((await(await page.request.get('/api/v1/me/decisions')).json()).items).toEqual([]);
    await page.goto('/setup/portfolio?step=risk');
    await page.getByRole('radio',{name:'매분기'}).check();
    await page.getByRole('button',{name:'다음: 투자 인사이트 반영'}).click();
    await page.getByRole('region',{name:'주도주·수출 전략 자료'}).getByRole('link',{name:'주도주 모델 · 자료 검토'}).click();
    await expect(page.getByLabel('전략 변형 선택')).toHaveValue('');
    await page.getByRole('link',{name:'투자 선택으로 돌아가기'}).click();
    await page.getByRole('button',{name:'인공지능 선택',exact:true}).click();
    await page.getByRole('button',{name:'다음: 변경 전·후 비교'}).click();
    await expect(page.getByLabel('확정 전 리밸런싱 주기')).toContainText('매분기');
    await expect(page.getByRole('region',{name:'테마 적용 전후 Efficient Frontier 위치'})).toBeVisible();
    await page.getByRole('button',{name:'포트폴리오 확정 · 성과 확인'}).click();
    await expect(page).toHaveURL(/\/portfolio$/);
    await expect(page.getByLabel('저장된 리밸런싱 주기')).toContainText('매분기');
    await page.reload();
    await expect(page.getByLabel('저장된 리밸런싱 주기')).toContainText('매분기');
    const d=(await(await page.request.get('/api/v1/me/decisions')).json()).items[0];
    expect(d.weights['theme:ai']).toBeGreaterThan(0);
    expect(d.weights['theme:leader_stock']).toBeUndefined();
    expect(d.expectations.expected_return.definition.cost_basis).toBe('EXCLUDES_TRANSACTION_COSTS');
    const review=await(await page.request.get(`/api/v1/me/decisions/${d.decision_id}/review`)).json();
    expect(review.actual.observations).toBe(0);
    expect(review.horizons.every((x:{status:string;cumulative_return:number|null})=>x.status==='NOT_REACHED'&&x.cumulative_return===null)).toBe(true);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:path.join(directory,`confirmed-${viewport.width}.png`),fullPage:true});
  });
}
for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
  test(`research variants and honest comparisons ${viewport.width}`,async({page})=>{
    await page.setViewportSize(viewport);
    const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
    await signIn(page);
    const before=await(await page.request.get('/api/v1/me/decisions')).json();
    const accountBefore=await(await page.request.get('/api/v1/me/performance/dashboard')).json();
    await page.goto('/strategies?strategy=leader_stock');
    await expect(page.getByRole('heading',{name:'주도주 모델 · 운용 준비 전'})).toBeVisible();
    await expect(page.getByLabel('전략 변형 선택')).toHaveValue('');
    await expect(page.getByRole('img',{name:'과거 모델 지수, 실제 계좌 운용 아님'})).toHaveCount(0);
    await page.getByLabel('전략 변형 선택').selectOption('leader_top10');
    await expect(page.getByText(/관측 177개/)).toBeVisible();
    await expect(page.getByText(/월말 라벨/)).toBeVisible();
    await expect(page.getByRole('img',{name:'과거 모델 지수, 실제 계좌 운용 아님'})).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:path.join(directory,`leader-${viewport.width}.png`),fullPage:true});
    await page.getByLabel('전략 자료 선택').selectOption('export_stock');
    await expect(page.getByRole('heading',{name:'수출 모델 · 운용 준비 전'})).toBeVisible();
    await expect(page.getByLabel('전략 변형 선택')).toHaveValue('');
    await expect(page.getByRole('img',{name:'과거 모델 지수, 실제 계좌 운용 아님'})).toHaveCount(0);
    await page.getByLabel('전략 변형 선택').selectOption('export_historical');
    await expect(page.getByText(/관측 1754개/)).toBeVisible();
    await expect(page.getByText(/과거 신호월 2026-07 · 리밸런싱 2026-09-01 · 체결창 종료 스냅샷 2026-09-03/)).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:path.join(directory,`export-${viewport.width}.png`),fullPage:true});
    await page.goto('/dashboard');
    await page.getByText('시장·안전자산 후보와 필요한 결정',{exact:true}).click();
    await expect(page.getByText('KOSPI 가격지수',{exact:true})).toBeVisible();
    await expect(page.getByText('원화 무이자 현금',{exact:true})).toBeVisible();
    const report=await(await page.request.get('/api/v1/me/performance/dashboard')).json();
    expect(report.comparators.find((x:{key:string})=>x.key==='market').reason).toBe('BENCHMARK_DEFINITION_NOT_CONFIGURED');
    expect(report.comparators.find((x:{key:string})=>x.key==='safe_asset').return).toBeNull();
    const review=await(await page.request.get(`/api/v1/me/decisions/${report.decision_context.report_decision_id}/review`)).json();
    expect(review.actual.observations).toBe(3);
    expect(review.horizons.every((x:{status:string})=>x.status==='NOT_REACHED')).toBe(true);
    expect(review.comparisons.every((x:{difference:number|null})=>x.difference===null)).toBe(true);
    await page.goto(`/review?decision_id=${report.decision_context.report_decision_id}`);
    const comparison=page.getByLabel('예상 실제 비교 조건');
    await expect(comparison).toContainText('비교 불가');
    await comparison.getByText('기간·단위·통화·비용·기준 대조',{exact:true}).first().click();
    await expect(comparison.getByRole('columnheader',{name:'저장 예상'}).first()).toBeVisible();
    await expect(comparison).toContainText('2026-10-01');
    await expect(comparison).toContainText('2026-10-05');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await page.screenshot({path:path.join(directory,`expectations-${viewport.width}.png`),fullPage:true});
    expect(await(await page.request.get('/api/v1/me/decisions')).json()).toEqual(before);
    expect((await(await page.request.get('/api/v1/me/performance/dashboard')).json()).metrics).toEqual(accountBefore.metrics);
    expect(errors).toEqual([]);
  });
}
