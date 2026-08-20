const SKILLS = [
  "Python", "Statistics", "Machine Learning", "Deep Learning", "PyTorch", "CNNs",
  "MLOps", "NLP", "Transformers", "SQL", "Data Engineering", "Prompt Engineering",
  "Computer Vision", "Reinforcement Learning", "Docker", "Kubernetes",
];

export function Marquee() {
  return (
    <section className="border-y border-border/60 bg-surface/30 py-6 backdrop-blur">
      <p className="mb-4 text-center text-xs font-medium uppercase tracking-widest text-muted">
        One graph of every skill — mapped, gapped, and sequenced
      </p>
      <div className="marquee-mask relative flex overflow-hidden">
        <div className="marquee-track flex shrink-0 items-center gap-3 pr-3">
          {[...SKILLS, ...SKILLS].map((s, i) => (
            <span
              key={i}
              className="whitespace-nowrap rounded-full border border-border bg-surface px-4 py-1.5 text-sm text-muted"
            >
              {s}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
