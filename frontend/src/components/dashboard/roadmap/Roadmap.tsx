"use client";

import { useState } from "react";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import {
  IconCheck,
  IconClipboard,
  IconClock,
  IconFlag,
  IconLayers,
  IconLock,
  IconPath,
  IconSpark,
  IconTarget,
} from "@/components/ui/icons";
import { clsx } from "@/lib/cn";
import { hoursFromMinutes } from "@/lib/format";
import {
  STATE_LABEL,
  type RoadmapMilestone,
  type RoadmapPhase,
  type RoadmapResource,
  type RoadmapState,
  type RoadmapView,
} from "@/lib/roadmap-view";
import type { DashboardData } from "@/lib/dashboard-data";
import { useProgress } from "@/lib/progress-context";
import { ResourceModal } from "./ResourceModal";

// Visual identity per state — shared across nodes, badges and rails.
const STATE: Record<
  RoadmapState,
  { badge: "success" | "accent" | "brand" | "neutral"; ring: string; rail: string; bar: "success" | "accent" | "brand" }
> = {
  completed: { badge: "success", ring: "border-success bg-success text-white", rail: "bg-success", bar: "success" },
  current: { badge: "accent", ring: "border-accent bg-accent text-white", rail: "bg-accent", bar: "accent" },
  available: { badge: "brand", ring: "border-brand bg-brand text-white", rail: "bg-brand", bar: "brand" },
  locked: { badge: "neutral", ring: "border-border bg-surface text-muted", rail: "bg-border", bar: "brand" },
};

interface OpenResource {
  resource: RoadmapResource;
  milestone: RoadmapMilestone;
}

export function Roadmap({ data }: { data: DashboardData }) {
  const roadmap: RoadmapView = data.roadmap;
  const [open, setOpen] = useState<OpenResource | null>(null);
  // Default-expand the current phase (fall back to the first non-completed one).
  const initial =
    roadmap.phases.find((p) => p.state === "current")?.index ??
    roadmap.phases.find((p) => p.state !== "completed")?.index ??
    roadmap.phases[0]?.index;
  const [expanded, setExpanded] = useState<Set<number>>(new Set(initial !== undefined ? [initial] : []));

  const toggle = (index: number) =>
    setExpanded((s) => {
      const next = new Set(s);
      next.has(index) ? next.delete(index) : next.add(index);
      return next;
    });

  return (
    <Card>
      <CardHeader
        title="Personalized Roadmap"
        subtitle={`${roadmap.phases.length} phases · ~${roadmap.totalPlannedHours}h to your goal`}
        icon={<IconPath />}
        action={
          <Badge tone="brand">
            <IconLayers className="h-3.5 w-3.5" /> {roadmap.progressPct}% complete
          </Badge>
        }
      />
      <CardBody>
        {/* Goal → Phase 1 → … → Capstone vertical flow */}
        <div className="mx-auto max-w-3xl">
          <GoalNode roadmap={roadmap} />

          {roadmap.phases.map((phase) => (
            <div key={phase.index}>
              <Connector state={phase.state} />
              <PhaseNode
                phase={phase}
                expanded={expanded.has(phase.index)}
                onToggle={() => toggle(phase.index)}
                onOpenResource={(resource, milestone) => setOpen({ resource, milestone })}
              />
            </div>
          ))}
        </div>
      </CardBody>

      <ResourceModal
        resource={open?.resource ?? null}
        milestone={open?.milestone ?? null}
        onClose={() => setOpen(null)}
      />
    </Card>
  );
}

// ---- goal node --------------------------------------------------------------

function GoalNode({ roadmap }: { roadmap: RoadmapView }) {
  return (
    <div className="hud hud-bracket relative overflow-hidden border-cyan/25 p-5">
      <div className="flex items-center justify-between gap-4">
        <div className="min-w-0">
          <div className="label-meta mb-2 inline-flex items-center gap-1.5 text-cyan">
            <IconTarget className="h-3.5 w-3.5" /> Goal
          </div>
          <h3 className="truncate text-lg font-bold sm:text-xl">{roadmap.goal}</h3>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-brand">{roadmap.progressPct}%</div>
          <div className="text-[11px] text-muted">overall</div>
        </div>
      </div>
      <div className="mt-3">
        <ProgressBar value={roadmap.progressPct / 100} tone="brand" />
      </div>
    </div>
  );
}

