"use client";

import { useEffect, useState } from "react";
import { clsx } from "@/lib/cn";
import { IconArrow, IconCheck, IconSpark, IconChat } from "@/components/ui/icons";
import { Reveal, useInView } from "@/components/landing/motion";

export function Showcase() {
  return (
    <section id="showcase" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 lg:px-6">
        <div className="max-w-2xl">
          <Reveal>
            <span className="label-meta text-cyan">The interface</span>
          </Reveal>
          <Reveal delay={80}>
            <h2 className="display mt-4 text-3xl font-semibold leading-tight lg:text-[42px]">
              You watch the engine think.
            </h2>
          </Reveal>
        </div>

        <div className="mt-14 grid auto-rows-[minmax(0,1fr)] gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* adaptive spotlight — spans 2 cols */}
          <Reveal className="sm:col-span-2">
            <AdaptiveTile />
          </Reveal>

          {/* AI coach */}
          <Reveal delay={100}>
            <CoachTile />
          </Reveal>

          {/* skill radar */}
          <Reveal delay={160}>
            <RadarTile />
          </Reveal>

          {/* roadmap mini — spans 2 cols */}
          <Reveal delay={220} className="sm:col-span-2">
            <RoadmapTile />
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={clsx(
        "group relative h-full overflow-hidden border border-line bg-panel/70 p-5 backdrop-blur transition-colors hover:border-cyan/40",
        className,
      )}
    >
      {children}
    </div>
  );
}

/** The headline moment: an assessment result moves a skill and the path adapts. */
function AdaptiveTile() {
  const { ref, inView } = useInView<HTMLDivElement>();
  const [after, setAfter] = useState(false);
  useEffect(() => {
    if (!inView) return;
    const id = window.setTimeout(() => setAfter(true), 700);
    return () => window.clearTimeout(id);
  }, [inView]);

  return (
    <Card>
      <div ref={ref} className="flex h-full flex-col">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold">You submitted an assessment</h3>
          <span className="rounded-full bg-brand/15 px-2 py-0.5 text-[10px] font-semibold text-brand">
            adaptive
          </span>
        </div>

        <div className="border border-line bg-panel-2/50 p-4">
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="font-medium">CNN fundamentals</span>
            <span className={clsx("font-semibold transition-colors", after ? "text-success" : "text-muted")}>
              {after ? "35% → 78%" : "35%"}
            </span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand to-accent transition-[width] duration-[1100ms] ease-out"
              style={{ width: after ? "78%" : "35%" }}
            />
          </div>
        </div>

        <div
          className={clsx(
            "mt-3 flex items-start gap-2 border border-cyan/25 bg-cyan/5 p-3 transition-all duration-500",
            after ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0",
          )}
        >
          <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-lg bg-brand text-white">
            <IconSpark className="h-3.5 w-3.5" />
          </span>
          <p className="text-xs leading-relaxed">
            <span className="font-semibold">Your roadmap has been updated.</span>{" "}
            You've demonstrated strong CNN fundamentals — we've moved you on to{" "}
            <span className="font-semibold text-brand">Object Detection</span>.
          </p>
        </div>

        <p className="mt-auto pt-3 text-[11px] text-muted">
          No forms, no re-planning. One result, and the whole path re-tunes.
        </p>
      </div>
    </Card>
  );
}

function CoachTile() {
  return (
    <Card>
      <div className="mb-3 flex items-center gap-2">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-brand-soft text-brand">
          <IconChat className="h-4 w-4" />
        </span>
        <h3 className="text-sm font-semibold">AI coach</h3>
      </div>
      <div className="space-y-2">
        <div className="ml-auto w-fit max-w-[85%] border border-cyan/40 bg-cyan/15 px-3 py-1.5 text-xs text-cyan">
          What should I learn next?
        </div>
        <div className="w-fit max-w-[90%] border border-line bg-panel-2 px-3 py-1.5 text-xs">
          Start <b>PyTorch Fundamentals</b> — it closes your biggest gap and you meet every prerequisite.
        </div>
        <div className="flex gap-1">
          <span className="rounded bg-fg/5 px-1.5 py-0.5 text-[9px] text-muted">get next action</span>
          <span className="rounded bg-fg/5 px-1.5 py-0.5 text-[9px] text-muted">get skill gaps</span>
        </div>
      </div>
    </Card>
  );
}

function RadarTile() {
  // static hexagon radar (current vs target)
  const pts = (r: number) =>
    Array.from({ length: 6 }, (_, i) => {
      const a = (Math.PI / 3) * i - Math.PI / 2;
      return `${50 + r * Math.cos(a)},${50 + r * Math.sin(a)}`;
    }).join(" ");
  return (
    <Card>
      <h3 className="mb-2 text-sm font-semibold">Skill vs. goal</h3>
      <svg viewBox="0 0 100 100" className="mx-auto h-36 w-36">
        <polygon points={pts(42)} fill="none" stroke="var(--border)" strokeWidth="0.6" />
        <polygon points={pts(28)} fill="none" stroke="var(--border)" strokeWidth="0.6" />
        <polygon points={pts(14)} fill="none" stroke="var(--border)" strokeWidth="0.6" />
        <polygon points="50,12 84,32 78,72 30,76 18,44 40,24" fill="var(--accent)" fillOpacity="0.12" stroke="var(--accent)" strokeWidth="1" />
        <polygon points="50,26 70,40 66,64 38,66 32,46 44,34" fill="var(--brand)" fillOpacity="0.25" stroke="var(--brand)" strokeWidth="1.2" />
      </svg>
      <div className="flex justify-center gap-3 text-[10px] text-muted">
        <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-brand" /> Current</span>
        <span className="flex items-center gap-1"><i className="h-2 w-2 rounded-full bg-accent" /> Target</span>
      </div>
    </Card>
  );
}

function RoadmapTile() {
  const phases = [
    { t: "Foundations", s: "done" },
    { t: "Machine Learning", s: "done" },
    { t: "Deep Learning", s: "current" },
    { t: "Production", s: "next" },
    { t: "Capstone", s: "next" },
  ] as const;
  return (
    <Card>
      <h3 className="mb-4 text-sm font-semibold">Your roadmap, at a glance</h3>
      <div className="flex items-center gap-1.5 overflow-hidden">
        {phases.map((p, i) => (
          <div key={p.t} className="flex flex-1 items-center gap-1.5">
            <div className="flex flex-col items-center gap-1.5 text-center">
              <span
                className={clsx(
                  "grid h-8 w-8 place-items-center border text-[11px] font-semibold",
                  p.s === "done"
                    ? "border-success bg-success text-white"
                    : p.s === "current"
                      ? "border-brand bg-brand text-white animate-pulse-ring"
                      : "border-border bg-surface text-muted",
                )}
              >
                {p.s === "done" ? <IconCheck className="h-4 w-4" /> : i + 1}
              </span>
              <span className="hidden text-[10px] text-muted sm:block">{p.t}</span>
            </div>
            {i < phases.length - 1 && (
              <IconArrow className={clsx("h-3.5 w-3.5 shrink-0", p.s === "done" ? "text-success" : "text-border")} />
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}
