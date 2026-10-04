"use client";
import {Suspense} from "react";
import {useSearchParams} from "next/navigation";
import DashboardPage from "../dashboard/page";
import {HistoricalPerformancePage} from "./HistoricalPerformance";
import {LoadingSkeleton} from "@/components/shared/ui";
export default function PerformancePage(){return <Suspense fallback={<LoadingSkeleton rows={6}/>}><Route/></Suspense>;}
function Route(){return useSearchParams().get("source")==="demo"?<><p className="ui-note" role="status">과거 가격 비교·시연 화면 · 실제 운용 성과가 아닙니다.</p><HistoricalPerformancePage/></>:<DashboardPage/>;}
