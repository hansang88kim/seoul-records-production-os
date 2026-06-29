import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type Tone = "success" | "warning" | "danger" | "secondary" | "default";

/** A labeled status card with a badge and optional body. */
export function StatusCard({
  title,
  status,
  tone = "default",
  children,
}: {
  title: string;
  status: string;
  tone?: Tone;
  children?: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm">{title}</CardTitle>
        <Badge variant={tone === "default" ? "default" : tone}>{status}</Badge>
      </CardHeader>
      {children && <CardContent className="text-sm text-muted-foreground">{children}</CardContent>}
    </Card>
  );
}
