import { ParticipantPerformance } from "@/components/dashboard/ParticipantPerformance";
import { LedgerComparison } from "@/components/performance/LedgerComparison";

export default async function ParticipantPage({ params, searchParams }: { params: Promise<{ participantId: string }>; searchParams:Promise<{source?:string}> }) {
  const { participantId } = await params;
  return (await searchParams).source==="demo" ? <ParticipantPerformance participantId={participantId}/> : <LedgerComparison participantId={participantId}/>;
}
