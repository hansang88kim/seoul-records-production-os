import { RotateCw } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { MetricCard } from "@/components/shared/metric-card";
import { LogViewer } from "@/components/shared/log-viewer";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getDashboardStatus } from "@/lib/api";

export default async function RemoteControlPage() {
  const snap = await getDashboardStatus();
  const rc = snap.remote_control;

  return (
    <>
      <PageHeader
        title="Remote Control"
        description="Supervisor와 Telegram 봇 상태를 확인합니다. 토큰·시크릿은 표시되지 않습니다."
        action={
          <Button variant="outline" size="sm">
            <RotateCw /> 새로고침
          </Button>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          label="Supervisor"
          value={rc.supervisor.status}
          accent="cyan"
          hint={`재시작 ${rc.supervisor.restart_count_last_hour}/h`}
        />
        <MetricCard
          label="Streamlit"
          value={rc.supervisor.streamlit_running ? "running" : "down"}
          accent="muted"
          hint={`HTTP ${rc.supervisor.streamlit_http_status ?? "n/a"}`}
        />
        <MetricCard label="허용 chat_id" value={rc.allowed_chat_id_count} accent="amber" />
        <MetricCard
          label="Tailscale"
          value={rc.tailscale_status ?? "n/a"}
          accent="muted"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Telegram 봇</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">상태</span>
              <Badge variant={rc.telegram_enabled ? "success" : "secondary"}>
                {rc.telegram_enabled ? "활성화" : "비활성화"}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">python-telegram-bot</span>
              <span>{rc.telegram_package_installed ? "설치됨" : "미설치"}</span>
            </div>
            <p className="pt-2 text-xs text-muted-foreground">
              TELEGRAM_BOT_TOKEN + TELEGRAM_ALLOWED_CHAT_IDS 환경변수로 활성화합니다.
              허용된 chat_id만 명령할 수 있고, /shell 등 임의 명령은 차단됩니다.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">최근 명령 (sanitized)</CardTitle>
          </CardHeader>
          <CardContent>
            <LogViewer
              lines={[
                "[info] /status — allowed",
                "[info] /jobs — allowed",
                "[info] unknown chat_id rejected",
              ]}
            />
          </CardContent>
        </Card>
      </div>
    </>
  );
}
