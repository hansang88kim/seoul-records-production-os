import { Disc3, FileDown, ExternalLink } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { WarningCallout } from "@/components/layout/progress-panel";
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
import { mockTracks } from "@/lib/mock-data";
import { formatDuration } from "@/lib/utils";

export default function UnitedMastersPage() {
  const allReady = mockTracks.every((t) => t.distribution_ready);
  return (
    <>
      <PageHeader
        title="UnitedMasters"
        description="Video Renderer 플레이리스트 순서로 배포 패키지를 만듭니다. MP3는 소스/초안, WAV·FLAC가 있어야 배포 준비 완료."
        action={
          <>
            <Button size="sm">
              <Disc3 /> 패키지 생성
            </Button>
            <Button variant="outline" size="sm">
              <FileDown /> ZIP 내보내기
            </Button>
          </>
        }
      />

      {!allReady && (
        <div className="mb-4">
          <WarningCallout
            level="warning"
            message="MP3-only 패키지입니다 — 실제 배포에는 WAV/FLAC 마스터가 필요합니다."
          />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">트랙 (YouTube 렌더 순서)</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>#</TableHead>
                    <TableHead>제목</TableHead>
                    <TableHead className="text-right">길이</TableHead>
                    <TableHead className="text-right">배포 상태</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {mockTracks.map((t) => (
                    <TableRow key={t.track_no}>
                      <TableCell className="tabular-nums text-muted-foreground">{t.track_no}</TableCell>
                      <TableCell className="font-medium">{t.title}</TableCell>
                      <TableCell className="text-right tabular-nums text-muted-foreground">
                        {formatDuration(t.duration_sec)}
                      </TableCell>
                      <TableCell className="text-right">
                        <Badge variant={t.distribution_ready ? "success" : "warning"}>
                          {t.distribution_ready ? "Distribution Ready" : "MP3-only"}
                        </Badge>
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
              <CardTitle className="text-sm">릴리스 메타데이터</CardTitle>
            </CardHeader>
            <CardContent className="space-y-1 text-sm text-muted-foreground">
              <div>아티스트: Seoul Records</div>
              <div>제목: Korea CityPop Playlist Vol.1</div>
              <div>장르: City Pop · 언어: Korean</div>
              <div>레이블: Seoul Records</div>
            </CardContent>
          </Card>
          <Button variant="outline" className="w-full" asChild>
            <a href="https://unitedmasters.com/" target="_blank" rel="noreferrer">
              <ExternalLink /> UnitedMasters 열기
            </a>
          </Button>
        </div>
      </div>
    </>
  );
}
