"use client";

import Link from "next/link";
import { Reveal } from "@/components/landing/motion";
import { IconArrow } from "@/components/ui/icons";

export function CTA() {
  return (
    <section className="relative border-t border-line py-28 lg:py-36">
      {/* One distant light source, centred behind the type. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 50% 60% at 50% 50%, rgba(41,230,209,0.08), transparent 70%)",
        }}
      />
      <div className="relative mx-auto max-w-[1400px] px-6 text-center lg:px-12">
        <Reveal>
          <p className="label-meta text-cyan">Ready when you are</p>
          <h2 className="display mx-auto mt-5 max-w-2xl text-3xl font-semibold leading-tight lg:text-[46px]">
            Find out where you actually stand.
          </h2>
          <p className="mx-auto mt-5 max-w-md text-[14px] leading-relaxed text-text-2">
            Describe a goal in a sentence. The engine maps the terrain between
            you and it, and shows you the route.
          </p>
          <Link
            href="/dashboard"
            className="group mt-10 inline-flex items-center gap-2.5 border border-cyan/50 bg-cyan/10 px-7 py-3.5 text-[13px] font-medium tracking-wide text-cyan transition-all hover:bg-cyan/20 hover:shadow-glow"
          >
            ENTER THE UNIVERSE
            <IconArrow className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
          </Link>
        </Reveal>
      </div>
    </section>
  );
}
