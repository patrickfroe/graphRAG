import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: "graphRAG UI",
  description: "Next.js 14 frontend for chat, ingest and graph views"
};

const navItems = [
  { href: "/chat", label: "Chat" },
  { href: "/ingest", label: "Ingest" },
  { href: "/graph", label: "Graph" }
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de">
      <body>
        <div className="mx-auto min-h-screen max-w-5xl p-6">
          <header className="mb-8 flex items-center justify-between border-b pb-4">
            <h1 className="text-xl font-semibold">graphRAG UI</h1>
            <nav className="flex gap-2">
              {navItems.map((item) => (
                <Link key={item.href} className="rounded-md px-3 py-2 text-sm hover:bg-accent" href={item.href}>
                  {item.label}
                </Link>
              ))}
            </nav>
          </header>
          <main>{children}</main>
        </div>
      </body>
import "./globals.css";

export const metadata: Metadata = {
  title: "graphRAG UI",
  description: "Minimal graphRAG query interface"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
