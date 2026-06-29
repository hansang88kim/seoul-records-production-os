import { Badge } from "@/components/ui/badge";
import type { JobStatus } from "@/lib/types";

const MAP: Record<
  JobStatus,
  { label: string; variant: "default" | "success" | "warning" | "danger" | "secondary" }
> = {
  idle: { label: "idle", variant: "secondary" },
  queued: { label: "queued", variant: "secondary" },
  running: { label: "running", variant: "default" },
  rendering: { label: "rendering", variant: "default" },
  uploading: { label: "uploading", variant: "default" },
  completed: { label: "completed", variant: "success" },
  partial_success: { label: "partial", variant: "warning" },
  failed: { label: "failed", variant: "danger" },
  cancelled: { label: "cancelled", variant: "secondary" },
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const m = MAP[status] ?? MAP.idle;
  return <Badge variant={m.variant}>{m.label}</Badge>;
}
