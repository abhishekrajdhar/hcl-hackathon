import Link from "next/link";
import { IconArrow } from "@/components/ui/icons";
import { Reveal, Spotlight } from "@/components/landing/motion";

export function CTA() {
  return (
    <section className="relative py-20 sm:py-28">
      <div className="mx-auto max-w-5xl px-4 lg:px-6">
        <Reveal>
          <div className="relative overflow-hidden rounded-3xl border border-brand/30 bg-gradient-to-br from-brand/15 via-surface to-accent/15 p-10 text-center shadow-card sm:p-16">
            <Spotlight />
            <div className="animate-blob absolute -right-16 -top-16 h-56 w-56 rounded-full bg-accent/20 blur-3xl" />
            <div className="animate-blob absolute -bottom-16 -left-16 h-56 w-56 rounded-full bg-brand/20 blur-3xl" style={{ animationDelay: "-8s" }} />

            <div className="relative">
              <h2 className="text-3xl font-extrabold tracking-tight sm:text-5xl">
                Learn smarter,
                <br />
                <span className="text-gradient">not just harder.</span>
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-muted">
                Set your goal in one sentence. Get a roadmap that adapts to every step you take.
                Free to start — no card required.
              </p>
              <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Link
                  href="/dashboard"
                  className="group relative inline-flex items-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-brand to-accent px-6 py-3 text-sm font-semibold text-white shadow-card transition-transform hover:scale-[1.04]"
                >
                  <span className="relative z-10">Start your path</span>
                  <IconArrow className="relative z-10 h-4 w-4 transition-transform group-hover:translate-x-1" />
                  <span className="absolute inset-0 -translate-x-full bg-white/25 transition-transform duration-500 group-hover:translate-x-full" />
                </Link>
                <Link
                  href="/dashboard"
                  className="rounded-xl border border-border bg-surface/70 px-6 py-3 text-sm font-semibold backdrop-blur transition-colors hover:bg-surface"
                >
                  Explore the demo
                </Link>
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
