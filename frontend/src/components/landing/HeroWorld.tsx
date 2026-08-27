"use client";

// The landing hero runs the actual Learning Universe — the same GalaxyScene,
// the same mastery colours the product uses, fed by the live backend. The
// unauthenticated public endpoint serves the seeded demo learner's real graph
// and proficiencies, so what a visitor sees is what the engine computed, not
// a bundled dataset. If the backend is unreachable the world simply stays
// dark — an empty sky, never a fake one.
//
// It renders in ambient mode: the camera drifts, nothing is selectable, and
// pointer events pass through so the 3D never steals a click from the CTA.

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { publicApi } from "@/lib/api";
import { buildGraphModel } from "@/lib/graph-derive";
import type { GraphModel } from "@/lib/graph-view";

const GalaxyScene = dynamic(
  () => import("@/components/dashboard/universe/GalaxyScene").then((m) => m.GalaxyScene),
  { ssr: false, loading: () => null },
);

const NOTHING = new Set<string>();
const noop = () => undefined;

export function HeroWorld() {
  const [model, setModel] = useState<GraphModel | null>(null);

  useEffect(() => {
    let cancelled = false;
    publicApi
      .getDemoUniverse()
      .then((u) => {
        if (cancelled || !u.available || !u.graph) return;
        setModel(
          buildGraphModel({
            closures: [u.graph],
            catalogue: u.catalogue,
            targetSlugs: u.target_slugs,
            proficiencies: u.proficiencies.map((p) => ({
              slug: p.slug,
              current: p.current,
              target: p.target,
            })),
            goal: u.goal ?? "",
          }),
        );
      })
      .catch(() => undefined); // no backend, no galaxy — the copy still stands
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
      {model && (
        <GalaxyScene model={model} selectedId={null} onSelect={noop} pulseIds={NOTHING} />
      )}

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
