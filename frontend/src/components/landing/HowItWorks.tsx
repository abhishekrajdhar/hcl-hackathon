"use client";

import { Reveal } from "@/components/landing/motion";

/** The pipeline, drawn as a signal chain rather than four marketing steps. */
const STAGES = [
  {
    id: "IN",
    title: "You describe the goal",
    body: "Out loud or typed. A time budget and the skills you already have are pulled from the same sentence.",
  },
  {
    id: "01",
    title: "Position is located",
    body: "Your proficiencies are placed against the prerequisite graph to find exactly where you stand in it.",
  },
  {
    id: "02",
    title: "Route is computed",
    body: "The gap engine orders what is missing; the path generator phases it into a schedule that fits your week.",
  },
  {
    id: "03",
    title: "Evidence re-routes it",
    body: "Every assessment and completion moves your position, and the route is recomputed around the new one.",
  },
  {
    id: "OUT",
    title: "The world redraws",
    body: "Nodes light, paths open, fog recedes. What you see is the state of the engine, not an illustration of it.",
  },
];

export function HowItWorks() {
  return (
    <section id="pipeline" className="relative border-t border-line py-24 lg:py-32">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <Reveal>
          <p className="label-meta text-cyan">The pipeline</p>
          <h2 className="display mt-4 max-w-2xl text-3xl font-semibold leading-tight lg:text-[42px]">
            A closed loop, not a course list.
          </h2>
        </Reveal>

        <ol className="mt-16 space-y-px">
          {STAGES.map((s, i) => (
            <Reveal key={s.id} delay={i * 70}>
              <li className="group relative grid gap-4 border-l border-line py-7 pl-8 transition-colors hover:border-cyan/50 md:grid-cols-[110px_1fr_2fr] md:gap-10">
                {/* Node on the signal line. */}
                <span
                  aria-hidden
                  className="absolute -left-[4px] top-9 h-[7px] w-[7px] rounded-full bg-line-strong transition-colors group-hover:bg-cyan group-hover:shadow-glow"
                />
                <span className="readout display text-[13px] font-semibold text-cyan">{s.id}</span>
                <h3 className="display text-[19px] font-semibold leading-snug">{s.title}</h3>
                <p className="max-w-xl text-[13px] leading-relaxed text-text-2">{s.body}</p>
              </li>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
