"use client";

/** The catalogue as a telemetry ticker rather than a pill cloud. */
const SKILLS = [
  "python", "statistics", "linear-algebra", "machine-learning", "deep-learning",
  "neural-networks", "pytorch", "cnn", "transformers", "nlp-fundamentals",
  "computer-vision", "generative-ai", "large-language-models", "rag-systems",
  "mlops-fundamentals", "model-deployment", "docker-containers", "etl-pipelines",
];

export function Marquee() {
  return (
    <section className="relative border-y border-line bg-panel/30 py-5">
      <div className="marquee-mask relative flex overflow-hidden">
        <div className="marquee-track flex shrink-0 items-center gap-8 pr-8">
          {[...SKILLS, ...SKILLS].map((s, i) => (
            <span key={i} className="flex shrink-0 items-center gap-2.5 whitespace-nowrap">
              <span className="h-1 w-1 rounded-full bg-teal" />
              <span className="label-meta text-text-2">{s}</span>
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
