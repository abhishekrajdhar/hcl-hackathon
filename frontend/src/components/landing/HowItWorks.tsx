import { Reveal } from "@/components/landing/motion";

const STEPS = [
  {
    n: "01",
    title: "Tell us your goal",
    body: "“I want to become an NLP engineer.” The AI coach extracts the role, your experience, and your weekly time.",
  },
  {
    n: "02",
    title: "We map your skills",
    body: "Your current proficiency is placed on a graph of prerequisites and scored against what the goal actually requires.",
  },
  {
    n: "03",
    title: "Get an adaptive roadmap",
    body: "A phased plan appears — milestones, resources, projects and checkpoints — sequenced so nothing is out of order.",
  },
  {
    n: "04",
    title: "Learn — it adapts",
    body: "Every completion and assessment updates your skills, unlocks what's next, and re-tunes recommendations automatically.",
  },
];

export function HowItWorks() {
  return (
    <section id="how" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 lg:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <Reveal>
            <span className="text-xs font-semibold uppercase tracking-widest text-brand">How it works</span>
          </Reveal>
          <Reveal delay={80}>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
              From a sentence to a <span className="text-gradient">self-updating plan</span>
            </h2>
          </Reveal>
        </div>

        <div className="relative mt-16">
          {/* connecting line */}
          <div className="absolute left-0 right-0 top-7 hidden h-px bg-gradient-to-r from-transparent via-border to-transparent lg:block" />
          <div className="grid gap-8 lg:grid-cols-4">
            {STEPS.map((s, i) => (
              <Reveal key={s.n} delay={i * 120} className="relative text-center lg:text-left">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-surface text-lg font-bold text-brand shadow-card lg:mx-0">
                  <span className="text-gradient">{s.n}</span>
                </div>
                <h3 className="mt-4 text-lg font-semibold">{s.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted">{s.body}</p>
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
