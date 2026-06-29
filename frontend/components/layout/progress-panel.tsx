import * as React from "react";
import { AlertTriangle, Inbox, Info, ShieldAlert } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ScrollArea } from "@/components/ui/scroll-area";
import { JobStatusBadge } from "@/components/layout/job-status-badge";
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

/** Warning / blocker / optional callout. */
export function WarningCallout({
  level,
  message,
}: {
  level: "blocker" | "warning" | "optional";
  message: string;
}) {
  const variant = level === "blocker" ? "danger" : level === "warning" ? "warning" : "default";
  const Icon = level === "blocker" ? ShieldAlert : level === "warning" ? AlertTriangle : Info;
  return (
    <Alert variant={variant}>
      <Icon />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}

/** Empty state placeholder. */
export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border py-12 text-center">
      <Inbox className="size-6 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">{message}</p>
    </div>
  );
}

/** Sanitized log viewer (monospace, scrollable). Never receives secrets. */
export function LogViewer({ lines }: { lines: string[] }) {
  return (
    <ScrollArea className="h-48 rounded-md border border-border bg-card/60">
      <pre className="p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
        {lines.length ? lines.join("\n") : "로그가 없습니다."}
      </pre>
    </ScrollArea>
  );
}
