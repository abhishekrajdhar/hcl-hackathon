"use client";

// The landing hero runs the actual Learning Universe — the same GalaxyScene,
// the same demo graph, the same mastery colours the product uses. A mockup
// would be easier; showing the real engine is the whole argument.
//
// It renders in ambient mode: the camera drifts, nothing is selectable, and
// pointer events pass through to the page beneath so the 3D never steals a
// click meant for the call to action.

import dynamic from "next/dynamic";
import { demoGraph } from "@/lib/graph-demo";

const GalaxyScene = dynamic(
  () => import("@/components/dashboard/universe/GalaxyScene").then((m) => m.GalaxyScene),
  { ssr: false, loading: () => null },
);

const NOTHING = new Set<string>();
const noop = () => undefined;

export function HeroWorld() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      <GalaxyScene model={demoGraph} selectedId={null} onSelect={noop} pulseIds={NOTHING} />
      {/* Hold the world back so the type in front of it stays the subject. */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(90deg, rgba(7,10,13,0.94) 0%, rgba(7,10,13,0.72) 38%, rgba(7,10,13,0.25) 65%, rgba(7,10,13,0.55) 100%)",
        }}
      />
      <div
        className="absolute inset-x-0 bottom-0 h-40"
        style={{ background: "linear-gradient(180deg, transparent, var(--void))" }}
      />
    </div>
  );
}
