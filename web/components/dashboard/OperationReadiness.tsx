"use client";
import {useQuery} from "@tanstack/react-query";
import {getDecisions} from "@/lib/api/decisions";
import {get} from "@/lib/api/client";
import type {DecisionVerification} from "@/components/portfolio/DecisionVerificationPanel";
import {ValuationStatus, valuationLabel} from "@/components/portfolio/ValuationStatus";

/** The same owner-scoped decision queries as Portfolio/Review; no execution endpoint. */
export function OperationReadiness() {
  const decisions=useQuery({queryKey:["decisions"],queryFn:getDecisions,refetchInterval:60_000,refetchIntervalInBackground:false});
  const id=decisions.data?.items[0]?.decision_id;
  const evidence=useQuery({queryKey:["decision-verification",id],queryFn:()=>get<DecisionVerification>(`/api/v1/me/decisions/${encodeURIComponent(id!)}/verification`),enabled:!!id,refetchInterval:60_000,refetchIntervalInBackground:false});
  const retry=()=>{void decisions.refetch();if(id)void evidence.refetch();};
  const loading=decisions.isLoading || (!!id && evidence.isLoading);
  const failed=decisions.isError || (!!id && evidence.isError);
  const data=evidence.data;
  return <section aria-label="운용 대기 사유">
    {loading ? <p role="status">운용 상태 조회 중</p> : <>
      {failed && <p role="alert">{data ? "상태 갱신에 실패했습니다. 이전 조회 결과입니다." : "운용 상태를 불러오지 못했습니다."} <button className="btn-secondary" onClick={retry}>운용 상태 다시 조회</button></p>}
      {data ? <><h3>{valuationLabel(data.valuation_job)}</h3><ValuationStatus job={data.valuation_job}/>
        <p>{data.actual.status === "AVAILABLE" ? "선택한 판단의 동일 기간 성과는 투자 판단 검증에서 확인할 수 있습니다." : `동일 기간 계좌 성과 미확보${data.actual.reason ? ` · ${data.actual.reason}` : ""}`}</p></>
        : !failed && <p>{id ? "평가 작업 기록 미확보" : "확정 판단 기록 미확보"}</p>}
    </>}
  </section>;
}
