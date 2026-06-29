import Link from "next/link";
import {
  Music4,
  Image as ImageIcon,
  Clapperboard,
  Youtube,
  ClipboardCheck,
  ArrowRight,
} from "lucide-react";
import { PageHeader, MetricCard } from "@/components/layout/page-header";
import {
  ProgressPanel,
  WarningCallout,
  EmptyState,
} from "@/components/layout/progress-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getDashboardSnapshot } from "@/lib/api";
import { formatDuration } from "@/lib/utils";

const QUICK_ACTIONS = [
  { href: "/song-lab", label: "Generate Songs", icon: Music4 },
  { href: "/thumbnail-studio", label: "Create Thumbnail", icon: ImageIcon },
  { href: "/video-renderer", label: "Render Video", icon: Clapperboard },
  { href: "/youtube-package", label: "YouTube Package", icon: Youtube },
  { href: "/production-qa", label: "Check Production QA", icon: ClipboardCheck },
];

export default async function DashboardPage() {
  const snap = await getDashboardSnapshot();
  const qa = snap.production_qa;
  const activeRenders = snap.active_jobs.filter(
    (j) => j.status === "rendering" || j.status === "running" || j.status === "uploading"
  );

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

      {/* Metrics */}
      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard label="전체 준비도" value={`${qa.overall_readiness}%`} accent="cyan" />
        <MetricCard label="음악 준비도" value={`${qa.scores.song_readiness}%`} accent="amber" />
        <MetricCard label="영상 준비도" value={`${qa.scores.video_readiness}%`} accent="magenta" />
        <MetricCard
          label="Supervisor"
          value={snap.remote_control.supervisor.streamlit_running ? "online" : "down"}
          accent="muted"
          hint={`재시작 ${snap.remote_control.supervisor.restart_count_last_hour}/h`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Active jobs */}
        <div className="lg:col-span-2 space-y-4">
          <h2 className="text-sm font-medium text-muted-foreground">활성 작업</h2>
          {activeRenders.length ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {activeRenders.map((j) => (
                <ProgressPanel
                  key={j.id}
                  title={j.label}
                  status={j.status}
                  percent={j.progress_percent}
                  eta={j.eta}
                />
              ))}
            </div>
          ) : (
            <EmptyState message="현재 실행 중인 작업이 없습니다." />
          )}

          {/* Latest songs */}
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">최근 생성 곡</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>제목</TableHead>
                    <TableHead className="text-right">길이</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {snap.latest_songs.map((s, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">{s.title}</TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {formatDuration(s.duration_sec)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>

        {/* Next action + warnings */}
        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">다음 추천 작업</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground">{qa.next_action}</p>
            </CardContent>
          </Card>

          <div className="space-y-2">
            <h2 className="text-sm font-medium text-muted-foreground">경고</h2>
            {qa.warnings.slice(0, 4).map((w, i) => (
              <WarningCallout key={i} level={w.level} message={w.message} />
            ))}
          </div>

          <Card>
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
