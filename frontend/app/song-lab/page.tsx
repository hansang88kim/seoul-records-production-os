import { Music4, Play } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
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
import { getDashboardStatus } from "@/lib/api";
import { formatDuration } from "@/lib/utils";

export default async function SongLabPage() {
  const snap = await getDashboardStatus();
  return (
    <>
      <PageHeader
        title="Song Lab"
        description="시티팝/누디스코 곡을 생성하고 배치로 관리합니다. (쿠키·키는 마스킹됨)"
        action={
          <Button size="sm">
            <Music4 /> 곡 생성
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">생성된 곡</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>제목</TableHead>
                    <TableHead className="text-right">길이</TableHead>
                    <TableHead className="text-right">액션</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {snap.latest_songs.map((s, i) => (
                    <TableRow key={i}>
                      <TableCell className="font-medium">{s.title}</TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {formatDuration(s.duration_sec)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" aria-label="preview">
                          <Play />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">스타일 프리셋</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <div className="flex items-center justify-between">
                <span>City Pop (1980s–1990s)</span>
                <Badge>locked</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>Summer Nu-Disco House</span>
                <Badge variant="secondary">option</Badge>
              </div>
              <p className="pt-2 text-xs">
                여성 보컬 · 중저음 · BPM 110–114 · 드럼 없는 인트로 훅.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  );
}
