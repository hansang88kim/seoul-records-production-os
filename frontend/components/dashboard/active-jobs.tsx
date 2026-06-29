import { ProgressPanel } from "@/components/shared/progress-panel";
import { EmptyState } from "@/components/shared/empty-state";
import type { JobStatus } from "@/lib/types";

export interface ActiveJobItem {
  id: string;
  label: string;
  status: JobStatus;
  progress_percent: number;
  eta?: string;
}

/** Active jobs panel — shows a progress card per running job. */
export function ActiveJobs({ jobs }: { jobs: ActiveJobItem[] }) {
  const running = jobs.filter(
    (j) => j.status === "rendering" || j.status === "running" || j.status === "uploading"
  );
  if (!running.length) {
    return <EmptyState message="현재 실행 중인 작업이 없습니다." />;
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {running.map((j) => (
        <ProgressPanel
          key={j.id}
          title={j.label}
          status={j.status}
          percent={j.progress_percent}
          eta={j.eta}
        />
      ))}
    </div>
  );
}
