import { ScrollArea } from "@/components/ui/scroll-area";

/** Sanitized log viewer (monospace, scrollable). Never receives secrets. */
export function LogViewer({ lines }: { lines: string[] }) {
  return (
    <ScrollArea className="h-48 rounded-md border border-border bg-card/60">
      <pre className="p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
        {lines.length ? lines.join("\n") : "로그가 없습니다."}
      </pre>
    </ScrollArea>
  );
}
