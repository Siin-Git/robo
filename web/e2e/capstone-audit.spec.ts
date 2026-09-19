import { test, expect, Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { themeLabel, assetLabel } from '../lib/constants';
import { Comparison } from '../lib/api/comparison';

const audit = JSON.parse(readFileSync('../.work/capstone_audit.json','utf8'));
const pct = (n:number) => `${(n*100).toFixed(2)}%`;
const ret = (n:number) => `${n>0?'+':''}${pct(n)}`;
const excess = (n:number) => `${n>0?'+':''}${(n*100).toFixed(2)}%p`;
function rendered(r:Comparison) {
 const m=r.metrics;
 return {nav:m.nav.toFixed(2),cumulative_return:ret(m.cumulative_return),core_return:ret(m.core_return),
  excess_return:excess(m.excess_return),mdd:pct(m.mdd),volatility:pct(m.volatility!),sharpe:m.sharpe!.toFixed(2)};
}
async function checkPanel(page:Page, r:Comparison) {
 await expect(page.locator('h1')).toContainText(r.display_name);
 for (const theme of r.themes) await expect(page.getByText(`+ ${themeLabel(theme)}`,{exact:true})).toBeVisible();
 for (const [key,value] of Object.entries(rendered(r))) await expect(page.locator(`[data-metric="${key}"] .kpi-value`)).toHaveText(value);
 await expect(page.getByText(/시연용 가상 NAV · 실제 Forward Test 실적이 아닙니다/)).toBeVisible();
 await expect(page.locator('path.recharts-line-curve')).toHaveCount(2);
 // Inspect the actual data handed to the rendered Recharts instance, not a second fetch.
 const chartData = await page.locator('.recharts-wrapper').evaluate(element => {
  const key=Object.keys(element).find(k=>k.startsWith('__reactFiber$'))!;
  let fiber=(element as any)[key];
  while(fiber) {
   if (Array.isArray(fiber.memoizedProps?.data) && fiber.memoizedProps.data[0]?.personalized_nav!==undefined) return fiber.memoizedProps.data;
   fiber=fiber.return;
  }
  return null;
 });
 expect(chartData).toEqual(r.series);
}

test('13 real browser logins: seed themes, all KPI, chart data, ranking, allocation, logout and refresh',async({page,context})=>{
 test.setTimeout(240_000);
 const failures:string[]=[]; page.on('pageerror',e=>failures.push(e.message));
 const requests:string[]=[]; page.on('request',r=>requests.push(new URL(r.url()).pathname));
 for (let i=0;i<13;i++) {
  const account=audit.accounts[i]; const r:Comparison=audit.reports[i];
  await test.step(account.email, async()=>{
   await page.goto('/login');
   await page.getByLabel('이메일',{exact:true}).fill(account.email);
   await page.getByLabel('비밀번호',{exact:true}).fill('Capstone-Demo-2026!');
   await page.getByRole('button',{name:'로그인',exact:true}).click();
   await expect(page).toHaveURL(/\/dashboard$/);
   await checkPanel(page,r);
   await page.reload(); await checkPanel(page,r);
   const user=await (await page.request.get('/api/v1/auth/me')).json();
   expect(user.participant_id).toBe(account.participant_id);
   await page.getByRole('link',{name:'13명 성과 비교'}).click();
   await expect(page.locator('tbody tr')).toHaveCount(13);
   const row=page.locator('tbody tr').filter({has:page.getByRole('link',{name:new RegExp(r.display_name)})});
   const values=rendered(r);
   expect(await row.locator('td').allTextContents()).toEqual([
    String(audit.rankings.return.find((a:any)=>a.participant_id===r.participant_id).rank).padStart(2,'0'),
    r.display_name+'ME',r.themes.map(themeLabel).join(''),values.cumulative_return,values.excess_return,values.mdd,values.sharpe]);
   await page.getByLabel('정렬 기준').selectOption('volatility');
   await expect(row.locator('td')).toHaveCount(8);
   await expect(row.locator('td').nth(6)).toHaveText(values.volatility);
   await row.locator('td').last().click();
   await expect(page).toHaveURL(new RegExp(`/participants/${r.participant_id}$`));
   await checkPanel(page,r);
   const allocation=page.getByRole('region',{name:'현재 Personalized Portfolio 구성'});
   const bars=await allocation.locator('div.grid').evaluateAll(rows=>rows.map(row=>Array.from(row.querySelectorAll('span')).map(e=>e.textContent)));
   expect(bars).toEqual([...r.allocation].filter(w=>w.weight>0).sort((a,b)=>b.weight-a.weight).map(w=>[assetLabel(w.asset_id),pct(w.weight)]));
   await allocation.locator('summary').click();
   const coreRows=await allocation.locator('tbody tr').evaluateAll(rows=>rows.map(row=>Array.from(row.querySelectorAll('td')).map(e=>e.textContent)));
   const ids=Array.from(new Set([...r.core_allocation,...r.allocation].map(w=>w.asset_id)));
   expect(coreRows).toEqual(ids.map(id=>{
    const c=r.core_allocation.find(w=>w.asset_id===id)?.weight??0;
    const p=r.allocation.find(w=>w.asset_id===id)?.weight??0;
    return [assetLabel(id),pct(c),pct(p),c===0&&p===0?'—':excess(p-c)];
   }));
   const session=(await context.cookies()).find(c=>c.name==='ra_session')!.value;
   await page.getByRole('button',{name:'로그아웃',exact:true}).click();
   await expect(page).toHaveURL(/\/login$/);
   expect((await context.cookies()).filter(c=>['ra_session','ra_csrf'].includes(c.name))).toHaveLength(0);
   expect((await page.request.get('/api/v1/me/comparison')).status()).toBe(401);
   expect((await page.request.get('/api/v1/auth/me',{headers:{Cookie:`ra_session=${session}`}})).status()).toBe(401);
  });
 }
 expect(failures).toEqual([]);
 expect(requests.filter(path=>path==='/api/v1/rankings'||path.startsWith('/api/v1/me/performance'))).toEqual([]);
});

test('five full numeric sort orders, rank numbers and dynamic Top 3 styling',async({page})=>{
 await page.goto('/login');
 await page.getByLabel('이메일',{exact:true}).fill('capstone01@example.com');
 await page.getByLabel('비밀번호',{exact:true}).fill('Capstone-Demo-2026!');
 await page.getByRole('button',{name:'로그인',exact:true}).click();
 await expect(page).toHaveURL(/\/dashboard$/);
 await page.goto('/ranking');
 for(const basis of ['return','excess','mdd','volatility','sharpe']) {
  await page.getByLabel('정렬 기준').selectOption(basis);
  const expected=audit.rankings[basis];
  await expect(page.locator('tbody tr').first()).toContainText(expected[0].display_name);
  await expect(page.locator(`th[aria-sort]`)).toHaveText({return:'Return',excess:'Excess',mdd:'MDD',volatility:'Volatility',sharpe:'Sharpe'}[basis]!);
  const actual=await page.locator('tbody tr').evaluateAll(rows=>rows.map(row=>({
   href:row.querySelector('a')!.getAttribute('href'),rank:row.querySelector('td')!.textContent,
   highlighted:row.className.includes('topRow'),background:getComputedStyle(row.querySelector('td')!).backgroundColor
  })));
  expect(actual.map(r=>r.href)).toEqual(expected.map((r:any)=>`/participants/${r.participant_id}`));
  expect(actual.map(r=>r.rank)).toEqual(Array.from({length:13},(_,i)=>String(i+1).padStart(2,'0')));
  expect(actual.filter(r=>r.highlighted).map(r=>r.href)).toEqual(expected.slice(0,3).map((r:any)=>`/participants/${r.participant_id}`));
  expect(actual[0].background).not.toBe(actual[3].background);
 }
});
