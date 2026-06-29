import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

/** A small asset tile: name + status badge + optional icon/preview slot. */
export function AssetCard({
  name,
  status,
  tone = "secondary",
  icon,
}: {
  name: string;
  status: string;
  tone?: "success" | "warning" | "danger" | "secondary" | "default";
  icon?: React.ReactNode;
}) {
  return (
    <Card>
      <CardContent className="flex items-center justify-between p-3">
        <div className="flex items-center gap-2">
          {icon && <span className="text-muted-foreground">{icon}</span>}
          <span className="text-sm">{name}</span>
        </div>
        <Badge variant={tone === "default" ? "default" : tone}>{status}</Badge>
      </CardContent>
    </Card>
  );
}
