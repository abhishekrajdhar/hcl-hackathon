"use client";

import { useEffect } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  IconArrow,
  IconBook,
  IconCheck,
  IconClock,
  IconExternal,
  IconLock,
  IconSpark,
  IconTarget,
} from "@/components/ui/icons";
import { clsx } from "@/lib/cn";
import { difficultyLabel, hoursFromMinutes } from "@/lib/format";
import { STATE_LABEL, type RoadmapMilestone, type RoadmapResource } from "@/lib/roadmap-view";
import { useProgress } from "@/lib/progress-context";

const STATE_TONE = {
  completed: "success",
  current: "accent",
  available: "brand",
  locked: "neutral",
} as const;

/** Detail overlay for a clicked resource: info, time, skills, prereqs, why. */
export function ResourceModal({
  resource,
  milestone,
  onClose,
}: {
  resource: RoadmapResource | null;
  milestone: RoadmapMilestone | null;
  onClose: () => void;
}) {
  const { completeResource, skipResource, sendFeedback, pending } = useProgress();

  useEffect(() => {
    if (!resource) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [resource, onClose]);

  if (!resource) return null;
  const locked = resource.status === "locked";

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/50 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`${resource.title} details`}
    >
      <div
        className="scroll-thin max-h-[88vh] w-full max-w-lg overflow-y-auto rounded-t-2xl border border-border bg-surface shadow-card sm:rounded-2xl animate-in"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-start justify-between gap-3 border-b border-border p-5">
          <div className="min-w-0">
            <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
              <Badge tone="accent">{resource.type}</Badge>
              <Badge tone={STATE_TONE[resource.status]}>{STATE_LABEL[resource.status]}</Badge>
              {resource.isOptional && <Badge tone="neutral">optional</Badge>}
            </div>
            <h3 className="text-lg font-semibold leading-tight">{resource.title}</h3>
            {resource.provider && (
              <p className="mt-0.5 text-xs text-muted">{resource.provider}</p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-muted hover:bg-surface-2 hover:text-fg"
          >
            ✕
          </button>
        </div>

        <div className="space-y-4 p-5">
          {resource.description && (
            <p className="text-sm leading-relaxed text-fg/90">{resource.description}</p>
          )}

          {/* facts */}
          <div className="grid grid-cols-2 gap-2">
            <Fact icon={<IconClock className="h-3.5 w-3.5" />} label="Estimated time">
              {hoursFromMinutes(resource.estimatedMinutes)}
            </Fact>
            {resource.difficulty > 0 && (
              <Fact icon={<IconChartBars />} label="Difficulty">
                {difficultyLabel(resource.difficulty)}
              </Fact>
            )}
          </div>

          {/* skills */}
          {resource.skills.length > 0 && (
            <Section icon={<IconTarget className="h-3.5 w-3.5" />} title="Skills you'll build">
              <div className="flex flex-wrap gap-1.5">
                {resource.skills.map((s) => (
                  <span
                    key={s}
                    className="rounded-lg bg-brand-soft px-2 py-0.5 text-xs text-brand"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {/* prerequisites */}
          <Section icon={<IconLock className="h-3.5 w-3.5" />} title="Prerequisites">
            {resource.prerequisites.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {resource.prerequisites.map((p) => (
                  <span
                    key={p}
                    className="inline-flex items-center gap-1 rounded-lg border border-warning/30 bg-warning/10 px-2 py-0.5 text-xs text-warning"
                  >
                    {p}
                  </span>
                ))}
              </div>
            ) : (
              <p className="inline-flex items-center gap-1 text-xs text-success">
                <IconCheck className="h-3.5 w-3.5" /> All prerequisites met
              </p>
            )}
          </Section>

          {/* why recommended */}
          {resource.why && (
            <Section icon={<IconSpark className="h-3.5 w-3.5" />} title="Why this was recommended">
              <p className="rounded-xl border border-brand/20 bg-brand-soft/50 p-3 text-sm text-fg/90">
                {resource.why}
              </p>
            </Section>
          )}
        </div>

        {/* progress actions — drive the adaptive backend */}
        {!locked && milestone && (
          <div className="flex flex-wrap items-center gap-2 border-t border-border px-5 py-3">
            <Button
              size="sm"
              variant="primary"
              disabled={pending}
              onClick={async () => {
                await completeResource(milestone, resource);
                onClose();
              }}
            >
              <IconCheck className="h-3.5 w-3.5" />
              Mark {resource.type === "project" ? "project" : "course"} complete
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={pending}
              onClick={async () => {
                await skipResource(milestone, resource);
                onClose();
              }}
            >
              Skip
            </Button>
            <span className="ml-auto flex items-center gap-1">
              <button
                aria-label="This was helpful"
                disabled={pending}
                onClick={() => sendFeedback(resource, "up")}
                className="grid h-8 w-8 place-items-center rounded-lg border border-border text-muted hover:border-success/40 hover:text-success disabled:opacity-50"
              >
                <IconThumb up />
              </button>
              <button
                aria-label="Not helpful"
                disabled={pending}
                onClick={() => sendFeedback(resource, "down")}
                className="grid h-8 w-8 place-items-center rounded-lg border border-border text-muted hover:border-danger/40 hover:text-danger disabled:opacity-50"
              >
                <IconThumb />
              </button>
            </span>
          </div>
        )}

        {/* footer */}
        <div className="flex items-center justify-between gap-2 border-t border-border p-4">
          <span className="text-xs text-muted">
            {locked ? "Unlocks when prerequisites are complete" : "Ready to start"}
          </span>
          {resource.url && (
            <a href={resource.url} target="_blank" rel="noreferrer">
              <Button variant={locked ? "soft" : "primary"} size="md">
                <IconExternal className="h-4 w-4" />
                {locked ? "Preview" : "Start Learning"}
                {!locked && <IconArrow className="h-4 w-4" />}
              </Button>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function Fact({
  icon,
  label,
  children,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-surface-2/60 p-3">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-muted">
        <span className="text-brand">{icon}</span>
        {label}
      </div>
      <p className="mt-1 text-sm font-semibold">{children}</p>
    </div>
  );
}

function Section({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
        <span className="text-brand">{icon}</span>
        {title}
      </div>
      {children}
    </div>
  );
}

function IconChartBars() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className={clsx("h-3.5 w-3.5")}>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function IconThumb({ up }: { up?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      className={clsx("h-4 w-4", !up && "rotate-180")}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M7 10v11M2 21h5V10H2zM7 10l4-8a2 2 0 0 1 3 2l-1 5h5a2 2 0 0 1 2 2.4l-1.5 7A2 2 0 0 1 20.5 21H7" />
    </svg>
  );
}
