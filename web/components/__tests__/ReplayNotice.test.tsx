import {render,screen,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {ReplayNotice} from '../dashboard/ReplayNotice';
const response=vi.hoisted(()=>({data:null as any}));
const route=vi.hoisted(()=>({source:''}));
vi.mock('@tanstack/react-query',()=>({useQuery:()=>response}));
vi.mock('next/navigation',()=>({useSearchParams:()=>new URLSearchParams(route.source?'source='+route.source:''),usePathname:()=>'/dashboard'}));
afterEach(()=>{cleanup();route.source='';});
it('is absent from normal operation and distinguishes incomplete source-gap replay',()=>{
 response.data={enabled:false};const r=render(<ReplayNotice/>);expect(screen.queryByRole('status')).toBeNull();
 response.data={enabled:true,replay_context:{label:'현재 확정 구성을 과거 10거래일에 적용한 모의실험',ready:15,required:15,completed:8,status:'INCOMPLETE',dates:Array(10),start:'2026-09-16',end:'2026-10-02',initial_capital_krw:1e8,excluded_dates:[{date:'2026-09-24',missing_assets:['kr_equity']}]}};
 r.rerender(<ReplayNotice/>);expect(screen.getByRole('status')).toHaveTextContent('처리 8/15');
 expect(screen.getByRole('status')).toHaveTextContent('연속 10거래일 아님');
 expect(screen.getByRole('status')).toHaveTextContent('순위 보류');
 expect(screen.getByRole('status')).toHaveTextContent('3개월·6개월 추적 실적이 아닙니다');
});
it('does not describe the legacy backtest page as the competition run',()=>{
 response.data={enabled:true,replay_context:null};route.source='demo';render(<ReplayNotice/>);
 expect(screen.getByRole('status')).toHaveTextContent('경쟁 재생 원장과 별도');
 expect(screen.queryByText(/READY/)).toBeNull();
});
