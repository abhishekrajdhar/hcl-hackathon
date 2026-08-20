import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Pathwise — Adaptive learning paths, powered by AI",
  description:
    "Pathwise turns your goal into a personalized roadmap that adapts as you learn, with an AI coach that always explains the why.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
