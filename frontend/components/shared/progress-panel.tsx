import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { JobStatusBadge } from "@/components/shared/job-status-badge";
import type { JobStatus } from "@/lib/types";

/** A live job progress card (status + percent + eta). */
export function ProgressPanel({
  title,
  status,
  percent,
  eta,
}: {
  title: string;
  status: JobStatus;
  percent: number;
  eta?: string;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm">{title}</CardTitle>
        <JobStatusBadge status={status} />
      </CardHeader>
      <CardContent className="space-y-2">
        <Progress value={percent} />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span className="tabular-nums">{percent.toFixed(0)}%</span>
          {eta && <span>ETA {eta}</span>}
        </div>
      </CardContent>
    </Card>
  );
}