// ---- connector (the ↓ between nodes) ---------------------------------------

function Connector({ state }: { state: RoadmapState }) {
  return (
    <div className="flex flex-col items-center py-1.5" aria-hidden>
      <span className={clsx("h-5 w-0.5 rounded-full", STATE[state].rail)} />
      <svg viewBox="0 0 24 24" className={clsx("-mt-1 h-4 w-4", stateText(state))} fill="currentColor">
        <path d="M12 16l-6-6h12z" />
      </svg>
    </div>
  );
}

function stateText(state: RoadmapState) {
  return state === "completed"
    ? "text-success"
    : state === "current"
      ? "text-accent"
      : state === "available"
        ? "text-brand"
        : "text-border";
}

// ---- phase node -------------------------------------------------------------

function PhaseNode({
  phase,
  expanded,
  onToggle,
  onOpenResource,
}: {
  phase: RoadmapPhase;
  expanded: boolean;
  onToggle: () => void;
  onOpenResource: (r: RoadmapResource, m: RoadmapMilestone) => void;
}) {
  const s = STATE[phase.state];
  return (
    <div
      className={clsx(
        "rounded-2xl border transition-colors",
        phase.isCapstone ? "border-accent/40" : "border-border",
        phase.state === "current" && "ring-1 ring-accent/40",
        phase.state === "locked" && "opacity-90",
      )}
    >
      {/* header (click to expand/collapse) */}
      <button
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <span
          className={clsx(
            "grid h-9 w-9 shrink-0 place-items-center rounded-xl border-2 text-sm font-bold",
            s.ring,
          )}
        >
          {phase.state === "completed" ? (
            <IconCheck className="h-4 w-4" />
          ) : phase.isCapstone ? (
            <IconFlag className="h-4 w-4" />
          ) : phase.state === "locked" ? (
            <IconLock className="h-4 w-4" />
          ) : (
            phase.index + 1
          )}
        </span>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">
              {phase.isCapstone ? "Capstone" : `Phase ${phase.index + 1}`}
            </span>
            <Badge tone={s.badge}>{STATE_LABEL[phase.state]}</Badge>
          </div>
          <h4 className="mt-0.5 truncate text-sm font-semibold sm:text-base">{phase.title}</h4>
          <p className="truncate text-xs text-muted">{phase.objective}</p>
        </div>

        <div className="hidden shrink-0 flex-col items-end gap-1 sm:flex">
          <span className="inline-flex items-center gap-1 text-xs text-muted">
            <IconClock className="h-3.5 w-3.5" /> {hoursFromMinutes(phase.estimatedMinutes)}
          </span>
          <span className="text-xs font-medium">{phase.completionPct}%</span>
        </div>

        <span className={clsx("ml-1 shrink-0 text-muted transition-transform", expanded && "rotate-180")}>
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </button>

      {/* completion bar (always visible) */}
      <div className="px-4 pb-3">
        <ProgressBar value={phase.completionPct / 100} tone={s.bar} />
      </div>

      {/* body */}
      {expanded && (
        <div className="space-y-3 border-t border-border p-4">
          {phase.milestones.map((m) => (
            <MilestoneCard key={m.id} milestone={m} onOpenResource={onOpenResource} />
          ))}
        </div>
      )}
    </div>
  );
}

// ---- milestone --------------------------------------------------------------

