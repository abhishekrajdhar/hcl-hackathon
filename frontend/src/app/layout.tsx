import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";

// Body: Inter for dense readouts and UI copy.
const body = Inter({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

// Display: Space Grotesk — the slightly technical, wide-aperture face that
// makes headings read as instrumentation rather than marketing.
const heading = Space_Grotesk({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-heading",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Pathwise — Adaptive learning paths, powered by AI",
  description:
    "Pathwise turns your goal into a personalized roadmap that adapts as you learn, with an AI coach that always explains the why.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // One palette: the world is always night.
  return (
    <html lang="en" className={`${body.variable} ${heading.variable}`}>
      <body>{children}</body>
    </html>
  );
}
