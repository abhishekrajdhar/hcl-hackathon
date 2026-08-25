"use client";

import { Reveal } from "@/components/landing/motion";

/**
 * The engine's subsystems, presented as a spec sheet rather than a card grid:
 * a number, a name, and what it actually does. Each entry is a real module in
 * the codebase, which is the point — this is not a feature list, it is the
 * architecture.
 */
const SUBSYSTEMS = [
  {
    id: "01",
    name: "Skill graph",
    module: "engines/skill_graph",
    body: "A directed acyclic graph of every skill and what it rests on. Cycles are refused at write time by a depth-bounded recursive CTE — the ordering is auditable, not guessed.",
  },
  {
    id: "02",
    name: "Gap analysis",
    module: "engines/skill_gap",
    body: "Where you are against what the goal demands, skill by skill. Gaps are ordered topologically, never by size, so a prerequisite always precedes what depends on it.",
  },
  {
    id: "03",
    name: "Ranking",
    module: "engines/recommendation",
    body: "A weighted hybrid score over eight signals, with a readiness gate that demotes anything you cannot start yet. Every number is inspectable.",
  },
  {
    id: "04",
    name: "Path generator",
    module: "engines/path",
    body: "Milestones phased into a schedule that fits the hours you actually have. Pure — no clock, no model, reproducible from the same inputs.",
  },
  {
    id: "05",
    name: "Adaptive engine",
    module: "engines/adaptive",
    body: "Assessment evidence moves your proficiency through fixed threshold bands, unlocking or remediating the route as it goes.",
  },
  {
    id: "06",
    name: "Grounded coach",
    module: "engines/chat",
    body: "Rule-based intent, real tools, and a grounding check that rejects any claim absent from the evidence. The model writes prose; it never decides a fact.",
  },
];

export function Features() {
  return (
    <section id="engine" className="relative border-t border-line py-24 lg:py-32">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <Reveal>
          <p className="label-meta text-cyan">The engine</p>
          <h2 className="display mt-4 max-w-2xl text-3xl font-semibold leading-tight lg:text-[42px]">
            Nine deterministic engines.
            <br />
            The model only writes the prose.
          </h2>
        </Reveal>

        <div className="mt-16 grid gap-px border-t border-line bg-line md:grid-cols-2 lg:grid-cols-3">
          {SUBSYSTEMS.map((s, i) => (
            <Reveal key={s.id} delay={i * 60} className="bg-void">
              <article className="group h-full p-7 transition-colors hover:bg-panel">
                <div className="flex items-baseline justify-between">
                  <span className="readout display text-[13px] font-semibold text-cyan">{s.id}</span>
                  <span className="label-meta opacity-0 transition-opacity group-hover:opacity-100">
                    {s.module}
                  </span>
                </div>
                <h3 className="display mt-5 text-[19px] font-semibold">{s.name}</h3>
                <p className="mt-3 text-[13px] leading-relaxed text-text-2">{s.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
