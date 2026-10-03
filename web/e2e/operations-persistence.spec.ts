import {test,expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import path from 'node:path';
test('recorded user survives server restart and mobile review remains usable',async({page})=>{
 const f=process.env.E2E_OPERATIONS_DATA_DIR!;const account=JSON.parse(readFileSync(path.join(f,'accounts.json'),'utf8')).accounts[0];
 await page.goto('/login');await page.getByLabel('이메일',{exact:true}).fill(account.email);await page.getByLabel('비밀번호',{exact:true}).fill(account.password);await page.getByRole('button',{name:'로그인',exact:true}).click();await expect(page).toHaveURL(/\/dashboard$/);
 await page.getByRole('link',{name:'최초 예상·실제 검토',exact:true}).click();await expect(page.getByText('검증용 합성 데이터 · 실제 운용 기록이 아닙니다. 아래 관측 값은 기능 검증용입니다.',{exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'확정 당시 판단 · v2'})).toBeVisible();
 const d=await(await page.request.get('/api/v1/me/decisions')).json();expect(d.items).toHaveLength(2);
 await page.setViewportSize({width:390,height:844});await expect(page.getByLabel('선택 이유')).toBeVisible();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:'/private/tmp/robo-operations-e2e/review-mobile.png',fullPage:true});
});
