import { ASSET_META } from "../setup/portfolio/asset-meta";
import { THEME_INFO } from "../setup/portfolio/theme-content";
import { ASSET_COLORS } from "../setup/portfolio/FrontierChart";

export const PERIODS = [{key:"1M",label:"1개월"},{key:"3M",label:"3개월"},{key:"6M",label:"6개월"},{key:"1Y",label:"1년"},{key:"ALL",label:"전체"}] as const;
export type Period = typeof PERIODS[number]["key"];
export type Asset = {asset_id:string;group:string;contribution:number;average_weight:number|null;price_return:number|null};
export interface DecisionSummary {decision_id:string;version:number;target_effective_date:string}
export interface DecisionContext {
  as_of:string;selection_basis:"KST_EFFECTIVE_DATE";status:"ACTIVE"|"AWAITING_INITIAL_EFFECTIVE_DATE"|"LEGACY_UNRECORDED";
  active_decision:DecisionSummary|null;pending_decision:DecisionSummary|null;previous_decision:DecisionSummary|null;
  report_decision_id:string|null;window_start:string|null;window_end_exclusive:string|null;
}
export interface Report {
  valuation?:{date:string;nav_krw:number;cash_krw:number|null;index100:number}|null;
  anchor?:{date:string;nav_krw:number;index100:number}|null;
  latest_recorded_date?:string|null;latest_recorded_status?:string|null;
  comparison_window?:{start:string|null;end:string|null;dates:string[];status:string;reason:string|null};
  decision_context?:DecisionContext;
  data_kind?: "TEST_FIXTURE" | "FORWARD_SIMULATION";
  status:string;period:string;start:string|null;end:string|null;since:string|null;observations:number;benchmark_name:string;
  metrics:{cumulative_return:number|null;benchmark_return:number|null;difference_pp:number|null;mdd:number|null;volatility:number|null;tracking_error:number|null;information_ratio:number|null};
  series:{date:string;personal:number;benchmark:number|null;drawdown:number}[];
  attribution:{date:string;values:Record<string,number>;total:number}[];
  assets:Asset[];
  comparators?:{key:string;label:string;status:string;return:number|null;reason:string|null;source?:string;decision_id?:string|null;start?:string|null;end?:string|null}[];
  quality:{unresolved_intervals:number;stale_observations:number;missing_nav_dates:number;benchmark_complete:boolean};
}
export const GROUPS:Record<string,{name:string;color:string}> = {
  equity:{name:"일반 주식",color:"#3b72e8"},bonds:{name:"채권",color:"#819ba5"},
  alternatives:{name:"대체자산",color:"#b69a6b"},themes:{name:"선택 테마",color:"#8b62c9"},
  cash:{name:"현금",color:"#bac6d4"},costs:{name:"거래비용",color:"#b57575"},unexplained:{name:"미설명 차이",color:"#8d8b9a"}
};
export function assetName(id:string) {
  const raw=id.replace(/^theme:/,"");
  return GROUPS[id]?.name ?? ASSET_META[raw]?.name ?? THEME_INFO[raw]?.name ?? raw;
}
export function assetColor(id:string) {
  const raw=id.replace(/^theme:/,"");
  return GROUPS[id]?.color ?? ASSET_COLORS[raw] ?? ({semiconductor:"#7654c8",power_grid:"#ad7bd6",ai:"#9971ce"} as Record<string,string>)[raw] ?? "#9674bb";
}
export function contributionView(report:Report,mode:"groups"|"assets") {
  const metadata = new Map<string,{id:string;name:string;color:string;value:number}>();
  for(const asset of report.assets) {
    const id=mode==="groups"?asset.group:asset.asset_id;
    if(!metadata.has(id)) metadata.set(id,{id,name:assetName(id),color:assetColor(id),value:0});
    metadata.get(id)!.value+=asset.contribution;
  }
  const series=Array.from(metadata.values()).filter(item=>report.attribution.some(p=>Math.abs(report.assets.filter(a=>(mode==="groups"?a.group:a.asset_id)===item.id).reduce((sum,a)=>sum+(p.values[a.asset_id]??0),0))>1e-12));
  const points=report.attribution.map(p=>{
    const values:Record<string,string|number>={date:p.date,total:p.total*100};
    for(const item of series) values[item.id]=report.assets.filter(a=>(mode==="groups"?a.group:a.asset_id)===item.id).reduce((sum,a)=>sum+(p.values[a.asset_id]??0),0)*100;
    return values;
  });
  return {series,points,ranking:[...series].sort((a,b)=>b.value-a.value)};
}

