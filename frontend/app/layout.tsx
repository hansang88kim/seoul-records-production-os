import type { Metadata } from "next";
import "./globals.css";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: "Seoul Records Studio OS",
  description: "AI Music Production OS — dark studio console",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // Dark theme is the default (class on <html>). Fonts come from the system
  // stack defined in globals.css — no external Google Fonts dependency, so
  // `next build` works fully offline.
  return (
    <html lang="ko" className="dark">
      <body className="font-sans antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
