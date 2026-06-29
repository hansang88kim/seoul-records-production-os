import { FileDown, RefreshCw } from "lucide-react";
import { PageHeader, MetricCard } from "@/components/layout/page-header";
import { WarningCallout } from "@/components/layout/progress-panel";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { getProductionQA } from "@/lib/api";
import type { AssetStatus } from "@/lib/types";

const STATUS_VARIANT: Record<AssetStatus, "default" | "success" | "warning" | "danger" | "secondary"> = {
  Ready: "success",
  Completed: "success",
  Missing: "danger",
  Warning: "warning",
  Optional: "secondary",
  "Needs Review": "warning",
};

export default async function ProductionQAPage() {
  const qa = await getProductionQA();
  const scoreEntries: [string, number][] = [
    ["음악", qa.scores.song_readiness],
    ["비주얼", qa.scores.visual_readiness],
    ["영상", qa.scores.video_readiness],
    ["YouTube 패키지", qa.scores.youtube_package_readiness],
    ["업로드", qa.scores.upload_readiness],
    ["UnitedMasters", qa.scores.unitedmasters_readiness],
  ];

  return (
    <>
      <PageHeader
        title="Production QA"
        description="outputs 폴더를 스캔해 제작 준비 상태를 한눈에 확인합니다. (읽기 전용)"
        action={
          <>
            <Button variant="outline" size="sm">
              <RefreshCw /> 다시 스캔
            </Button>
            <Button size="sm">
              <FileDown /> 리포트
            </Button>
          </>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        <MetricCard label="전체 준비도" value={`${qa.overall_readiness}%`} accent="cyan" />
        {scoreEntries.map(([label, v]) => (
          <MetricCard key={label} label={label} value={`${v}%`} accent="muted" />
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">체크리스트</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {Object.entries(qa.groups).map(([group, items]) => (
                <div key={group}>
                  <div className="mb-2 text-xs font-medium text-muted-foreground">{group}</div>
                  <div className="space-y-1.5">
                    {items.map((it) => (
                      <div key={it.key} className="flex items-center justify-between text-sm">
                        <span>{it.label}</span>
                        <Badge variant={STATUS_VARIANT[it.status]}>{it.status}</Badge>
                      </div>
                    ))}
                  </div>
                  <Separator className="mt-3" />
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

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
            <h2 className="text-sm font-medium text-muted-foreground">경고 / 누락</h2>
            {qa.warnings.map((w, i) => (
              <WarningCallout key={i} level={w.level} message={w.message} />
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
