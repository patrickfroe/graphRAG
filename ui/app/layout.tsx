import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import QueryProvider from "../components/QueryProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "graphRAG UI",
  description: "Next.js 14 frontend for chat, ingest and graph views"
};

const navItems = [
  { href: "/chat", label: "Chat" },
  { href: "/ingest", label: "Ingest" },
  { href: "/graph", label: "Graph" },
  { href: "/documents", label: "Documents" }
];

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
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
          <main>
            <QueryProvider>{children}</QueryProvider>
          </main>
        </div>
      </body>
    </html>
  );
}
