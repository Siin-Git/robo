import { render,screen,fireEvent,within } from '@testing-library/react';
import { QueryClient,QueryClientProvider } from '@tanstack/react-query';
import { vi,expect,it,beforeEach } from 'vitest';
import { StrategyFrontierChart } from '@/app/(app)/setup/portfolio/FrontierChart';
import { SetupStyleProvider } from '@/app/(app)/setup/SetupStyleProvider';
import { get } from '@/lib/api/client';
vi.mock('@/lib/api/client',()=>({get:vi.fn()}));
beforeEach(()=>{vi.stubGlobal('ResizeObserver',class {observe(){} disconnect(){}});});
it('keeps assets readable independently of extreme model values and retains models during curve focus',async()=>{
 const selection={expected_return:.05,volatility:.08};
 vi.mocked(get).mockResolvedValue({period:{start:'2024-11-08',end:'2026-09-11',observations:97},items:[
  {id:'leader_stock',label:'주도주 모델',expected_return:.66,volatility:.29,sharpe:2.17,snapshot_date:'2026-10-01',weights:[{ticker:'069500',company:'KODEX 200',weight:1}]},
  {id:'export_stock',label:'수출주 모델',expected_return:.36,volatility:.30,sharpe:1.1,snapshot_date:'2026-09-03',weights:[{ticker:'005930',company:'삼성전자',weight:1}]}]});
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
 render(<QueryClientProvider client={client}><SetupStyleProvider><StrategyFrontierChart points={[{expected_return:.04,volatility:.06},{expected_return:.07,volatility:.13}]} assets={[{asset_id:'us_equity',name:'미국주식',cat:'주식',expected_return:.08,volatility:.22}]} selected={selection} inspectedId={null} onInspect={()=>{}}/></SetupStyleProvider></QueryClientProvider>);
 const leader=await screen.findByRole('img',{name:/주도주 모델: 과거 수익률 추정 66.00%/});
 expect(Number(leader.querySelector('text')?.getAttribute('y'))).toBeGreaterThanOrEqual(16);
 const exporter=screen.getByRole('img',{name:/수출주 모델: 과거 수익률 추정 36.00%/});
 const main=within(screen.getByRole('region',{name:'기본 Frontier와 자산 비교'}));
 const overview=within(screen.getByRole('region',{name:'주도주·수출주 모델 전체 비교'}));
 const base=main.getByRole('img',{name:'테마 적용 전 Base Portfolio'});
 expect(main.getByRole('button',{name:'미국주식 자산 정보 보기'})).toBeTruthy();
 expect(main.queryByRole('img',{name:/주도주 모델:/})).toBeNull();
 expect(main.getByRole('group').textContent).not.toContain('66.9%');
 const modelCoordinate=leader.querySelector('path')?.getAttribute('d');
 expect(leader.querySelector('path')?.getAttribute('d')).not.toEqual(exporter.querySelector('path')?.getAttribute('d'));
 const baseY=Number(base.querySelector('circle')?.getAttribute('cy'));
 fireEvent.click(screen.getByRole('button',{name:'Frontier 확대'}));
 expect(overview.getByRole('img',{name:/주도주 모델:/})).toBeTruthy();
 expect(leader.querySelector('path')?.getAttribute('d')).toEqual(modelCoordinate);
 expect(main.queryByRole('button',{name:'미국주식 자산 정보 보기'})).toBeNull();
 expect(screen.getByRole('article',{name:'주도주 모델 비교 지표'})).toBeTruthy();
 expect(Number(base.querySelector('circle')?.getAttribute('cy'))).toBeLessThan(baseY);
 fireEvent.click(screen.getByRole('button',{name:'전체 비교'}));
 expect(screen.getByRole('img',{name:/주도주 모델:/})).toBeTruthy();
 expect(main.getByRole('button',{name:'미국주식 자산 정보 보기'})).toBeTruthy();
 expect(screen.getByRole('button',{name:'전체 비교'}).getAttribute('aria-pressed')).toBe('true');
 expect(selection).toEqual({expected_return:.05,volatility:.08});
});
