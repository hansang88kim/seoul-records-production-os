import { AlertTriangle, Info, ShieldAlert } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

/** Warning / blocker / optional callout. */
export function WarningCallout({
  level,
  message,
}: {
  level: "blocker" | "warning" | "optional";
  message: string;
}) {
  const variant =
    level === "blocker" ? "danger" : level === "warning" ? "warning" : "default";
  const Icon = level === "blocker" ? ShieldAlert : level === "warning" ? AlertTriangle : Info;
  return (
    <Alert variant={variant}>
      <Icon />
      <AlertDescription>{message}</AlertDescription>
    </Alert>
  );
}
