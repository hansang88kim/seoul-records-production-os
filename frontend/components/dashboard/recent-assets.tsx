import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CompactDataTable } from "@/components/shared/compact-data-table";
import { formatDuration } from "@/lib/utils";
import type { SongTrack } from "@/lib/types";

/** Recent assets table — most recently generated songs. */
export function RecentAssets({ songs }: { songs: SongTrack[] }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">최근 생성 곡</CardTitle>
      </CardHeader>
      <CardContent>
        <CompactDataTable<SongTrack>
          rows={songs}
          empty="아직 생성된 곡이 없습니다."
          columns={[
            { key: "title", header: "제목", render: (s) => <span className="font-medium">{s.title}</span> },
            {
              key: "duration",
              header: "길이",
              align: "right",
              render: (s) => (
                <span className="tabular-nums text-muted-foreground">
                  {formatDuration(s.duration_sec)}
                </span>
              ),
            },
          ]}
        />
      </CardContent>
    </Card>
  );
}
