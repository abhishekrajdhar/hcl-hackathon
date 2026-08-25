"use client";

// The AI coach as a floating companion over the world rather than a chat card.
// Collapsed it is a single lit control; expanded it shows the next optimal step
// and hands off to the full assistant. It never invents the recommendation —
// `nextAction` is the same value the rest of the dashboard reads.

import { useState } from "react";
import { clsx } from "@/lib/cn";
import { IconArrow, IconChat, IconMic, IconSpark } from "@/components/ui/icons";
import type { DashboardData } from "@/lib/dashboard-data";

export function CoachDock({
  data,
  onFocusSkill,
}: {
  data: DashboardData;
  /** Point the world at a skill the coach names. */
  onFocusSkill?: (name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const next = data.nextAction;
  const milestone = next?.milestone || data.currentMilestone;

  return (
    <div className={clsx("transition-all duration-300 ease-out", open ? "w-[290px]" : "w-auto")}>
      {open ? (
        <div className="hud hud-bracket hud-raised animate-achievement p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="relative grid h-6 w-6 place-items-center">
                <span className="animate-aura absolute inset-0 rounded-full bg-cyan/25" />
                <IconSpark className="relative h-3.5 w-3.5 text-cyan" />
              </span>
              <span className="label-meta text-cyan">AI Coach</span>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-text-3 transition-colors hover:text-text"
              aria-label="Collapse coach"
            >
              ✕
            </button>
          </div>

          <p className="mt-3 text-[13px] leading-relaxed text-text">
            {next ? (
              <>
                Your next optimal step is{" "}
                <span className="font-semibold text-cyan">{next.title}</span>.
              </>
            ) : (
              <>Tell me a goal and I&apos;ll chart the route through your universe.</>
            )}
          </p>
          {milestone && (
            <p className="mt-1.5 text-[11px] text-text-2">
              Advances <span className="text-text">{milestone}</span>
              {next?.estimatedMinutes ? ` · ~${Math.round(next.estimatedMinutes / 60)}h` : ""}
            </p>
          )}

          <div className="hud-rule my-3.5" />

          <div className="flex items-center gap-2">
            {milestone && onFocusSkill && (
              <button
                onClick={() => onFocusSkill(milestone)}
                className="flex flex-1 items-center justify-center gap-1.5 border border-cyan/40 bg-cyan/10 px-2.5 py-2 text-[11px] font-medium text-cyan transition-colors hover:bg-cyan/20"
              >
                Show me <IconArrow className="h-3 w-3" />
              </button>
            )}
            <a
              href="#assistant"
              className="flex flex-1 items-center justify-center gap-1.5 border border-line-strong px-2.5 py-2 text-[11px] font-medium text-text-2 transition-colors hover:border-cyan/40 hover:text-cyan"
            >
              <IconChat className="h-3 w-3" /> Ask
            </a>
            <a
              href="#assistant"
              aria-label="Talk to your coach"
              title="Talk to your coach"
              className="grid h-[34px] w-[34px] place-items-center border border-line-strong text-text-2 transition-colors hover:border-cyan/40 hover:text-cyan"
            >
              <IconMic className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="hud hud-bracket group flex items-center gap-2.5 px-3.5 py-2.5 transition-colors hover:border-cyan/40"
        >
          <span className="relative grid h-5 w-5 place-items-center">
            <span className="animate-aura absolute inset-0 rounded-full bg-cyan/25" />
            <IconSpark className="relative h-3 w-3 text-cyan" />
          </span>
          <span className="label-meta text-text-2 transition-colors group-hover:text-cyan">
            AI Coach
          </span>
          {next && <span className="h-1 w-1 rounded-full bg-amber shadow-glow" />}
        </button>
      )}
    </div>
  );
}
