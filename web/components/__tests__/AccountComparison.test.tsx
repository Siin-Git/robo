import {render,screen,fireEvent,cleanup,within} from '@testing-library/react';
import {afterEach,beforeEach,it,expect,vi} from 'vitest';
import {AccountComparison} from '../verification/AccountComparison';
const state=vi.hoisted(()=>({query:{} as any}));
vi.mock('@tanstack/react-query',()=>({useQuery:()=>state.query}));
const fixture=()=>({available:true,historical_start:'2026-10-01',historical_end:'2026-10-24',forward_start:'2026-10-26',decision_confirmed_at:'2026-10-12T00:00:00Z',summary:{start:'2026-10-01',end:'2026-10-26',observations:18,personal_return:-.04,core_return:-.05,difference_pp:.01,missing_observations:1},series:[{date:'2026-10-01',personal_nav:100,core_nav:100,data_kind:'HISTORICAL_REPLAY'},{date:'2026-10-26',personal_nav:96,core_nav:95,data_kind:'FORWARD_SIMULATION'},{date:'2026-10-27',personal_nav:null,core_nav:null,data_kind:'FORWARD_SIMULATION'}]});
beforeEach(()=>{state.query={data:fixture(),isLoading:false,isError:false,isFetching:false,dataUpdatedAt:Date.parse('2026-10-28T00:00:00Z'),refetch:vi.fn()};});
afterEach(cleanup);
it('shows the server account-wide comparison regardless of the latest decision window',()=>{
 render(<AccountComparison/>);expect(screen.getByText('2026.10.01 — 2026.10.26')).toBeVisible();expect(screen.getByText('-4.00%')).toBeVisible();expect(screen.getByText('-5.00%')).toBeVisible();expect(screen.getByText('+1.00%p')).toBeVisible();expect(screen.getByText(/18개/)).toBeVisible();expect(screen.queryByText(/저장된 구성을 과거 가격/)).not.toBeInTheDocument();
 fireEvent.click(screen.getByText('전체 기간 계산 근거와 일별 평가액'));const table=screen.getByRole('table');expect(within(table).getAllByText('미확보')).toHaveLength(2);expect(within(table).getByText('과거 가격 적용')).toBeVisible();expect(screen.getByText(/평가 미확보 1일/)).toBeVisible();
});
it('keeps a failed refresh explicitly stale and offers its own retry',()=>{state.query.isError=true;render(<AccountComparison/>);expect(screen.getByRole('alert')).toHaveTextContent('이전 조회');expect(screen.getByText('-4.00%')).toBeVisible();fireEvent.click(screen.getByRole('button'));expect(state.query.refetch).toHaveBeenCalledOnce();});
it('does not turn an initial error or missing archive into a zero result',()=>{state.query.data=undefined;state.query.isError=true;const v=render(<AccountComparison/>);expect(screen.getByRole('alert')).toHaveTextContent('불러오지 못했습니다');expect(screen.queryByText('0.00%')).not.toBeInTheDocument();state.query.isError=false;state.query.data={available:false};v.rerender(<AccountComparison/>);expect(screen.getByText(/공통 평가 기록이 부족/)).toBeVisible();});
it.each([{observations:1},{personal_return:null},{core_return:NaN},{end:'2026-10-01'}])('does not display incomplete account-wide summaries %j',patch=>{Object.assign(state.query.data.summary,patch);render(<AccountComparison/>);expect(screen.queryByText('-4.00%')).not.toBeInTheDocument();});
it('preserves genuine zero results',()=>{Object.assign(state.query.data.summary,{personal_return:0,core_return:0,difference_pp:0});render(<AccountComparison/>);expect(screen.getAllByText('0.00%')).toHaveLength(2);expect(screen.getByText('0.00%p')).toBeVisible();});
