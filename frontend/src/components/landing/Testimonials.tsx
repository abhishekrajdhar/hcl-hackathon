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
    <section id="testimonials" className="relative border-t border-line py-24 lg:py-32">
      <div className="mx-auto max-w-[1400px] px-6 lg:px-12">
        <Reveal>
          <p className="label-meta text-cyan">Field reports</p>
        </Reveal>
        <div className="mt-14 grid gap-px border-t border-line bg-line lg:grid-cols-3">
          {QUOTES.map((q, i) => (
            <Reveal key={q.name} delay={i * 70} className="bg-void">
              <figure className="h-full p-8">
                <blockquote className="display text-[17px] font-medium leading-snug text-text">
                  &ldquo;{q.quote}&rdquo;
                </blockquote>
                <figcaption className="mt-6 flex items-center gap-2.5">
                  <span className="h-px w-6 bg-cyan/50" />
                  <span className="label-meta text-text-2">{q.name}</span>
                  <span className="label-meta">{q.role}</span>
                </figcaption>
              </figure>
            </Reveal>
          ))}
        </div>
        <p className="label-meta mt-8">Composite personas, not real individuals.</p>
      </div>
    </section>
  );
}
