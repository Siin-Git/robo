import { ParticipantPerformance } from "@/components/dashboard/ParticipantPerformance";

export default async function ParticipantPage({ params }: { params: Promise<{ participantId: string }> }) {
  const { participantId } = await params;
  return <ParticipantPerformance participantId={participantId}/>;
}