// Explicit, deterministic display examples. Never persisted or mixed with API data.
export function exampleReport(period:Period):Report {
  const assets:Asset[]=[
    {asset_id:"us_equity",group:"equity",average_weight:.3,contribution:0,price_return:null},
    {asset_id:"developed_ex_us",group:"equity",average_weight:.15,contribution:0,price_return:null},
    {asset_id:"us_treasury",group:"bonds",average_weight:.3,contribution:0,price_return:null},
    {asset_id:"gold",group:"alternatives",average_weight:.1,contribution:0,price_return:null},
    {asset_id:"theme:semiconductor",group:"themes",average_weight:.075,contribution:0,price_return:null},
    {asset_id:"theme:power_grid",group:"themes",average_weight:.075,contribution:0,price_return:null},
    {asset_id:"costs",group:"costs",average_weight:null,contribution:0,price_return:null},
    {asset_id:"unexplained",group:"unexplained",average_weight:null,contribution:0,price_return:null}
  ];
  const full:Report["series"]=[],attr:Report["attribution"]=[];
  const totals:Record<string,number>=Object.fromEntries(assets.map(a=>[a.asset_id,0]));
  let wealth=1,bm=1;
  let i=0;
  for(let day=new Date("2026-04-01T00:00:00Z");day<=new Date("2026-09-11T00:00:00Z");day.setUTCDate(day.getUTCDate()+1)) {
    if([0,6].includes(day.getUTCDay()))continue;
    const d=day.toISOString().slice(0,10);
    if(i>0) {
      const contributions=[
        .00038+.0014*Math.sin(i*.24), .00012+.00065*Math.sin(i*.19+1),
        .00013+.00032*Math.cos(i*.22), .00011+.00045*Math.sin(i*.12+2),
        .00028+.0008*Math.sin(i*.27), -.000055+.00033*Math.cos(i*.2),
        i%22===0?-.00012:0,0
      ];
      contributions.forEach((value,j)=>{totals[assets[j].asset_id]+=wealth*value;});
      wealth*=1+contributions.reduce((sum,x)=>sum+x,0);
      bm*=1+.00067+.0017*Math.sin(i*.23+.3);
    }
    full.push({date:d,personal:wealth-1,benchmark:bm-1,drawdown:0});
    attr.push({date:d,values:{...totals},total:wealth-1});i++;
  }
  const cutoff=new Date(full.at(-1)!.date+"T00:00:00Z");
  const months=({ "1M":1,"3M":3,"6M":6,"1Y":12,ALL:0 } as const)[period];
  if(months)cutoff.setUTCMonth(cutoff.getUTCMonth()-months);
  const start=months?full.findIndex(p=>p.date>=cutoff.toISOString().slice(0,10)):0;
  const anchor=full[Math.max(0,start)],a0=attr[Math.max(0,start)].values;
  let peak=1;
  const series=full.slice(Math.max(0,start)).map(p=>{
    const personal=(1+p.personal)/(1+anchor.personal)-1;
    peak=Math.max(peak,1+personal);
    return {...p,personal,benchmark:(1+p.benchmark!)/(1+anchor.benchmark!)-1,drawdown:(1+personal)/peak-1};
  });
  const attribution=attr.slice(Math.max(0,start)).map((p,j)=>({date:p.date,total:series[j].personal,values:Object.fromEntries(assets.map(a=>[a.asset_id,(p.values[a.asset_id]-a0[a.asset_id])/(1+anchor.personal)]))}));
  assets.forEach(a=>{a.contribution=attribution.at(-1)!.values[a.asset_id];});
  const returns=series.slice(1).map((p,j)=>(1+p.personal)/(1+series[j].personal)-1);
  const active=series.slice(1).map((p,j)=>returns[j]-((1+p.benchmark!)/(1+series[j].benchmark!)-1));
  const sd=(xs:number[])=>{const mean=xs.reduce((s,x)=>s+x,0)/xs.length;return Math.sqrt(xs.reduce((s,x)=>s+(x-mean)**2,0)/(xs.length-1));};
  const te=sd(active)*Math.sqrt(252),enough=returns.length>=30;
  const last=series.at(-1)!;
  return {status:enough?"OK":"SHORT_HISTORY",period,start:anchor.date,end:last.date,since:full[0].date,observations:series.length,benchmark_name:"시스템 기준 CORE",
    series,attribution,assets,quality:{unresolved_intervals:0,stale_observations:0,missing_nav_dates:0,benchmark_complete:true},
    metrics:{cumulative_return:last.personal,benchmark_return:last.benchmark,difference_pp:last.personal-last.benchmark!,mdd:Math.min(...series.map(p=>p.drawdown)),volatility:enough?sd(returns)*Math.sqrt(252):null,tracking_error:enough?te:null,information_ratio:enough&&te>0?active.reduce((s,x)=>s+x,0)/active.length*252/te:null}};
}
