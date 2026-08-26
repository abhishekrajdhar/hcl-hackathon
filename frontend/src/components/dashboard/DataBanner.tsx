"use client";

// Two states that must never be mistaken for the learner's own universe:
// a demo they opted into, and a load that failed. Both were previously
// signalled only by a small chip in the top strip, which scrolls away — so a
// backend learner could scroll to the roadmap, see "Become a Machine Learning
// Engineer", and reasonably conclude the product was broken.

import Link from "next/link";
import { IconArrow, IconSpark } from "@/components/ui/icons";

export function DemoBanner() {
  return (
    <div className="hud hud-bracket flex flex-wrap items-center gap-x-4 gap-y-2 border-amber/40 px-5 py-3">
      <span className="flex items-center gap-2">
        <IconSpark className="h-3.5 w-3.5 text-amber" />
        <span className="label-meta text-amber">Demo universe</span>
      </span>
      <p className="min-w-0 flex-1 text-[12px] leading-relaxed text-text-2">
        This is a sample learner&apos;s journey, not yours — the goal, roadmap and
        progress below all belong to the demo.
      </p>
      <Link
        href="/onboarding"
        className="group flex shrink-0 items-center gap-2 border border-cyan/50 bg-cyan/10 px-4 py-2 text-[11px] font-medium tracking-[0.1em] text-cyan transition-all hover:bg-cyan/20"
      >
        BUILD MY OWN
        <IconArrow className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
      </Link>
    </div>
  );
}

export function LoadErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="hud hud-bracket flex flex-wrap items-center gap-x-4 gap-y-2 border-coral/40 px-5 py-3">
      <span className="label-meta shrink-0 text-coral">Couldn&apos;t load your data</span>
      <p className="min-w-0 flex-1 text-[12px] leading-relaxed text-text-2">
        {message} — nothing below is yours yet, so it is not being shown.
      </p>
      <button
        onClick={onRetry}
        className="shrink-0 border border-line-strong px-4 py-2 text-[11px] tracking-[0.1em] text-text-2 transition-colors hover:border-cyan/40 hover:text-cyan"
      >
        RETRY
      </button>
    </div>
  );
}
