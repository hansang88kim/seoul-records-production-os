import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { WarningCallout } from "@/components/shared/warning-callout";
import type { ProductionReadiness } from "@/lib/types";

/** Production readiness panel — overall score, per-stage bars, next action, warnings. */
export function ReadinessSummary({ readiness }: { readiness: ProductionReadiness }) {
  const bars: [string, number][] = [
    ["음악", readiness.song_readiness],
    ["비주얼", readiness.visual_readiness],
    ["영상", readiness.video_readiness],
    ["YouTube", readiness.youtube_package_readiness],
    ["업로드", readiness.upload_readiness],
    ["UnitedMasters", readiness.unitedmasters_readiness],
  ];
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">제작 준비도</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <div className="mb-1 flex justify-between text-xs">
              <span className="text-muted-foreground">전체</span>
              <span className="tabular-nums">{readiness.overall_readiness}%</span>
            </div>
            <Progress value={readiness.overall_readiness} />
          </div>
          {bars.map(([label, v]) => (
            <div key={label}>
              <div className="mb-1 flex justify-between text-xs text-muted-foreground">
                <span>{label}</span>
                <span className="tabular-nums">{v}%</span>
              </div>
              <Progress value={v} />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">다음 추천 작업</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{readiness.next_action}</p>
        </CardContent>
      </Card>

      <div className="space-y-2">
        {readiness.warnings.slice(0, 4).map((w, i) => (
          <WarningCallout key={i} level={w.level} message={w.message} />
        ))}
      </div>
    </div>
  );
}
