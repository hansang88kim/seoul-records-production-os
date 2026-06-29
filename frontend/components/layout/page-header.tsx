import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** Page title + description + optional primary action. */
export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {action && <div className="flex shrink-0 gap-2">{action}</div>}
    </div>
  );
}

/** A compact metric tile (number + label). */
export function MetricCard({
  label,
  value,
  accent = "cyan",
  hint,
}: {
  label: string;
  value: string | number;
  accent?: "cyan" | "magenta" | "amber" | "muted";
  hint?: string;
}) {
  const accentClass = {
    cyan: "text-accent-cyan",
    magenta: "text-accent-magenta",
    amber: "text-accent-amber",
    muted: "text-foreground",
  }[accent];
  return (
    <Card>
      <CardContent className="p-4">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className={cn("mt-1 text-2xl font-semibold tabular-nums", accentClass)}>
          {value}
        </div>
        {hint && <div className="mt-1 text-[11px] text-muted-foreground">{hint}</div>}
      </CardContent>
    </Card>
  );
}
