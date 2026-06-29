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

/** Slide-down mobile navigation drawer (rendered by the Topbar on small screens). */
export function MobileNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col p-2">
      {NAV.map(({ href, label, icon: Icon }) => (
        <Link
          key={href}
          href={href}
          onClick={onNavigate}
          className={cn(
            "flex items-center gap-3 rounded-md px-3 py-2 text-sm",
            pathname === href
              ? "bg-accent text-accent-foreground"
              : "text-muted-foreground hover:bg-accent/60"
          )}
        >
          <Icon className="size-4" />
          {label}
        </Link>
      ))}
    </nav>
  );
}
