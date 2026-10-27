import {render,screen,fireEvent,cleanup} from "@testing-library/react";
import {afterEach,beforeEach,it,expect,vi} from "vitest";
import {OperationReadiness} from "../dashboard/OperationReadiness";
import {valuationLabel} from "../portfolio/ValuationStatus";
const state=vi.hoisted(()=>({decisions:{} as any,evidence:{} as any}));
vi.mock("@tanstack/react-query",()=>({useQuery:({queryKey}:any)=>queryKey[0]==="decisions"?state.decisions:state.evidence}));
afterEach(cleanup);
beforeEach(()=>{
 state.decisions={data:{items:[{decision_id:"test-decision"}]},isLoading:false,isError:false,refetch:vi.fn()};
 state.evidence={data:{valuation_job:{status:"success",state:"START_WAIT",reason_code:"START_NOT_SCHEDULED",valuation_completed:false,scheduled_for:"2026-10-23",ready:15,required:15,valuated:0},actual:{status:"UNAVAILABLE",reason:"동일 날짜의 정상 NAV가 필요합니다."}},isLoading:false,isError:false,refetch:vi.fn()};
});
it('uses the server reason, readiness and date without interpreting success as NAV',()=>{
 render(<OperationReadiness/>);
 expect(screen.getByRole('heading',{name:'공동 운용 시작일 미지정'})).toBeVisible();
 expect(screen.getByText(/준비 인원: 15\/15명/)).toBeVisible();
 expect(screen.getByText(/작업 예정일: 2026.10.23/)).toBeVisible();
 expect(screen.queryByText('정상 NAV 저장 완료')).not.toBeInTheDocument();
 expect(screen.getByText(/화면 갱신으로 운용 작업이 실행되지는 않습니다/)).toBeVisible();
});
it('does not infer an unspecified start from the generic START_WAIT state',()=>{
 delete state.evidence.data.valuation_job.reason_code;
 render(<OperationReadiness/>);
 expect(screen.queryByRole('heading',{name:'공동 운용 시작일 미지정'})).not.toBeInTheDocument();
 expect(screen.getByRole('heading',{name:'공동 운용 시작 대기'})).toBeVisible();
});
it('keeps previous evidence on refresh failure and retries existing queries',()=>{
 state.evidence.isError=true;render(<OperationReadiness/>);
 expect(screen.getByRole('alert')).toHaveTextContent('이전 조회 결과');
 expect(screen.getByRole('heading',{name:'공동 운용 시작일 미지정'})).toBeVisible();
 fireEvent.click(screen.getByRole('button',{name:'운용 상태 다시 조회'}));
 expect(state.evidence.refetch).toHaveBeenCalled();
});
it('shows loading and initial error without fabricated readiness',()=>{
 state.evidence.data=undefined;state.evidence.isLoading=true;
 const view=render(<OperationReadiness/>);expect(screen.getByRole('status')).toHaveTextContent('조회 중');
 state.evidence.isLoading=false;state.evidence.isError=true;view.rerender(<OperationReadiness/>);
 expect(screen.getByRole('alert')).toHaveTextContent('불러오지 못했습니다');
 expect(screen.queryByText(/15명/)).not.toBeInTheDocument();
});
it.each([
 ['PARTICIPANTS_NOT_READY','참가자 준비 부족'],['PRICE_WAIT','가격 확보 대기 · 평가 미완료'],
 ['PARTIAL','일부 평가 미완료'],['EVALUATION_FAILED','평가 작업 실패'],['NO_NAV','저장된 NAV 없음'],
])('distinguishes %s even when process status is success',(state,label)=>{
 expect(valuationLabel({status:'success',state,scheduled_for:'2026-10-23',completed_at:null,valuation_completed:false})).toBe(label);
});
it('requires both NAV_COMPLETE and valuation_completed',()=>{
 const job={status:'success' as const,state:'NAV_COMPLETE',scheduled_for:'2026-10-23',completed_at:null};
 expect(valuationLabel(job)).toBe('정상 NAV 저장 확인 미완료');
 expect(valuationLabel({...job,valuation_completed:true})).toBe('정상 NAV 저장 완료');
 expect(valuationLabel({...job,state:undefined})).toContain('평가 완료 여부 미확인');
});

it('separates scheduled date, valuation date and persisted normal/stale counts',()=>{
 Object.assign(state.evidence.data.valuation_job,{state:'PRICE_WAIT',scheduled_for:'2026-10-27',valuation_date:'2026-10-26',valuated:30,normal_nav_accounts:0,stale_nav_accounts:30,expected_nav_accounts:30});
 render(<OperationReadiness/>);
 expect(screen.getByText(/작업 예정일: 2026.10.27/)).toBeVisible();
 expect(screen.getByText(/평가 대상일: 2026.10.26/)).toHaveTextContent('정상 NAV: 0개 계좌 · 가격 지연 NAV: 30개 계좌');
 expect(screen.queryByText(/NAV 저장: 30/)).not.toBeInTheDocument();
 expect(screen.queryByText('정상 NAV 저장 완료')).not.toBeInTheDocument();
});
it('keeps legacy missing counts unknown instead of using valuated or zero',()=>{
 state.evidence.data.valuation_job.valuated=30;
 render(<OperationReadiness/>);
 expect(screen.getByText(/평가 대상일: 미확보/)).toHaveTextContent('정상 NAV: 미확보 · 가격 지연 NAV: 미확보');
 expect(screen.queryByText(/30개 계좌/)).not.toBeInTheDocument();
});
