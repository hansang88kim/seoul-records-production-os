import { Image as ImageIcon, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const OUTPUTS = [
  { label: "YouTube Thumbnail 16:9", status: "Ready" },
  { label: "Video Playback Background 16:9", status: "Missing" },
  { label: "Streaming Cover 1:1", status: "Optional" },
];

export default function ThumbnailStudioPage() {
  return (
    <>
      <PageHeader
        title="Thumbnail Studio"
        description="프롬프트로 후보 이미지를 만들고 Canva 브랜딩 후 3종 에셋을 분리 출력합니다."
        action={
          <Button size="sm">
            <Sparkles /> 프롬프트 생성
          </Button>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">프롬프트 입력</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <div>국가: Korea</div>
            <div>무드: night / neon</div>
            <div>스타일: 1990s 2D cel anime + citypop</div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">후보 갤러리</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              {[0, 1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="flex aspect-video items-center justify-center rounded-md border border-dashed border-border text-muted-foreground"
                >
                  <ImageIcon className="size-5" />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">출력 에셋 (3종 분리)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {OUTPUTS.map((o) => (
              <div key={o.label} className="flex items-center justify-between text-sm">
                <span>{o.label}</span>
                <Badge
                  variant={
                    o.status === "Ready" ? "success" : o.status === "Missing" ? "danger" : "secondary"
                  }
                >
                  {o.status}
                </Badge>
              </div>
            ))}
            <p className="pt-2 text-xs text-muted-foreground">
              커버에는 곡 제목·웨이브폼·CTA가 들어가지 않습니다.
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
