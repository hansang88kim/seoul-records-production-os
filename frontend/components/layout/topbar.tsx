"use client";

import { useState } from "react";
import { Menu, X, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { MobileNav } from "@/components/layout/mobile-nav";

export function Topbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center justify-between gap-3 border-b border-border bg-background/80 px-4 backdrop-blur md:px-6">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle navigation"
        >
          {open ? <X /> : <Menu />}
        </Button>
        <div className="md:hidden text-sm font-semibold">Seoul Records Studio</div>
      </div>

      <div className="flex items-center gap-2">
        <Badge variant="success" className="gap-1">
          <Activity className="size-3" /> Live
        </Badge>
        <span className="hidden sm:inline text-xs text-muted-foreground">127.0.0.1:8501</span>
      </div>

      {open && (
        <div className="absolute left-0 top-14 w-full border-b border-border bg-background md:hidden">
          <MobileNav onNavigate={() => setOpen(false)} />
        </div>
      )}
    </header>
  );
}
