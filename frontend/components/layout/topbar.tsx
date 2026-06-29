"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { Menu, X, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const MOBILE_NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/production-qa", label: "Production QA" },
  { href: "/video-renderer", label: "Video Renderer" },
  { href: "/youtube-package", label: "YouTube" },
  { href: "/remote-control", label: "Remote" },
];

export function Topbar() {
  const pathname = usePathname();
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
        <span className="hidden sm:inline text-xs text-muted-foreground">
          127.0.0.1:8501
        </span>
      </div>

      {/* Mobile drawer */}
      {open && (
        <div className="absolute left-0 top-14 w-full border-b border-border bg-background md:hidden">
          <nav className="flex flex-col p-2">
            {MOBILE_NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "rounded-md px-3 py-2 text-sm",
                  pathname === n.href
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/60"
                )}
              >
                {n.label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}
