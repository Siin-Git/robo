import { get } from './client';
export interface Strategy {
  id:string;label:string;status:string;currency:string;selection_rule:string;rebalance_rule:string;
  cost_basis:string;dividend_basis:string;blockers:string[];
  variants:{id:string;label:string;frequency:string;signal_execution:string}[];
}
export interface StrategyDetail extends Strategy {
  version:string;
  snapshot:{as_of?:string;rebalance_date?:string;snapshot_date?:string;signal_month?:string;data_kind?:string;members:{ticker:string;company:string;weight?:number;target_weight?:number|null;actual_weight?:number;sector?:string}[]};
  report:{start:string;end:string;frequency:string;warning?:string;source_period?:{start:string;end:string};observations:number;metrics:{cumulative_return:number;mdd:number};series:{date:string;personal:number}[]}|null;
  source_summary?:{cagr:number;mdd:number};
}
export const getStrategies=()=>get<{items:Strategy[];version:string}>('/api/v1/strategies');
export const getStrategy=(id:string,variant:string)=>get<StrategyDetail>(`/api/v1/strategies/${encodeURIComponent(id)}${variant?`?variant=${encodeURIComponent(variant)}`:''}`);
