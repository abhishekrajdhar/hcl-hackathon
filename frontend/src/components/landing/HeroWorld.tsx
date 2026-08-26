"use client";

// The landing hero runs the actual Learning Universe — the same GalaxyScene,
// the same demo graph, the same mastery colours the product uses. A mockup
// would be easier; showing the real engine is the whole argument.
//
// It renders in ambient mode: the camera drifts, nothing is selectable, and
// pointer events pass through so the 3D never steals a click from the CTA.
// It fills its own container rather than the viewport, so the copy beside it
// keeps a clean, uncrowded column.

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

      {/* Feather the panel's edges so the world dissolves into the page
          instead of ending on a hard rectangle. */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(90deg, var(--void) 0%, rgba(7,10,13,0.4) 8%, transparent 22%)",
        }}
      />
      <div
        className="absolute inset-x-0 top-0 h-24"
        style={{ background: "linear-gradient(180deg, var(--void), transparent)" }}
      />
      <div
        className="absolute inset-x-0 bottom-0 h-28"
        style={{ background: "linear-gradient(0deg, var(--void), transparent)" }}
      />
    </div>
  );
}
