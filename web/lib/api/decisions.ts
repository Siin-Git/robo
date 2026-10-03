import { get, post } from './client';
import type { Report } from '@/app/(app)/dashboard/performance-data';
export interface Decision {
  decision_id:string; version:number; account_id:string; target_id:string; previous_decision_id:string|null;
  confirmed_at:string; target_effective_date:string; weights:Record<string,number>; reason:string|null;
  expectations:Record<string,{value:number|null;unit:string;horizon:string;basis:string;sampling:string;unavailable_reason:string|null}>;
  provenance:{frontier_id:string;risk_model_version:string;price_data_as_of:string|null;artifact_sha256:Record<string,string>};
}
export interface Choice {choice_id:string;decision_id:string;target_id:string;action:'KEEP'|'ADJUST';reason:string;selected_at:string;effect:{pending_orders:string;target_changed:boolean}}
export interface Review {
  decision:Decision;first_execution_date:string|null;valuation_date:string|null;observation_start:string|null;observation_end:string|null;
  actual:Report;review_only:boolean;review_reasons:string[];
  comparisons:{metric:string;difference:number|null;reason:string;status:string}[];
  weight_changes:{asset_id:string;confirmed_weight:number;current_weight:number|null;difference:number|null;unit:string}[];
  horizons:{months:number;due_date:string;status:string;cumulative_return:number|null}[];
}
export const getDecisions=()=>get<{items:Decision[];legacy_status:string|null}>('/api/v1/me/decisions');
export const getChoices=()=>get<{items:Choice[]}>('/api/v1/me/portfolio/choices');
export const getReview=(id:string)=>get<Review>(`/api/v1/me/decisions/${id}/review`);
export const saveChoice=(body:{decision_id:string;target_id:string;action:'KEEP'|'ADJUST';reason:string;request_key:string})=>post<Choice>('/api/v1/me/portfolio/choices',body);
