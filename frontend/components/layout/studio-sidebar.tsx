"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Music4,
  Image as ImageIcon,
  Clapperboard,
  Youtube,
  ClipboardCheck,
  Disc3,
  Radio,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/song-lab", label: "Song Lab", icon: Music4 },
  { href: "/thumbnail-studio", label: "Thumbnail Studio", icon: ImageIcon },
  { href: "/video-renderer", label: "Video Renderer", icon: Clapperboard },
  { href: "/youtube-package", label: "YouTube Package", icon: Youtube },
  { href: "/production-qa", label: "Production QA", icon: ClipboardCheck },
  { href: "/unitedmasters", label: "UnitedMasters", icon: Disc3 },
  { href: "/remote-control", label: "Remote Control", icon: Radio },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function StudioSidebar() {
  const pathname = usePathname();
  return (
    <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar">
      <div className="flex h-14 items-center gap-2 px-5 border-b border-sidebar-border">
        <div className="size-7 rounded-md bg-gradient-to-br from-accent-cyan to-accent-magenta" />
        <div className="leading-tight">
          <div className="text-sm font-semibold text-sidebar-foreground">Seoul Records</div>
          <div className="text-[10px] text-muted-foreground">Studio OS · v1.0.0-alpha</div>
        </div>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname === href;
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                  : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground"
              )}
            >
              <Icon className="size-4" />
              {label}
            </Link>
          );
        })}
      </nav>
      <div className="p-3 text-[10px] text-muted-foreground border-t border-sidebar-border">
        Local desktop console · dark theme
      </div>
    </aside>
  );
}
