"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { clsx } from "@/lib/cn";
import { useTheme } from "@/lib/hooks/useTheme";

const LINKS = [
  { label: "Features", href: "#features" },
  { label: "How it works", href: "#how" },
  { label: "Showcase", href: "#showcase" },
  { label: "Testimonials", href: "#testimonials" },
];

export function LandingNav() {
  const { theme, toggle } = useTheme();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={clsx(
        "fixed inset-x-0 top-0 z-50 transition-all duration-300",
        scrolled ? "border-b border-border bg-bg/70 backdrop-blur-xl" : "border-b border-transparent",
      )}
    >
      <nav className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 lg:px-6">
        <Link href="/" className="group flex items-center gap-2">
          <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-brand to-accent text-white shadow-card transition-transform group-hover:rotate-12">
            ◆
          </span>
          <span className="text-[15px] font-bold tracking-tight">Pathwise</span>
        </Link>

        <div className="hidden items-center gap-1 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="rounded-lg px-3 py-1.5 text-sm text-muted transition-colors hover:text-fg"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={toggle}
            aria-label="Toggle theme"
            className="grid h-9 w-9 place-items-center rounded-xl border border-border text-muted transition-colors hover:text-fg"
          >
            {theme === "dark" ? "☾" : "☀"}
          </button>
          <Link
            href="/dashboard"
            className="hidden rounded-xl px-3.5 py-2 text-sm font-medium text-muted transition-colors hover:text-fg sm:block"
          >
            Sign in
          </Link>
          <Link
            href="/dashboard"
            className="group relative overflow-hidden rounded-xl bg-gradient-to-r from-brand to-accent px-4 py-2 text-sm font-semibold text-white shadow-card transition-transform hover:scale-[1.03]"
          >
            <span className="relative z-10">Get started</span>
            <span className="absolute inset-0 -translate-x-full bg-white/20 transition-transform duration-500 group-hover:translate-x-full" />
          </Link>
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label="Menu"
            className="grid h-9 w-9 place-items-center rounded-xl border border-border text-muted md:hidden"
          >
            ☰
          </button>
        </div>
      </nav>

      {open && (
        <div className="border-t border-border bg-bg/95 px-4 py-2 backdrop-blur-xl md:hidden">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="block rounded-lg px-3 py-2 text-sm text-muted hover:text-fg"
            >
              {l.label}
            </a>
          ))}
        </div>
      )}
    </header>
  );
}
