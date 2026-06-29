import { Clapperboard, Play, Square } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { ProgressPanel } from "@/components/layout/progress-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { JobStatusBadge } from "@/components/layout/job-status-badge";
import { getDashboardSnapshot } from "@/lib/api";

export default async function VideoRendererPage() {
  const snap = await getDashboardSnapshot();
  const active = snap.active_jobs.find((j) => j.kind === "video_render");

  return (
    <>
      <PageHeader
        title="Video Renderer"
        description="MP3 플레이리스트 + Canva 오버레이 + 비주얼라이저로 롱폼 영상을 렌더링합니다."
        action={
          <>
            <Button variant="outline" size="sm">
              <Play /> 30초 Preview
            </Button>
            <Button size="sm">
              <Clapperboard /> Full Render
            </Button>
          </>
        }
      />

      {active && (
        <div className="mb-6 max-w-md">
          <ProgressPanel
            title={active.label}
            status={active.status}
            percent={active.progress_percent}
            eta={active.eta}
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">설정</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5 text-sm text-muted-foreground">
            <div>길이: 60분 (repeat-until-target)</div>
            <div>비주얼라이저: citypop glow</div>
            <div>오버레이: CTA · Now Playing · Frame</div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">렌더 작업 이력</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>작업</TableHead>
                  <TableHead>상태</TableHead>
                  <TableHead className="text-right">진행률</TableHead>
                  <TableHead className="text-right">액션</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {snap.latest_renders.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-mono text-xs">{r.id}</TableCell>
                    <TableCell>
                      <JobStatusBadge status={r.status} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.progress_percent.toFixed(0)}%
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" aria-label="cancel">
                        <Square />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