function MilestoneCard({
  milestone: m,
  onOpenResource,
}: {
  milestone: RoadmapMilestone;
  onOpenResource: (r: RoadmapResource, m: RoadmapMilestone) => void;
}) {
  const s = STATE[m.state];
  const locked = m.state === "locked";
  const { submitAssessment, completeResource, pending } = useProgress();
  // A passing score that clears the target — demonstrates the adaptive jump.
  const passScore = Math.min(0.95, Math.max(m.required + 0.08, 0.75));
  return (
    <div
      className={clsx(
        "rounded-xl border p-3.5",
        m.state === "current" ? "border-accent/40 bg-accent/5" : "border-border bg-surface-2/40",
        locked && "opacity-95",
      )}
    >
      {/* header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-semibold">{m.title}</span>
            <Badge tone={s.badge}>{STATE_LABEL[m.state]}</Badge>
          </div>
          {m.completionCriteria && (
            <p className="mt-0.5 text-[11px] text-muted">{m.completionCriteria}</p>
          )}
        </div>
        <span className="inline-flex shrink-0 items-center gap-1 text-[11px] text-muted">
          <IconClock className="h-3 w-3" /> {hoursFromMinutes(m.estimatedMinutes)}
        </span>
      </div>

      {/* required skills */}
      {m.requiredSkills.length > 0 && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="text-[10px] uppercase tracking-wide text-muted">Skills</span>
          {m.requiredSkills.map((sk) => (
            <span key={sk} className="rounded-md bg-brand-soft px-1.5 py-0.5 text-[11px] text-brand">
              {sk}
            </span>
          ))}
        </div>
      )}

      {/* proficiency toward target */}
      <div className="mt-2.5">
        <ProgressBar value={m.current} target={m.required} tone={s.bar} />
        <div className="mt-1 flex justify-between text-[11px] text-muted">
          <span>
            {Math.round(m.current * 100)}% → target {Math.round(m.required * 100)}%
          </span>
          <span>{m.completionPct}% complete</span>
        </div>
      </div>

      {/* locked → prerequisites */}
      {locked && m.prerequisites.length > 0 && (
        <div className="mt-2.5 rounded-lg border border-warning/25 bg-warning/5 px-2.5 py-2">
          <div className="mb-1 flex items-center gap-1 text-[11px] font-medium text-warning">
            <IconLock className="h-3 w-3" /> Complete these first
          </div>
          <div className="flex flex-wrap gap-1.5">
            {m.prerequisites.map((p) => (
              <span
                key={p}
                className="rounded-md border border-warning/30 bg-warning/10 px-1.5 py-0.5 text-[11px] text-warning"
              >
                {p}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* items: resources, assessment, project */}
      {(m.resources.length > 0 || m.assessment || m.project) && (
        <div className="mt-3 space-y-1.5">
          {m.resources.map((r) => (
            <ResourceRow
              key={r.id}
              resource={r}
              milestone={m}
              onOpen={() => onOpenResource(r, m)}
            />
          ))}

          {m.assessment && (
            <ItemRow
              icon={<IconClipboard className="h-3.5 w-3.5" />}
              label={m.assessment.title}
              meta={`Checkpoint · ${Math.round(m.assessment.passingPct * 100)}% to pass · ${hoursFromMinutes(m.assessment.estimatedMinutes)}`}
              state={m.assessment.status}
              action={
                m.assessment.status !== "locked" && m.assessment.status !== "completed" ? (
                  <RowButton disabled={pending} onClick={() => submitAssessment(m, passScore)}>
                    Submit result
                  </RowButton>
                ) : undefined
              }
            />
          )}

          {m.project && (
            <ItemRow
              icon={<IconLayers className="h-3.5 w-3.5" />}
              label={m.project.title}
              meta={`Project · ${hoursFromMinutes(m.project.estimatedMinutes)}`}
              state={m.project.status}
              action={
                m.project.status !== "locked" && m.project.status !== "completed" ? (
                  <RowButton
                    disabled={pending}
                    onClick={() => completeResource(m, projectAsResource(m))}
                  >
                    Mark complete
                  </RowButton>
                ) : undefined
              }
            />
          )}
        </div>
      )}
    </div>
  );
}

/** Adapt a milestone's project into a RoadmapResource for the complete action. */
function projectAsResource(m: RoadmapMilestone): RoadmapResource {
  const p = m.project!;
  return {
    id: p.id,
    title: p.title,
    kind: "project",
    type: "project",
    provider: "",
    description: p.description,
    url: "",
    estimatedMinutes: p.estimatedMinutes,
    difficulty: 0,
    skills: p.skills,
    prerequisites: [],
    why: "",
    status: p.status,
    isOptional: false,
  };
}

function RowButton({
  onClick,
  disabled,
  children,
}: {
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="shrink-0 rounded-md bg-brand px-2 py-1 text-[11px] font-medium text-white hover:opacity-90 disabled:opacity-50"
    >
      {children}
    </button>
  );
}

// ---- resource row (clickable → modal; "Why this?" → inline reveal) ---------

function ResourceRow({
  resource: r,
  milestone,
  onOpen,
}: {
  resource: RoadmapResource;
  milestone: RoadmapMilestone;
  onOpen: () => void;
}) {
  const [whyOpen, setWhyOpen] = useState(false);
  const { completeResource, pending } = useProgress();
  const s = STATE[r.status];
  const done = r.status === "completed";
  return (
    <div className="rounded-lg border border-border bg-surface">
      <div className="flex items-center gap-2 p-2">
        <span className={clsx("h-1.5 w-1.5 shrink-0 rounded-full", s.rail)} />
        <button onClick={onOpen} className="min-w-0 flex-1 text-left">
          <span className="block truncate text-sm font-medium hover:text-brand">{r.title}</span>
          <span className="block truncate text-[11px] capitalize text-muted">
            {r.type}
            {r.provider && ` · ${r.provider}`} · {hoursFromMinutes(r.estimatedMinutes)}
          </span>
        </button>
        {!done && r.status !== "locked" && (
          <button
            onClick={() => completeResource(milestone, r)}
            disabled={pending}
            title="Mark complete"
            className="hidden shrink-0 items-center gap-1 rounded-md border border-success/30 bg-success/10 px-2 py-1 text-[11px] font-medium text-success hover:bg-success/20 disabled:opacity-50 sm:inline-flex"
          >
            <IconCheck className="h-3 w-3" /> Complete
          </button>
        )}
        {done && (
          <span className="hidden shrink-0 items-center gap-1 rounded-md bg-success/10 px-2 py-1 text-[11px] font-medium text-success sm:inline-flex">
            <IconCheck className="h-3 w-3" /> Done
          </span>
        )}
        {r.why && (
          <button
            onClick={() => setWhyOpen((o) => !o)}
            className={clsx(
              "inline-flex shrink-0 items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors",
              whyOpen
                ? "border-brand bg-brand-soft text-brand"
                : "border-border bg-surface-2 text-muted hover:text-fg",
            )}
          >
            <IconSpark className="h-3 w-3" /> Why this?
          </button>
        )}
        <button
          onClick={onOpen}
          aria-label="Open details"
          className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-fg"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth={2}>
            <path d="M9 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
      {whyOpen && r.why && (
        <p className="border-t border-border bg-brand-soft/40 px-3 py-2 text-xs text-fg/90">
          <span className="font-semibold text-brand">Why this? </span>
          {r.why}
        </p>
      )}
    </div>
  );
}

// ---- non-resource item row (assessment / project) --------------------------

function ItemRow({
  icon,
  label,
  meta,
  state,
  action,
}: {
  icon: React.ReactNode;
  label: string;
  meta: string;
  state: RoadmapState;
  action?: React.ReactNode;
}) {
  const s = STATE[state];
  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-surface p-2">
      <span
        className={clsx(
          "grid h-6 w-6 shrink-0 place-items-center rounded-md",
          state === "completed"
            ? "bg-success/15 text-success"
            : state === "locked"
              ? "bg-surface-2 text-muted"
              : "bg-brand-soft text-brand",
        )}
      >
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{label}</span>
        <span className="block truncate text-[11px] text-muted">{meta}</span>
      </div>
      {action}
      <span className={clsx("h-1.5 w-1.5 shrink-0 rounded-full", s.rail)} title={STATE_LABEL[state]} />
    </div>
  );
}
