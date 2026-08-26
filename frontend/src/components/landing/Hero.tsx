"use client";

import Link from "next/link";
import { HeroWorld } from "@/components/landing/HeroWorld";
import { IconArrow } from "@/components/ui/icons";

/** Live telemetry strip — real figures from the seeded catalogue. */
const TELEMETRY = [
  { label: "Skills mapped", value: "49" },
  { label: "Prerequisite edges", value: "76" },
  { label: "Deterministic engines", value: "9" },
  { label: "Model-invented facts", value: "0" },
];

export function Hero() {
  return (
    <section className="relative flex min-h-screen flex-col overflow-hidden">
      <Corners />

      {/* Two distinct halves: the argument on the left, the world on the
          right. The 3D used to run full-bleed behind the copy, which crowded
          the type — here each side gets its own column and neither competes. */}
      <div className="relative mx-auto grid w-full max-w-[1500px] flex-1 grid-cols-1 items-center gap-10 px-6 pb-8 pt-28 lg:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)] lg:gap-16 lg:px-12 lg:pt-24">
        {/* --- copy ------------------------------------------------------- */}
        <div className="relative z-10 max-w-xl">
          <p className="label-meta mb-6 flex items-center gap-2.5 text-cyan">
            <span className="h-1 w-1 rounded-full bg-cyan shadow-glow" />
            Adaptive learning engine
          </p>

          <h1 className="display text-[40px] font-semibold leading-[0.98] sm:text-[52px] lg:text-[64px]">
            Your knowledge
            <br />
            has a{" "}
            <span className="relative">
              <span className="text-cyan">topology</span>
              <span
                aria-hidden
                className="absolute -bottom-1 left-0 h-px w-full bg-cyan/50 shadow-glow"
              />
            </span>
            .
          </h1>

          <p className="mt-7 max-w-md text-[15px] leading-relaxed text-text-2">
            Every skill you need sits somewhere in a prerequisite graph. Pathwise
            maps that terrain, finds your position in it, and computes the route —
            then adapts it the moment your position changes.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              href="/signup"
              className="group flex items-center gap-2.5 border border-cyan/50 bg-cyan/10 px-6 py-3 text-[13px] font-medium tracking-wide text-cyan transition-all hover:bg-cyan/20 hover:shadow-glow"
            >
              ENTER THE UNIVERSE
              <IconArrow className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
            </Link>
            <Link
              href="#engine"
              className="border border-line-strong px-6 py-3 text-[13px] tracking-wide text-text-2 transition-colors hover:border-cyan/40 hover:text-cyan"
            >
              HOW IT WORKS
            </Link>
          </div>
        </div>

        {/* --- the world -------------------------------------------------- */}
        <div className="relative h-[46vh] min-h-[300px] w-full lg:h-[74vh] lg:min-h-[520px]">
          <HeroWorld />
          {/* A caption, so the visual is understood as live product rather
              than decoration. */}
          <p className="label-meta pointer-events-none absolute bottom-1 right-0 hidden lg:block">
            live engine · demo learner
          </p>
        </div>
      </div>

      {/* Telemetry along the floor of the viewport. */}
      <div className="relative z-10 mx-auto w-full max-w-[1500px] px-6 pb-8 lg:px-12">
        <div className="grid grid-cols-2 gap-px border-t border-line bg-line md:grid-cols-4">
          {TELEMETRY.map((t) => (
            <div key={t.label} className="bg-void px-4 py-4">
              <div className="readout display text-[22px] font-semibold text-text">{t.value}</div>
              <div className="label-meta mt-1.5">{t.label}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/** Viewport corner brackets — the cheapest, strongest "instrument" cue. */
function Corners() {
  const base = "pointer-events-none absolute h-6 w-6 border-cyan/30";
  return (
    <div aria-hidden className="absolute inset-6 z-10 hidden lg:block">
      <span className={`${base} left-0 top-0 border-l border-t`} />
      <span className={`${base} right-0 top-0 border-r border-t`} />
      <span className={`${base} bottom-0 left-0 border-b border-l`} />
      <span className={`${base} bottom-0 right-0 border-b border-r`} />
    </div>
  );
}
