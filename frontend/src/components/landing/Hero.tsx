"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  IconArrow,
  IconCheck,
  IconSpark,
  IconTarget,
} from "@/components/ui/icons";
import { CountUp, Reveal, Spotlight, Tilt } from "@/components/landing/motion";

export function Hero() {
  return (
    <section className="relative overflow-hidden pt-32 pb-16 sm:pt-40 lg:pb-24">
      <Spotlight />
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 lg:grid-cols-[1.05fr_0.95fr] lg:px-6">
        {/* copy */}
        <div className="relative z-10 text-center lg:text-left">
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface/70 px-3 py-1 text-xs font-medium text-muted backdrop-blur">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-70" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
              </span>
              Adaptive learning, powered by AI
            </span>
          </Reveal>

          <Reveal delay={80}>
            <h1 className="mt-5 text-4xl font-extrabold leading-[1.05] tracking-tight sm:text-5xl lg:text-6xl">
              Master any skill on a
              <br className="hidden sm:block" /> path that{" "}
              <span className="text-gradient">rewrites itself</span>
              <br className="hidden sm:block" /> as you learn.
            </h1>
          </Reveal>

          <Reveal delay={160}>
            <p className="mx-auto mt-5 max-w-xl text-base text-muted sm:text-lg lg:mx-0">
              Pathwise turns your goal into a personalized roadmap, tracks every skill you
              build, and adapts the plan the moment your progress changes — with an AI coach
              that always tells you the <em>why</em>.
            </p>
          </Reveal>

          <Reveal delay={240}>
            <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row lg:justify-start">
              <Link
                href="/dashboard"
                className="group relative inline-flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-brand to-accent px-5 py-3 text-sm font-semibold text-white shadow-card transition-transform hover:scale-[1.03] sm:w-auto"
              >
                <span className="relative z-10">Start learning free</span>
                <IconArrow className="relative z-10 h-4 w-4 transition-transform group-hover:translate-x-1" />
                <span className="absolute inset-0 -translate-x-full bg-white/20 transition-transform duration-500 group-hover:translate-x-full" />
              </Link>
              <a
                href="#how"
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-surface/60 px-5 py-3 text-sm font-semibold text-fg backdrop-blur transition-colors hover:bg-surface sm:w-auto"
              >
                See how it works
              </a>
            </div>
          </Reveal>

          <Reveal delay={320}>
            <dl className="mt-10 grid max-w-md grid-cols-3 gap-4 lg:mx-0">
              <Stat value={<CountUp to={40} suffix="k+" />} label="Learners" />
              <Stat value={<CountUp to={1200} suffix="+" />} label="Skills mapped" />
              <Stat value={<CountUp to={94} suffix="%" />} label="Stay on track" />
            </dl>
          </Reveal>
        </div>

        {/* visual */}
        <Reveal delay={200} className="relative z-10">
          <HeroVisual />
        </Reveal>
      </div>
    </section>
  );
}

function Stat({ value, label }: { value: React.ReactNode; label: string }) {
  return (
    <div>
      <dt className="text-2xl font-bold tracking-tight sm:text-3xl">{value}</dt>
      <dd className="mt-0.5 text-xs text-muted">{label}</dd>
    </div>
  );
}

// ---- floating product visual -----------------------------------------------

function HeroVisual() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const id = window.setTimeout(() => setMounted(true), 250);
    return () => window.clearTimeout(id);
  }, []);

  const skills = [
    { name: "Python", value: 0.9 },
    { name: "Deep Learning", value: 0.62 },
    { name: "PyTorch", value: 0.41 },
  ];

  return (
    <div className="relative mx-auto max-w-md">
      {/* floating accent chips — sit above/below the card so they never
          overlap its content at any width */}
      <div className="animate-float-slow absolute -top-5 left-4 z-20 hidden rounded-2xl border border-border bg-surface/90 px-3 py-2 shadow-card backdrop-blur sm:block">
        <div className="flex items-center gap-2 text-xs font-medium">
          <span className="grid h-6 w-6 place-items-center rounded-lg bg-success/15 text-success">
            <IconCheck className="h-3.5 w-3.5" />
          </span>
          Milestone unlocked
        </div>
      </div>
      <div className="animate-float absolute -bottom-5 right-4 z-20 hidden rounded-2xl border border-border bg-surface/90 px-3 py-2 shadow-card backdrop-blur sm:block">
        <div className="flex items-center gap-2 text-xs font-medium">
          <span className="grid h-6 w-6 place-items-center rounded-lg bg-brand-soft text-brand">
            <IconSpark className="h-3.5 w-3.5" />
          </span>
          AI coach online
        </div>
      </div>

      <Tilt className="relative z-10">
        <div className="relative overflow-hidden rounded-3xl border border-border bg-surface/80 p-5 shadow-card backdrop-blur-xl">
          {/* sheen sweep */}
          <div className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-white/10 to-transparent [animation:sheen_5s_ease-in-out_infinite]" />

          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="inline-flex items-center gap-1.5 rounded-full bg-brand/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-brand">
                <IconTarget className="h-3 w-3" /> Goal
              </div>
              <p className="mt-1 text-sm font-bold">ML Engineer</p>
            </div>
            <Ring value={0.68} mounted={mounted} />
          </div>

          <div className="space-y-3">
            {skills.map((s, i) => (
              <div key={s.name}>
                <div className="mb-1 flex justify-between text-[11px]">
                  <span className="font-medium">{s.name}</span>
                  <span className="text-muted">{Math.round(s.value * 100)}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-brand to-accent transition-[width] duration-1000 ease-out"
                    style={{
                      width: mounted ? `${s.value * 100}%` : "0%",
                      transitionDelay: `${400 + i * 180}ms`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex items-center gap-2 rounded-xl border border-brand/25 bg-brand-soft/50 p-2.5">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-brand text-white">
              <IconArrow className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <p className="text-[11px] font-semibold">Next: PyTorch Fundamentals</p>
              <p className="truncate text-[10px] text-muted">Adapts as you complete each step</p>
            </div>
          </div>
        </div>
      </Tilt>

      {/* glow */}
      <div className="absolute -inset-8 -z-10 rounded-[3rem] bg-gradient-to-tr from-brand/25 to-accent/25 blur-3xl" />
    </div>
  );
}

function Ring({ value, mounted }: { value: number; mounted: boolean }) {
  const size = 56;
  const stroke = 6;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="url(#ringgrad)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={mounted ? c * (1 - value) : c}
          style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.22,1,0.36,1) 0.3s" }}
        />
        <defs>
          <linearGradient id="ringgrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--brand)" />
            <stop offset="100%" stopColor="var(--accent)" />
          </linearGradient>
        </defs>
      </svg>
      <span className="absolute text-xs font-bold">{Math.round(value * 100)}%</span>
    </div>
  );
}
