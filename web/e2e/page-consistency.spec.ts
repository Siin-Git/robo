import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const root=path.resolve(__dirname,'../..'),fixture=process.env.E2E_OPERATIONS_DATA_DIR!;
if(!fixture?.startsWith('/private/tmp/'))throw new Error('Disposable fixture required.');
const account=JSON.parse(fs.readFileSync(path.join(fixture,'accounts.json'),'utf8')).accounts[0];
const evidence=path.join(root,'docs/evidence/page-consistency');
const counts=()=>JSON.parse(execFileSync(path.join(root,'.venv/bin/python'),['scripts/seed_verification_ui_fixture.py','--directory',fixture,'--mode','counts'],{cwd:root,encoding:'utf8'}));
test('main pages remain readable and browsing does not change investment records',async({page})=>{
  test.setTimeout(180_000);fs.mkdirSync(evidence,{recursive:true});
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/login');await page.getByLabel('이메일').fill(account.email);await page.getByLabel('비밀번호').fill(account.password);
  await page.getByRole('button',{name:'로그인',exact:true}).click();await expect(page).toHaveURL(/dashboard|setup\/portfolio/);
  const before=counts();
  for(const [route,ready] of [
    ['/dashboard','보유자산과 운용 기록'],['/portfolio','목표 자산 구성'],['/views','저장된 투자 의견'],
    ['/performance','계산·데이터 상세'],['/review','이 판단의 검토 기록'],['/strategies','전략별 자료'],
    ['/ranking','비교 기준 보기'],['/account','로그인 내역'],
  ]){
    await page.setViewportSize({width:1440,height:1050});await page.goto(route);
    await expect(page.getByText(ready,{exact:false}).first()).toBeVisible();
    if(route==='/views'){
      await expect(page.getByRole('group',{name:'투자 테마 선택'})).toBeVisible();
      const rules=page.locator('details.view-rules');await expect(rules).not.toHaveAttribute('open','');
      await rules.locator('summary').press('Enter');await expect(rules).toHaveAttribute('open','');
      await expect(rules).toContainText('위험 한도');await rules.locator('summary').press('Enter');
    }
    await page.screenshot({path:path.join(evidence,`${route.slice(1)}-desktop.png`),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),{message:`${route} mobile overflow`}).toBe(true);
    await page.screenshot({path:path.join(evidence,`${route.slice(1)}-mobile.png`),fullPage:true});
  }
  expect(counts()).toEqual(before);expect(errors).toEqual([]);
});
