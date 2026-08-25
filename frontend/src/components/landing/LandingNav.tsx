"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { clsx } from "@/lib/cn";

const LINKS = [
  { label: "Engine", href: "#engine" },
  { label: "Pipeline", href: "#pipeline" },
  { label: "Interface", href: "#showcase" },
];

/** Thin instrument bar. Transparent over the world until the page scrolls. */
export function LandingNav() {
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
        "fixed inset-x-0 top-0 z-50 h-14 transition-colors duration-300",
        scrolled
          ? "border-b border-line bg-[color-mix(in_srgb,var(--void)_82%,transparent)] backdrop-blur-xl"
          : "border-b border-transparent",
      )}
    >
      <nav className="mx-auto flex h-full max-w-[1400px] items-center justify-between px-6 lg:px-12">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="relative grid h-5 w-5 place-items-center">
            <span className="absolute inset-0 rounded-full border border-cyan/60" />
            <span className="h-1.5 w-1.5 rounded-full bg-cyan shadow-glow" />
          </span>
          <span className="display text-[13px] font-semibold tracking-tight">PATHWISE</span>
          <span className="label-meta ml-1 hidden text-text-3 sm:inline">v0.1</span>
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="label-meta transition-colors hover:text-cyan"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="label-meta hidden transition-colors hover:text-cyan sm:inline"
          >
            Sign in
          </Link>
          <Link
            href="/dashboard"
            className="border border-cyan/50 bg-cyan/10 px-4 py-2 text-[11px] font-medium uppercase tracking-[0.12em] text-cyan transition-all hover:bg-cyan/20 hover:shadow-glow"
          >
            Launch
          </Link>
          <button
            onClick={() => setOpen((o) => !o)}
            aria-label="Menu"
            className="text-text-2 md:hidden"
          >
            {open ? "✕" : "☰"}
          </button>
        </div>
      </nav>

      {open && (
        <div className="border-b border-line bg-void/95 px-6 py-4 backdrop-blur-xl md:hidden">
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="label-meta block py-2.5 hover:text-cyan"
            >
              {l.label}
            </a>
          ))}
        </div>
      )}
    </header>
  );
}
