import type { Metadata } from "next";
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
