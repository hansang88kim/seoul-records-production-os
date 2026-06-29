import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

/** A compact metric tile (number + label + optional hint). */
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
