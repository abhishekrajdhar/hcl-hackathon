import { Reveal } from "@/components/landing/motion";

// Illustrative testimonials (composite personas — not real individuals).
const QUOTES = [
  {
    quote:
      "It felt like a mentor who actually remembered where I was. The path shuffled itself after every quiz — I never wondered what to do next.",
    name: "Maya R.",
    role: "Career switcher → ML Engineer",
    initials: "MR",
  },
  {
    quote:
      "The ‘why this?’ on every recommendation is the killer feature. I finally trusted the plan instead of second-guessing it.",
    name: "Devon K.",
    role: "Data Analyst",
    initials: "DK",
  },
  {
    quote:
      "I set one goal and got a roadmap sequenced better than anything I'd have built myself. Skipped the fluff, went straight to my gaps.",
    name: "Aisha N.",
    role: "CS Student",
    initials: "AN",
  },
];

export function Testimonials() {
  return (
    <section id="testimonials" className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-6xl px-4 lg:px-6">
        <div className="mx-auto max-w-2xl text-center">
          <Reveal>
            <span className="text-xs font-semibold uppercase tracking-widest text-brand">Loved by learners</span>
          </Reveal>
          <Reveal delay={80}>
            <h2 className="mt-3 text-3xl font-extrabold tracking-tight sm:text-4xl">
              Progress you can <span className="text-gradient">feel</span>
            </h2>
          </Reveal>
        </div>

        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {QUOTES.map((q, i) => (
            <Reveal key={q.name} delay={i * 100}>
              <figure className="flex h-full flex-col rounded-2xl border border-border bg-surface/70 p-6 backdrop-blur transition-transform hover:-translate-y-1">
                <div className="mb-3 text-3xl leading-none text-brand">“</div>
                <blockquote className="flex-1 text-sm leading-relaxed text-fg/90">{q.quote}</blockquote>
                <figcaption className="mt-5 flex items-center gap-3">
                  <span className="grid h-10 w-10 place-items-center rounded-full bg-gradient-to-br from-brand to-accent text-xs font-bold text-white">
                    {q.initials}
                  </span>
                  <div>
                    <div className="text-sm font-semibold">{q.name}</div>
                    <div className="text-xs text-muted">{q.role}</div>
                  </div>
                </figcaption>
              </figure>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
