"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { ArrowLeft, ArrowRight, ExternalLink } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { useSetupStyles } from "../style-context";

const issues = [
  {
    type: "최근 소식", source: "NVIDIA · 기업 발표", date: "2026-09-10",
    title: "로봇이 영상 하나로 새로운 작업을 배운다면?",
    summary: "NVIDIA는 Skild AI의 S1 모델이 영상 시연을 바탕으로 새로운 작업을 수행하도록 설계됐다고 소개했습니다. 회사는 모델 학습, 시뮬레이션과 실제 로봇 적용에 사용한 기술을 설명했습니다.",
    context: "기업이 공개한 기술 소개입니다. 다양한 현장에서의 성능과 상용화 성과는 별도로 확인할 필요가 있습니다.",
    question: "기술 시연을 넘어, 기업이 로봇 도입 비용을 회수하려면 무엇이 필요할까요?",
    tags: [{ name: "로봇·자동화", category: "산업·인프라" }, { name: "인공지능", category: "기술" }],
    url: "https://blogs.nvidia.com/blog/skild-ai-s1-physical-ai/",
  },
  {
    type: "함께 읽을 배경 자료", source: "IEA · 보고서 발표", date: "2026-04-16",
    title: "AI 데이터센터의 성장, 전력망은 준비됐을까요?",
    summary: "IEA는 2025년 데이터센터의 전력 수요가 17% 증가했다고 발표했습니다. 보고서는 변압기 등 설비 공급과 전력망 연결 지연이 데이터센터 확장의 제약이 될 수 있다고 설명합니다.",
    context: "2026년 4월에 발표된 배경 자료입니다. 데이터센터 수요와 전력 설비의 관계를 이해하는 데 참고할 수 있습니다.",
    question: "전력 수요 증가가 실제 설비 발주로 이어지려면 어떤 조건이 갖춰져야 할까요?",
    tags: [{ name: "전력 인프라", category: "에너지" }, { name: "클라우드·데이터센터", category: "산업·인프라" }],
    url: "https://www.iea.org/news/data-centre-electricity-use-surged-in-2025-even-with-tightening-bottlenecks-driving-a-scramble-for-solutions",
  },
];

function IssuesInner() {
  const params=useSearchParams();
  const suffix=params.get("adjustment_choice_id") ? `&adjustment_choice_id=${encodeURIComponent(params.get("adjustment_choice_id")!)}` : "";
  const { theme: s } = useSetupStyles();
  return <AppShell headerTitle="최신 이슈" setup><div className={s.page}>
    <Link href={`/setup/portfolio?step=themes${suffix}`} className={s.back} style={{ paddingTop: 0, marginBottom: 28 }}><ArrowLeft size={16} /> 테마 선택으로 돌아가기</Link>
    <div className={s.eyebrow}>관심 분야를 찾는 읽을거리</div>
    <h1 className={s.heading}>변화를 읽고, 내 생각을 만들어보세요.</h1>
    <p className={s.intro}>산업의 소식과 질문을 함께 살펴보세요. 눈에 들어오는 분야가 있으면 테마를 둘러볼 수 있습니다.</p>
    <div className={s.issueLayout}>
      <div>{issues.map(issue => <article className={s.issue} key={issue.url}>
        <div className={s.issueMeta}><span className={s.badge}>{issue.type}</span><span>{issue.source}</span><time dateTime={issue.date}>{issue.date.replaceAll("-", ".")}</time></div>
        <h2>{issue.title}</h2><p>{issue.summary}</p><p style={{ fontSize: 13 }}>{issue.context}</p>
        <div className={s.question}><small>생각해 볼 질문</small><p>{issue.question}</p></div>
        <div className={s.issueFooter}><div className={s.tags}>{issue.tags.map(tag => <Link key={tag.name} href={`/setup/portfolio?step=themes&category=${encodeURIComponent(tag.category)}${suffix}`}>{tag.name} 둘러보기 →</Link>)}</div><a className={s.textButton} href={issue.url} target="_blank" rel="noopener noreferrer">출처 원문 <ExternalLink size={14} /></a></div>
      </article>)}</div>
      <aside className={s.issueAside}><h2>읽으면서 생각해 보세요</h2><p>01　어떤 변화가 일어나고 있나요?</p><p>02　그 변화가 실제 수요와 기업의 수익으로 이어질까요?</p><p>03　기대와 달라질 수 있는 점은 무엇인가요?</p><div className={s.impact}><p>관련 테마는 소식의 주제를 연결한 것입니다. 관심 있는 분야를 직접 선택해 보세요.</p><Link className={s.primary} href={`/setup/portfolio?step=themes${suffix}`}>테마 둘러보기 <ArrowRight size={16} /></Link></div><p style={{ fontSize: 12, marginTop: 22 }}>자료 확인일 2026.09.16<br />직접 선별한 읽을거리이며 실시간 뉴스 목록은 아닙니다.</p></aside>
    </div>
  </div></AppShell>;
}

export default function IssuesPage(){return <Suspense fallback={<p>읽을거리 조회 중</p>}><IssuesInner/></Suspense>;}
