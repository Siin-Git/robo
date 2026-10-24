import {render,screen,cleanup} from '@testing-library/react';
import {afterEach,it,expect,vi} from 'vitest';
import {Continuity} from '../dashboard/Continuity';
const response=vi.hoisted(()=>({data:null as any,isError:false}));
vi.mock('@tanstack/react-query',()=>({useQuery:()=>response}));
vi.mock('recharts',()=>({ResponsiveContainer:()=>null,LineChart:()=>null,Line:()=>null,XAxis:()=>null,YAxis:()=>null,Tooltip:()=>null,ReferenceLine:()=>null}));
afterEach(()=>{cleanup();response.data=null;response.isError=false});
it('does not invent a carryover when none exists',()=>{response.data={available:false};render(<Continuity/>);expect(screen.queryByRole('region')).toBeNull()});
it('labels retrospective data and waits for actual forward valuations',()=>{
 response.data={available:true,historical_start:'2026-10-01',historical_end:'2026-10-24',forward_start:'2026-10-26',decision_confirmed_at:'2026-10-11T16:00Z',forward_observations:0,opening:{as_of:'2026-10-23',nav:98000000,cash_balance:1234,holdings:[]},series:[{date:'2026-10-23',personal_index:98,core_index:99,data_kind:'HISTORICAL_REPLAY'}]};
 render(<Continuity/>);expect(screen.getByText(/당시 투자 판단의 실적을 뜻하지/)).toBeVisible();expect(screen.getByRole('status')).toHaveTextContent('첫 정상 평가 대기');expect(screen.getByText(/98,000,000원/)).toBeVisible();expect(screen.getByText(/자동운용 구간은 별도 기록/)).toBeVisible();
});
it('reports fetch failure rather than saying no history',()=>{response.isError=true;render(<Continuity/>);expect(screen.getByRole('alert')).toHaveTextContent('확인하지 못했습니다')});
