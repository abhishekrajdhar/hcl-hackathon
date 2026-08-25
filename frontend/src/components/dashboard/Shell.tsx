"use client";

import { useEffect, useState } from "react";
import { clsx } from "@/lib/cn";
import {
  IconActivity,
  IconBook,
  IconChart,
  IconChat,
  IconClipboard,
  IconFlag,
  IconGraph,
  IconLayers,
  IconLogout,
  IconPath,
  IconSpark,
  IconTarget,
} from "@/components/ui/icons";

/** Sections, in page order. The rail scrolls to them; ids are unchanged. */
const NAV = [
  { id: "universe", label: "Learning Universe", icon: IconSpark },
  { id: "overview", label: "Overview", icon: IconTarget },
  { id: "next-action", label: "Current Mission", icon: IconFlag },
  { id: "roadmap", label: "Roadmap", icon: IconLayers },
  { id: "path", label: "Learning Path", icon: IconPath },
  { id: "skills", label: "Skill Progress", icon: IconChart },
  { id: "graph", label: "Knowledge Graph", icon: IconGraph },
  { id: "milestones", label: "Milestones", icon: IconFlag },
  { id: "recommendations", label: "Recommended", icon: IconBook },
  { id: "assessments", label: "Assessments", icon: IconClipboard },
  { id: "activity", label: "Activity", icon: IconActivity },
  { id: "assistant", label: "AI Coach", icon: IconChat },
];

/**
 * The world's chrome: a compact floating rail on the left and a thin status
 * strip on top. Nothing is a card and nothing is opaque — both float over the
 * content so the universe reads as the page rather than as a widget on it.
 */
export function Shell({
  children,
  userLabel,
  isDemo,
  onSignOut,
  hud,
}: {
  children: React.ReactNode;
  userLabel: string;
  isDemo: boolean;
  onSignOut: () => void;
  /** Live status readouts rendered into the top strip. */
  hud?: React.ReactNode;
}) {
  const active = useActiveSection(NAV.map((n) => n.id));

  return (
    <div className="world-backdrop relative min-h-screen text-text">
      {/* Distant structure behind everything. Fades out at the edges so it
          never competes with the 3D world. */}
      <div aria-hidden className="world-grid pointer-events-none fixed inset-0 -z-10" />

      <TopHud userLabel={userLabel} isDemo={isDemo} onSignOut={onSignOut} hud={hud} />

      <NavRail active={active} />

      {/* Left padding clears the rail; the content itself is full-bleed. */}
      <main className="pb-16 pl-0 pt-12 lg:pl-[68px]">{children}</main>
    </div>
  );
}

/** Thin status strip. Readouts, not dashboard cards. */
function TopHud({
  userLabel,
  isDemo,
  onSignOut,
  hud,
}: {
  userLabel: string;
  isDemo: boolean;
  onSignOut: () => void;
  hud?: React.ReactNode;
}) {
  return (
    <header className="fixed inset-x-0 top-0 z-40 h-12 border-b border-line bg-[color-mix(in_srgb,var(--void)_78%,transparent)] backdrop-blur-xl">
      <div className="flex h-full items-center gap-4 px-4 lg:pl-[80px] lg:pr-6">
        <div className="flex items-center gap-2.5">
          <span className="relative grid h-5 w-5 place-items-center">
            <span className="absolute inset-0 rounded-full border border-cyan/60" />
            <span className="h-1.5 w-1.5 rounded-full bg-cyan shadow-glow" />
          </span>
          <span className="display text-[13px] font-semibold tracking-tight">
            LEARNING UNIVERSE
          </span>
        </div>

        <div className="hidden h-4 w-px bg-line md:block" />

        {/* Live readouts supplied by the page. */}
        <div className="hidden min-w-0 flex-1 md:block">{hud}</div>
        <div className="flex-1 md:hidden" />

        <div className="flex items-center gap-3">
          {isDemo && (
            <span className="label-meta rounded-sm border border-amber/40 px-1.5 py-1 text-amber">
              demo
            </span>
          )}
          <span className="label-meta hidden sm:inline">{userLabel}</span>
          <button
            onClick={onSignOut}
            className="text-text-3 transition-colors hover:text-coral"
            aria-label="Sign out"
          >
            <IconLogout className="h-4 w-4" />
          </button>
        </div>
      </div>
    </header>
  );
}

/** Icon rail that expands on hover. Never occupies layout width beyond 68px. */
function NavRail({ active }: { active: string }) {
  const [open, setOpen] = useState(false);

  return (
    <nav
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      className="fixed left-0 top-12 z-40 hidden h-[calc(100vh-3rem)] lg:block"
      aria-label="Sections"
    >
      <div
        className={clsx(
          "flex h-full flex-col gap-0.5 border-r border-line bg-[color-mix(in_srgb,var(--void)_72%,transparent)] py-4 backdrop-blur-xl transition-[width] duration-200 ease-out",
          open ? "w-[212px]" : "w-[68px]",
        )}
      >
        {NAV.map((n) => {
          const isActive = active === n.id;
          return (
            <a
              key={n.id}
              href={`#${n.id}`}
              aria-current={isActive ? "true" : undefined}
              className={clsx(
                "group relative mx-2 flex items-center gap-3 rounded-sm px-[18px] py-2.5 transition-colors",
                isActive ? "text-cyan" : "text-text-3 hover:text-text",
              )}
            >
              {/* Active marker: a lit edge, not a filled pill. */}
              <span
                className={clsx(
                  "absolute left-0 top-1/2 h-5 w-px -translate-y-1/2 transition-all",
                  isActive ? "bg-cyan shadow-glow" : "bg-transparent",
                )}
              />
              <n.icon className={clsx("h-[18px] w-[18px] shrink-0", isActive && "drop-shadow-[0_0_6px_var(--cyan)]")} />
              {open && (
                <span className="animate-rail-label whitespace-nowrap text-[12px] font-medium tracking-tight">
                  {n.label}
                </span>
              )}
            </a>
          );
        })}
      </div>
    </nav>
  );
}

/**
 * Which section is in view. Uses IntersectionObserver rather than scroll
 * maths so it stays accurate as sections change height (the 3D world is tall).
 */
function useActiveSection(ids: string[]): string {
  const [active, setActive] = useState(ids[0] ?? "");

  useEffect(() => {
    const seen = new Map<string, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) seen.set(entry.target.id, entry.intersectionRatio);
        let best = "";
        let bestRatio = 0;
        for (const [id, ratio] of seen) {
          if (ratio > bestRatio) {
            best = id;
            bestRatio = ratio;
          }
        }
        if (best) setActive(best);
      },
      { threshold: [0, 0.25, 0.5, 0.75, 1], rootMargin: "-15% 0px -55% 0px" },
    );
    for (const id of ids) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [ids]);

  return active;
}
