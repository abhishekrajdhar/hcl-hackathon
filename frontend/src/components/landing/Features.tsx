import {
  IconPath,
  IconSpark,
  IconChart,
  IconChat,
  IconBook,
  IconClipboard,
} from "@/components/ui/icons";
import { Reveal, Tilt } from "@/components/landing/motion";

const FEATURES = [
  {
    icon: IconPath,
    title: "Personalized roadmaps",
    body: "Turn a one-line goal into a phased path — foundations to capstone — sequenced by real skill prerequisites.",
  },
  {
    icon: IconSpark,
    title: "Adaptive engine",
    body: "Complete, skip, or ace an assessment and the plan recalculates instantly — unlocking, reordering, remediating.",
  },
  {
    icon: IconChart,
    title: "Skill-gap analysis",
    body: "See exactly where you stand versus what your goal demands, skill by skill, on a live radar.",
  },
  {
    icon: IconChat,
    title: "AI learning coach",
    body: "Ask what to learn next or why something's recommended. Answers are grounded in your real data — never invented.",
  },
  {
    icon: IconBook,
    title: "Explainable picks",
    body: "Every recommendation shows the why: your gap, your level, your prerequisites. No black boxes.",
  },
  {
    icon: IconClipboard,
    title: "Assessments that count",
    body: "Checkpoints measure mastery and feed straight back into your path — proof, not guesswork.",
  },
];

export function Features() {
  return (
    <section id="features" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 lg:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <Reveal>
            <span className="text-xs font-semibold uppercase tracking-widest text-brand">Everything you need</span>
          </Reveal>
          <Reveal delay={80}>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
              A learning system that <span className="text-gradient">thinks with you</span>
            </h2>
          </Reveal>
          <Reveal delay={140}>
            <p className="mt-4 text-muted">
              Six engines working together — so your plan is always current, personal, and explainable.
            </p>
          </Reveal>
        </div>

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={i * 70}>
              <Tilt max={6}>
                <article className="group relative h-full overflow-hidden rounded-2xl border border-border bg-surface/70 p-6 backdrop-blur transition-colors hover:border-brand/40">
                  <div className="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-brand/10 blur-2xl transition-opacity group-hover:opacity-100 opacity-0" />
                  <span className="inline-grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-brand to-accent text-white shadow-card transition-transform group-hover:scale-110 group-hover:-rotate-6">
                    <f.icon className="h-5 w-5" />
                  </span>
                  <h3 className="mt-4 text-lg font-semibold">{f.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted">{f.body}</p>
                </article>
              </Tilt>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
