import { Youtube, Upload, Package } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const CHECKLIST = [
  { label: "final_video.mp4", ok: true },
  { label: "title / description / tags", ok: true },
  { label: "thumbnail_upload_ready", ok: true },
  { label: "privacy: private", ok: true },
];

export default function YouTubePackagePage() {
  return (
    <>
      <PageHeader
        title="YouTube Package"
        description="영상·썸네일·챕터로 수동 패키지를 만들고, OAuth로 private 업로드합니다. (OAuth 상태는 마스킹됨)"
        action={
          <>
            <Button variant="outline" size="sm">
              <Package /> 패키지 생성
            </Button>
            <Button size="sm">
              <Upload /> Private 업로드
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">메타데이터</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5 text-sm text-muted-foreground">
            <div>제목: 밤이 지나면 · Korea CityPop Playlist Vol.1</div>
            <div>카테고리: Music (10)</div>
            <div>공개 범위: private (기본)</div>
            <div>made for kids: false</div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">업로드 체크리스트</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {CHECKLIST.map((c) => (
              <div key={c.label} className="flex items-center justify-between text-sm">
                <span>{c.label}</span>
                <Badge variant={c.ok ? "success" : "danger"}>{c.ok ? "OK" : "Missing"}</Badge>
              </div>
            ))}
            <div className="flex items-center justify-between pt-1 text-sm">
              <span className="text-muted-foreground">OAuth</span>
              <Badge variant="secondary">redacted</Badge>
            </div>
            <p className="pt-1 text-xs text-muted-foreground">
              <Youtube className="mr-1 inline size-3" />
              공개 전 YouTube Studio에서 직접 확인하세요.
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
