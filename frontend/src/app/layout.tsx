import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Learning Path Dashboard",
  description: "AI-powered personalized learning path dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
