import {test,expect,type Page} from '@playwright/test';
import {readFileSync,mkdirSync} from 'node:fs';
import {execFileSync} from 'node:child_process';
import path from 'node:path';

const directory=process.env.E2E_OPERATIONS_DATA_DIR!;
if(!directory?.startsWith('/private/tmp/') || !readFileSync(path.join(directory,'verification-ui-marker'),'utf8').includes('TEST_FIXTURE')) throw new Error('Require the disposable verification fixture, never production.');
const root=path.resolve(process.cwd(),'..');
const evidence=process.env.E2E_EVIDENCE_DIR??'/private/tmp/robo-pr20-ui-evidence';
mkdirSync(evidence,{recursive:true});
const account=JSON.parse(readFileSync(path.join(directory,'accounts.json'),'utf8')).accounts[0];
const original=JSON.parse(readFileSync(path.join(directory,'original.json'),'utf8'));
function fixture(mode:string){return execFileSync(path.join(root,'.venv/bin/python'),[path.join(root,'scripts/seed_verification_ui_fixture.py'),'--directory',directory,'--mode',mode],{cwd:root,encoding:'utf8'});}
function counts(){return JSON.parse(fixture('counts'));}
async function login(page:Page){
 await page.goto('/login');await page.getByLabel('이메일',{exact:true}).fill(account.email);await page.getByLabel('비밀번호',{exact:true}).fill(account.password);
 await page.getByRole('button',{name:'로그인',exact:true}).click();await expect(page).toHaveURL(/\/dashboard$/);
}

