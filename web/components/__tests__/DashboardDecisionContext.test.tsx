import {render,screen,cleanup} from '@testing-library/react';
import {describe,it,expect,afterEach} from 'vitest';
import {DashboardDecisionContext} from '../dashboard/DashboardDecisionContext';
import type {DecisionContext} from '@/app/(app)/dashboard/performance-data';
afterEach(cleanup);
const v1={decision_id:'original',version:1,target_effective_date:'2026-10-01'};
const v2={decision_id:'pending',version:2,target_effective_date:'2026-10-05'};
const base:DecisionContext={as_of:'2026-10-03',selection_basis:'KST_EFFECTIVE_DATE',status:'ACTIVE',active_decision:v1,pending_decision:v2,previous_decision:null,report_decision_id:'original',window_start:'2026-10-01',window_end_exclusive:'2026-10-04'};
describe('dashboard decision context',()=>{
  it('keeps current performance distinct from a future confirmation',()=>{
    render(<DashboardDecisionContext context={base} observations={2} start="2026-10-01" end="2026-10-02"/>);
    expect(screen.getByText(/현재 운용 판단: v1/)).toBeVisible();
    expect(screen.getByText(/적용 대기 판단: v2/)).toBeVisible();
    expect(screen.getByText(/성과·기여도·기본 구성 비교 기준: v1/)).toHaveTextContent('평가일 2개');
    expect(screen.getByRole('link',{name:'대기 판단 상세 보기'})).toHaveAttribute('href','/review?decision_id=pending');
  });
  it('shows insufficient new history and an explicit previous-detail link',()=>{
    render(<DashboardDecisionContext context={{...base,as_of:'2026-10-05',active_decision:v2,pending_decision:null,previous_decision:v1,report_decision_id:'pending'}} observations={1} start="2026-10-05" end="2026-10-05"/>);
    expect(screen.getByText(/현재 운용 판단: v2/)).toBeVisible();
    expect(screen.getByText(/현재 판단의 평가 기록이 부족/)).toBeVisible();
    expect(screen.getByRole('link',{name:'이전 판단 v1 성과 상세 보기'})).toHaveAttribute('href','/review?decision_id=original');
    expect(screen.queryByText(/적용 대기 판단: v/)).toBeNull();
  });
  it('does not present a first pending decision as already operating',()=>{
    render(<DashboardDecisionContext context={{...base,status:'AWAITING_INITIAL_EFFECTIVE_DATE',active_decision:null,report_decision_id:null}} observations={0} start={null} end={null}/>);
    expect(screen.getByText(/현재 운용 판단: 없음 · 첫 목표 효력일 대기/)).toBeVisible();
  });
});
