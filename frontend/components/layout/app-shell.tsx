import * as React from "react";
import { StudioSidebar } from "@/components/layout/studio-sidebar";
import { Topbar } from "@/components/layout/topbar";

/** The overall studio console frame: sidebar + topbar + scrollable main. */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <StudioSidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto px-4 py-6 md:px-8">
          <div className="mx-auto w-full max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
