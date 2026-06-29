import Link from "next/link";
import { Music4, Image as ImageIcon, Clapperboard, Youtube, Disc3 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { ProductionReadiness } from "@/lib/types";

/** The five-stage pipeline overview cards (Song → Thumbnail → Video → YouTube → Distribution). */
export function PipelineOverview({ readiness }: { readiness: ProductionReadiness }) {
  const stages = [
    { href: "/song-lab", label: "Song Lab", icon: Music4, score: readiness.song_readiness },
    { href: "/thumbnail-studio", label: "Thumbnail", icon: ImageIcon, score: readiness.visual_readiness },
    { href: "/video-renderer", label: "Video", icon: Clapperboard, score: readiness.video_readiness },
    { href: "/youtube-package", label: "YouTube", icon: Youtube, score: readiness.youtube_package_readiness },
    { href: "/unitedmasters", label: "Distribution", icon: Disc3, score: readiness.unitedmasters_readiness },
  ];
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
      {stages.map(({ href, label, icon: Icon, score }) => (
        <Link key={href} href={href}>
          <Card className="transition-colors hover:border-primary/50">
            <CardContent className="p-4">
              <div className="mb-2 flex items-center justify-between">
                <Icon className="size-4 text-muted-foreground" />
                <Badge variant={score >= 80 ? "success" : score >= 50 ? "warning" : "secondary"}>
                  {score}%
                </Badge>
              </div>
              <div className="text-sm font-medium">{label}</div>
            </CardContent>
          </Card>
        </Link>
      ))}
    </div>
  );
}
