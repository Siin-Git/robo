import {render,screen,cleanup} from '@testing-library/react';
import {afterEach,describe,it,expect} from 'vitest';
import {ExpectationComparison} from '@/components/performance/ExpectationComparison';

afterEach(cleanup);
describe('expectation measurement alignment',()=>{
  it('shows actual minus expected in percentage points only for comparable metrics',()=>{
    render(<ExpectationComparison items={[{metric:'expected_return',status:'COMPARABLE',reason:null,difference:.0123,difference_unit:'fraction'}]}/>);
    expect(screen.getByText(/실제 − 예상 \+1.23%p/)).toBeInTheDocument();
    expect(screen.queryByText('비교 불가')).not.toBeInTheDocument();
  });
  it('retains specific missing legacy basis, cost, sampling and period reasons',()=>{
    render(<ExpectationComparison items={[{metric:'volatility',status:'NOT_COMPARABLE',reason:'ORIGINAL_COMPARISON_BASIS_NOT_RECORDED',reasons:['ORIGINAL_COMPARISON_BASIS_NOT_RECORDED','COST_BASIS_DIFFERS','SAMPLING_DIFFERS','END_DIFFERS'],difference:null,alignment:{end:{expected:'2027-10-01',actual:'2026-10-02',matches:false}}}]}/>);
    expect(screen.getByText(/확정 당시 비교 기준 미기록 · 비용 처리 불일치 · 산출 주기 불일치 · 종료일 불일치/)).toBeInTheDocument();
    expect(screen.getByText('2027-10-01')).toBeInTheDocument();
    expect(screen.getByText('2026-10-02')).toBeInTheDocument();
  });
});
