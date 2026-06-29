import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { IS_MOCK } from "@/lib/api";

export default function SettingsPage() {
  return (
    <>
      <PageHeader
        title="Settings"
        description="콘솔 설정과 백엔드 연결 상태입니다. 시크릿 값은 표시되지 않습니다."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">백엔드 연결</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">데이터 소스</span>
              <Badge variant={IS_MOCK ? "warning" : "success"}>
                {IS_MOCK ? "Mock (alpha)" : "Live backend"}
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              NEXT_PUBLIC_API_BASE 환경변수를 설정하면 Python 백엔드(api/snapshot.py)에서
              sanitized 데이터를 가져옵니다.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">테마</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <div className="flex items-center justify-between">
              <span>기본 테마</span>
              <Badge>Dark</Badge>
            </div>
            <p className="text-xs">
              Light 모드는 선택 사항이며 v1.0.0-alpha에서는 다크 테마가 기본입니다.
            </p>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">시크릿 정책</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            이 콘솔은 OAuth 토큰, client_secret, Suno 쿠키, OpenAI/Gemini/Canva 키 등
            어떤 시크릿도 화면에 렌더링하지 않습니다. 백엔드 응답은 항상 sanitized 됩니다.
          </CardContent>
        </Card>
      </div>
    </>
  );
}
