import Link from "next/link";
import {
  Music4,
  Image as ImageIcon,
  Clapperboard,
  Youtube,
  ClipboardCheck,
  ArrowRight,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { MetricCard } from "@/components/shared/metric-card";
import { PipelineOverview } from "@/components/dashboard/pipeline-overview";
import { ActiveJobs } from "@/components/dashboard/active-jobs";
import { ReadinessSummary } from "@/components/dashboard/readiness-summary";
import { RecentAssets } from "@/components/dashboard/recent-assets";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getDashboardStatus } from "@/lib/api";

const QUICK_ACTIONS = [
  { href: "/song-lab", label: "Generate Songs", icon: Music4 },
  { href: "/thumbnail-studio", label: "Create Thumbnail", icon: ImageIcon },
  { href: "/video-renderer", label: "Render Video", icon: Clapperboard },
  { href: "/youtube-package", label: "YouTube Package", icon: Youtube },
  { href: "/production-qa", label: "Check Production QA", icon: ClipboardCheck },
];

export default async function DashboardPage() {
  const snap = await getDashboardStatus();
  const r = snap.readiness;

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="전체 제작 파이프라인 상태와 다음 작업을 한눈에 확인합니다."
        action={
          <Button asChild>
            <Link href="/production-qa">
              Production QA <ArrowRight />
            </Link>
          </Button>
        }
      />

      {/* Quick actions */}
      <div className="mb-6 flex flex-wrap gap-2">
        {QUICK_ACTIONS.map(({ href, label, icon: Icon }) => (
          <Button key={href} variant="outline" size="sm" asChild>
            <Link href={href}>
              <Icon /> {label}
            </Link>
          </Button>
        ))}
      </div>

      {/* Studio status metrics */}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="전체 준비도" value={`${r.overall_readiness}%`} accent="cyan" />
        <MetricCard label="음악 준비도" value={`${r.song_readiness}%`} accent="amber" />
        <MetricCard label="영상 준비도" value={`${r.video_readiness}%`} accent="magenta" />
        <MetricCard
          label="Supervisor"
          value={snap.remote_control.supervisor.streamlit_running ? "online" : "down"}
          accent="muted"
          hint={`재시작 ${snap.remote_control.supervisor.restart_count_last_hour}/h`}
        />
      </div>

      {/* Pipeline overview */}
      <div className="mb-6">
        <h2 className="mb-3 text-sm font-medium text-muted-foreground">파이프라인</h2>
        <PipelineOverview readiness={r} />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-sm font-medium text-muted-foreground">활성 작업</h2>
          <ActiveJobs jobs={snap.active_jobs} />
          <RecentAssets songs={snap.latest_songs} />
        </div>

        <div>
          <ReadinessSummary readiness={r} />
          <Card className="mt-4">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Remote</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-xs text-muted-foreground">
              <div className="flex items-center justify-between">
                <span>Telegram 봇</span>
                <Badge variant={snap.remote_control.telegram_enabled ? "success" : "secondary"}>
                  {snap.remote_control.telegram_enabled ? "활성화" : "비활성화"}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>python-telegram-bot</span>
                <span>{snap.remote_control.telegram_package_installed ? "설치됨" : "미설치"}</span>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