test('real API: waiting reason, keyboard panel, KEEP/ADJUST, same-decision return and synthetic exclusion',async({page})=>{
 const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
 const before=counts();await login(page);
 await expect(page.getByRole('heading',{name:'공동 운용 시작일 미지정',exact:true})).toBeVisible();
 await expect(page.getByText(/준비 인원: 15\/15명/)).toBeVisible();
 await page.screenshot({path:path.join(evidence,'dashboard-wait-desktop.png'),fullPage:true});
 await page.getByRole('link',{name:'내 포트폴리오',exact:true}).first().click();
 const base=page.getByRole('button',{name:'테마 적용 전 Base Portfolio',exact:true});
 await base.focus();await base.press('Enter');
 const panel=page.getByRole('complementary',{name:'투자 판단 검증'});
 await expect(panel.getByRole('heading',{name:'투자 판단 검증',exact:true})).toBeFocused();
 await expect(panel.getByRole('heading',{level:4})).toHaveCount(3);
 await expect(panel).toContainText('격리 테스트용 판단');
 await expect(panel).toContainText('공동 운용 시작일 미지정');
 const region=page.getByRole('region',{name:'테마 적용 전후 Efficient Frontier 위치'});
 const svg=region.locator('svg').first();
 const panelBox=(await panel.boundingBox())!,chartBox=(await svg.boundingBox())!;
 expect(panelBox.x).toBeGreaterThan(chartBox.x+chartBox.width-1);
 await region.scrollIntoViewIfNeeded();await region.screenshot({path:path.join(evidence,'verification-desktop.png')});
 await panel.press('Escape');await expect(base).toBeFocused();await expect(panel).toHaveCount(0);
 const personal=page.getByRole('button',{name:'테마 적용 후 Personalized Portfolio',exact:true});
 await personal.focus();await personal.press('Space');await expect(panel).toBeVisible();
 await panel.getByRole('button',{name:'투자 판단 검증 닫기'}).click();await expect(personal).toBeFocused();
 const legend=page.getByRole('button',{name:'Personalized · 판단 보기',exact:true});
 await legend.click();await panel.press('Escape');await expect(legend).toBeFocused();await legend.click();
 const initial=await(await page.request.get(`/api/v1/me/decisions/${original.decision_id}/verification`)).json();
 expect(initial.original.personalized.expected_return).toBe(original.expectations.expected_return.value);
 expect(initial.actual.status).toBe('UNAVAILABLE');expect(initial.valuation_job.valuation_completed).toBe(false);
 expect(JSON.stringify(initial)).not.toContain('internal_tracking');
 await panel.getByRole('link',{name:'이 판단의 검토 기록 보기'}).click();
 await expect(page).toHaveURL(new RegExp(original.decision_id));
 const keep='격리 검증: 관측 기간이 부족하므로 확정 비중을 유지합니다.';
 await page.getByLabel('선택 이유').fill(keep);await page.getByRole('button',{name:'구성 유지 선택',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('유지 선택을 저장했습니다');
 await page.screenshot({path:path.join(evidence,'review-saved-desktop.png'),fullPage:true});
 await page.getByRole('link',{name:'이 판단의 검증으로 돌아가기'}).click();
 await expect(panel).toBeVisible();await expect(panel).toContainText(keep);
 const saved=await(await page.request.get(`/api/v1/me/decisions/${original.decision_id}/verification`)).json();
 expect(saved.original).toEqual(initial.original);expect(saved.review.choice.action).toBe('KEEP');
 // ADJUST records a reason and opens the existing redesign route; never confirms a new decision.
 await panel.getByRole('link',{name:'이 판단의 검토 기록 보기'}).click();
 const adjust='격리 검증: 위험 근거를 재검토합니다. 새 구성은 아직 확정하지 않습니다.';
 await page.getByLabel('선택 이유').fill(adjust);await page.getByRole('button',{name:'조정 검토 · 재설계',exact:true}).click();
 await expect(page).toHaveURL(/adjustment_choice_id=/);
 await page.goto(`/portfolio?decision_id=${original.decision_id}&inspect=personalized`);
 await expect(panel).toContainText(adjust);
 await page.setViewportSize({width:390,height:844});
 await expect(panel).toBeVisible();const mobilePanel=(await panel.boundingBox())!,mobileChart=(await svg.boundingBox())!;
 expect(mobilePanel.y).toBeGreaterThan(mobileChart.y+mobileChart.height);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await region.screenshot({path:path.join(evidence,'verification-mobile.png')});
 const after=counts();for(const key of ['orders','trades','nav_daily','scheduled_jobs','portfolio_decisions']) expect(after[key]).toBe(before[key]);
 expect(after.portfolio_choices).toBe(before.portfolio_choices+2);
 expect((await(await page.request.get('/api/v1/me/decisions')).json()).items[0]).toEqual(original);
 // Stored success fixture is explicitly synthetic: NAV completion never makes it actual performance.
 fixture('nav');await page.reload();await expect(panel).toContainText('정상 NAV 저장 완료');
 await expect(panel).toContainText('합성 테스트 자료는 계좌 실적으로 사용하지 않습니다.');
 const synthetic=await(await page.request.get(`/api/v1/me/decisions/${original.decision_id}/verification`)).json();
 expect(synthetic.valuation_job.valuation_completed).toBe(true);expect(synthetic.actual.status).toBe('UNAVAILABLE');
 await region.screenshot({path:path.join(evidence,'synthetic-nav-excluded-mobile.png')});
 await page.goto('/dashboard?source=forward');await expect(page.getByText('검증용 합성 데이터 · 실제 운용 실적이 아닙니다.',{exact:true})).toBeVisible();
 expect(errors).toEqual([]);
});

test('real API: initial loading/error and cached refresh failure stay explicit',async({page})=>{
 await page.clock.install();
 await login(page);
 let release!:()=>void;
 const barrier=new Promise<void>(resolve=>{release=resolve;});
 await page.route('**/decisions/*/verification',async route=>{await barrier;await route.continue();});
 await page.goto('/portfolio');
 const region=page.getByRole('region',{name:'테마 적용 전후 Efficient Frontier 위치'});
 await expect(region.getByLabel('Loading')).toBeVisible();
 release();await expect(page.getByRole('button',{name:'Base · 판단 보기'})).toBeVisible();
 await page.unroute('**/decisions/*/verification');
 await page.getByRole('button',{name:'Base · 판단 보기'}).click();
 await page.route('**/decisions/*/verification',route=>route.abort('failed'));
 await page.clock.fastForward(61_000);await page.clock.resume();
 await expect(region.getByRole('alert')).toContainText('이전 조회 결과');
 await expect(page.getByRole('complementary',{name:'투자 판단 검증'})).toContainText('격리 테스트용 판단');
 await region.screenshot({path:path.join(evidence,'refresh-failure-desktop.png')});
 await page.unroute('**/decisions/*/verification');await region.getByRole('button',{name:'다시 조회',exact:true}).click();
 await expect(region.getByRole('alert')).toHaveCount(0);
 await page.route('**/decisions/*/verification',route=>route.abort('failed'));await page.reload();
 await expect(region.getByText('판단 기록을 불러오지 못했습니다.',{exact:true})).toBeVisible();
 await expect(region.getByRole('button',{name:'테마 적용 전 Base Portfolio'})).toHaveCount(0);
 await page.unroute('**/decisions/*/verification');await region.getByRole('button',{name:'Retry',exact:true}).click();
 await expect(region.getByRole('button',{name:'테마 적용 전 Base Portfolio'})).toBeVisible();
});
