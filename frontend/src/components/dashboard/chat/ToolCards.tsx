"use client";

// Structured cards for assistant tool results. When the coach recommends
// something, we render the tool's real data as a card instead of relying on
// prose. Data shapes mirror backend `chat_tools.py` — the backend is the
// source of truth; nothing here recomputes learner state.

import { Badge } from "@/components/ui/Badge";
import { ProgressBar } from "@/components/ui/ProgressBar";
import {
  IconArrow,
  IconBook,
  IconCheck,
  IconChart,
  IconClock,
  IconFlag,
  IconLayers,
  IconPath,
  IconSpark,
  IconTarget,
} from "@/components/ui/icons";
import { clsx } from "@/lib/cn";
import type {
  ChatRecommendationDatum,
  ChatRoadmapPhaseDatum,
  ChatSearchResultDatum,
  ChatSkillGapDatum,
  ChatUpdatedSkillDatum,
  ToolInvocation,
} from "@/lib/types";

export interface ToolCardActions {
  /** Send a follow-up chat message (e.g. "Why this?"). */
  onAsk: (text: string) => void;
  /** Start a resource — opens its URL when known, else asks the coach. */
  onStart: (title: string) => void;
}

/** Render every tool invocation that has a card representation. */
export function ToolCards({
  tools,
  actions,
}: {
  tools: ToolInvocation[];
  actions: ToolCardActions;
}) {
  const renderable = tools.filter((t) => t.available && hasCard(t));
  if (renderable.length === 0) return null;
  return (
    <div className="mt-2 space-y-2">
      {renderable.map((t, i) => (
        <ToolCard key={`${t.name}-${i}`} tool={t} actions={actions} />
      ))}
    </div>
  );
}

function hasCard(t: ToolInvocation): boolean {
  const d = t.data ?? {};
  switch (t.name) {
    case "get_recommendations":
      return Array.isArray(d.recommendations) && d.recommendations.length > 0;
    case "get_current_learning_path":
      return Array.isArray(d.phases) && d.phases.length > 0;
    case "search_resources":
      return Array.isArray(d.results) && d.results.length > 0;
    case "get_next_action":
      return typeof d.title === "string";
    case "get_skill_gaps":
      return Array.isArray(d.gaps) && d.gaps.length > 0;
    case "get_progress":
      return typeof d.completion_pct === "number";
    case "get_learner_profile":
      return typeof d.goal === "string" || typeof d.target_role === "string";
    case "update_learning_progress":
      return Array.isArray(d.updated_skills);
    default:
      return false;
  }
}

function ToolCard({ tool, actions }: { tool: ToolInvocation; actions: ToolCardActions }) {
  const d = tool.data as Record<string, unknown>;
  switch (tool.name) {
    case "get_recommendations":
      return (
        <RecommendationCards items={d.recommendations as ChatRecommendationDatum[]} actions={actions} />
      );
    case "get_current_learning_path":
      return (
        <RoadmapCard
          title={String(d.title ?? "Your roadmap")}
          phases={d.phases as ChatRoadmapPhaseDatum[]}
          totalHours={Number(d.total_hours ?? 0)}
          feasible={d.feasibility_ok !== false}
        />
      );
    case "search_resources":
      return (
        <ResourceCards
          query={String(d.query ?? "")}
          results={d.results as ChatSearchResultDatum[]}
          actions={actions}
        />
      );
    case "get_next_action":
      return (
        <NextActionCard
          title={String(d.title)}
          kind={String(d.kind ?? "resource")}
          phase={String(d.phase ?? "")}
          milestone={String(d.milestone ?? "")}
          minutes={Number(d.estimated_minutes ?? 0)}
          actions={actions}
        />
      );
    case "get_skill_gaps":
      return <SkillGapsCard gaps={d.gaps as ChatSkillGapDatum[]} />;
    case "get_progress":
      return (
        <ProgressCard
          completed={Number(d.items_completed ?? 0)}
          total={Number(d.items_total ?? 0)}
          pct={Number(d.completion_pct ?? 0)}
          hours={Number(d.total_time_hours ?? 0)}
        />
      );
    case "get_learner_profile":
      return (
        <ProfileCard
          goal={String(d.target_role ?? d.goal ?? "")}
          experience={String(d.experience_level ?? "")}
          weeklyHours={Number(d.weekly_hours ?? 0)}
          skillCount={Number(d.skill_count ?? 0)}
          topSkills={(d.top_skills as { skill: string | null; proficiency: number }[]) ?? []}
        />
      );
    case "update_learning_progress":
      return (
        <AdaptiveCard
          updated={(d.updated_skills as ChatUpdatedSkillDatum[]) ?? []}
          unlocked={(d.unlocked_milestones as string[]) ?? []}
          completed={(d.completed_milestones as string[]) ?? []}
          nextAction={typeof d.next_action === "string" ? d.next_action : null}
        />
      );
    default:
      return null;
  }
}

// ---- shared shell -----------------------------------------------------------

function CardShell({
  icon,
  label,
  children,
  className,
}: {
  icon: React.ReactNode;
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("rounded-xl border border-border bg-surface p-3 shadow-card", className)}>
      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
        <span className="text-brand [&>svg]:h-3.5 [&>svg]:w-3.5">{icon}</span>
        {label}
      </div>
      {children}
    </div>
  );
}

function ActionButton({
  onClick,
  children,
  primary,
}: {
  onClick: () => void;
  children: React.ReactNode;
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx(
        "inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors",
        primary
          ? "bg-brand text-white hover:opacity-90"
          : "border border-border bg-surface-2 text-muted hover:text-fg",
      )}
    >
      {children}
    </button>
  );
}

// ---- recommendation cards ---------------------------------------------------

function RecommendationCards({
  items,
  actions,
}: {
  items: ChatRecommendationDatum[];
  actions: ToolCardActions;
}) {
  return (
    <CardShell icon={<IconSpark />} label="Recommended for you">
      <div className="space-y-2">
        {items.slice(0, 4).map((r, i) => {
          const title = r.title ?? "Untitled resource";
          return (
            <div key={i} className="rounded-lg border border-border bg-surface-2/60 p-2.5">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium text-fg">{title}</p>
                <Badge tone="brand">match {Math.round(r.score * 100)}%</Badge>
              </div>
              {r.reason && <p className="mt-1 text-xs text-muted">{r.reason}</p>}
              <div className="mt-2 flex gap-1.5">
                <ActionButton primary onClick={() => actions.onStart(title)}>
                  Start Learning <IconArrow className="h-3 w-3" />
                </ActionButton>
                <ActionButton onClick={() => actions.onAsk(`Why are you recommending ${title}?`)}>
                  Why this?
                </ActionButton>
              </div>
            </div>
          );
        })}
      </div>
    </CardShell>
  );
}

// ---- roadmap card -----------------------------------------------------------

function RoadmapCard({
  title,
  phases,
  totalHours,
  feasible,
}: {
  title: string;
  phases: ChatRoadmapPhaseDatum[];
  totalHours: number;
  feasible: boolean;
}) {
  return (
    <CardShell icon={<IconPath />} label="Your roadmap">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <p className="text-sm font-semibold text-fg">{title}</p>
        <Badge tone="neutral">
          <IconClock className="h-3 w-3" /> ~{totalHours}h
        </Badge>
        {!feasible && <Badge tone="warning">tight schedule</Badge>}
      </div>
      <ol className="space-y-1.5">
        {phases.map((p, i) => (
          <li key={i} className="flex items-start gap-2 text-xs">
            <span
              className={clsx(
                "mt-0.5 grid h-4.5 w-4.5 shrink-0 place-items-center rounded-full text-[10px] font-semibold",
                p.is_capstone ? "bg-accent/15 text-accent" : "bg-brand-soft text-brand",
              )}
              style={{ height: 18, width: 18 }}
            >
              {p.is_capstone ? <IconFlag className="h-2.5 w-2.5" /> : i + 1}
            </span>
            <span>
              <span className="font-medium text-fg">{p.phase}</span>
              {p.milestones.length > 0 && (
                <span className="text-muted"> — {p.milestones.join(", ")}</span>
              )}
            </span>
          </li>
        ))}
      </ol>
    </CardShell>
  );
}

// ---- resource (search) cards ------------------------------------------------

function ResourceCards({
  query,
  results,
  actions,
}: {
  query: string;
  results: ChatSearchResultDatum[];
  actions: ToolCardActions;
}) {
  return (
    <CardShell icon={<IconBook />} label={query ? `Resources for "${query}"` : "Resources"}>
      <div className="space-y-1.5">
        {results.slice(0, 5).map((r, i) => (
          <div
            key={i}
            className="flex items-center justify-between gap-2 rounded-lg border border-border bg-surface-2/60 px-2.5 py-1.5"
          >
            <div className="min-w-0">
              <p className="truncate text-sm text-fg">{r.title}</p>
              <p className="text-[11px] capitalize text-muted">
                {r.type} · relevance {Math.round(r.similarity * 100)}%
              </p>
            </div>
            <ActionButton primary onClick={() => actions.onStart(r.title)}>
              Start
            </ActionButton>
          </div>
        ))}
      </div>
    </CardShell>
  );
}

// ---- next action card -------------------------------------------------------

function NextActionCard({
  title,
  kind,
  phase,
  milestone,
  minutes,
  actions,
}: {
  title: string;
  kind: string;
  phase: string;
  milestone: string;
  minutes: number;
  actions: ToolCardActions;
}) {
  return (
    <CardShell icon={<IconTarget />} label="Next action">
      <p className="text-sm font-semibold text-fg">{title}</p>
      <p className="mt-0.5 text-xs text-muted">
        <span className="capitalize">{kind}</span>
        {phase && <> · {phase}</>}
        {milestone && <> · {milestone}</>}
        {minutes > 0 && <> · ~{Math.max(1, Math.round(minutes / 60))}h</>}
      </p>
      <div className="mt-2 flex gap-1.5">
        <ActionButton primary onClick={() => actions.onStart(title)}>
          Start Learning <IconArrow className="h-3 w-3" />
        </ActionButton>
        <ActionButton onClick={() => actions.onAsk(`Why is ${title} my next step?`)}>
          Why this?
        </ActionButton>
      </div>
    </CardShell>
  );
}

// ---- skill gaps card --------------------------------------------------------

function SkillGapsCard({ gaps }: { gaps: ChatSkillGapDatum[] }) {
  return (
    <CardShell icon={<IconChart />} label="Skill gaps to close">
      <div className="space-y-2">
        {gaps.slice(0, 6).map((g, i) => (
          <div key={i}>
            <div className="mb-0.5 flex justify-between text-xs">
              <span className="font-medium text-fg">{g.skill}</span>
              <span className="text-muted">
                {Math.round(g.current_level * 100)}% → {Math.round(g.required_level * 100)}%
              </span>
            </div>
            <ProgressBar value={g.current_level} target={g.required_level} />
          </div>
        ))}
      </div>
    </CardShell>
  );
}

// ---- progress card ----------------------------------------------------------

function ProgressCard({
  completed,
  total,
  pct,
  hours,
}: {
  completed: number;
  total: number;
  pct: number;
  hours: number;
}) {
  return (
    <CardShell icon={<IconChart />} label="Your progress">
      <div className="mb-1.5 flex items-baseline justify-between">
        <p className="text-sm text-fg">
          <span className="font-semibold">{completed}</span>
          <span className="text-muted">/{total} items</span>
        </p>
        <p className="text-xs text-muted">{hours}h invested</p>
      </div>
      <ProgressBar value={pct / 100} tone="success" />
      <p className="mt-1 text-right text-[11px] text-muted">{Math.round(pct)}% complete</p>
    </CardShell>
  );
}

// ---- profile card -----------------------------------------------------------

function ProfileCard({
  goal,
  experience,
  weeklyHours,
  skillCount,
  topSkills,
}: {
  goal: string;
  experience: string;
  weeklyHours: number;
  skillCount: number;
  topSkills: { skill: string | null; proficiency: number }[];
}) {
  return (
    <CardShell icon={<IconTarget />} label="Your profile">
      {goal && <p className="text-sm font-semibold capitalize text-fg">{goal}</p>}
      <div className="mt-1 flex flex-wrap gap-1.5">
        {experience && <Badge tone="neutral">{experience}</Badge>}
        {weeklyHours > 0 && <Badge tone="neutral">{weeklyHours}h / week</Badge>}
        <Badge tone="neutral">{skillCount} skills tracked</Badge>
      </div>
      {topSkills.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {topSkills.map(
            (s, i) =>
              s.skill && (
                <span
                  key={i}
                  className="rounded-full bg-brand-soft px-2 py-0.5 text-[11px] text-brand"
                >
                  {s.skill} · {Math.round(s.proficiency * 100)}%
                </span>
              ),
          )}
        </div>
      )}
    </CardShell>
  );
}

// ---- adaptive update card ---------------------------------------------------

function AdaptiveCard({
  updated,
  unlocked,
  completed,
  nextAction,
}: {
  updated: ChatUpdatedSkillDatum[];
  unlocked: string[];
  completed: string[];
  nextAction: string | null;
}) {
  return (
    <CardShell icon={<IconLayers />} label="Path updated">
      {updated.length > 0 && (
        <div className="space-y-1">
          {updated.map((s, i) => (
            <p key={i} className="text-xs text-fg">
              <span className="font-medium">{s.skill}</span>{" "}
              <span className="text-muted">
                {Math.round(s.previous * 100)}% → {Math.round(s.new * 100)}%
              </span>{" "}
              <Badge tone="success">{s.mastery}</Badge>
            </p>
          ))}
        </div>
      )}
      {completed.length > 0 && (
        <p className="mt-1.5 flex items-center gap-1 text-xs text-success">
          <IconCheck className="h-3.5 w-3.5" /> Completed: {completed.join(", ")}
        </p>
      )}
      {unlocked.length > 0 && (
        <p className="mt-1 text-xs text-fg">
          🔓 Unlocked: <span className="text-muted">{unlocked.join(", ")}</span>
        </p>
      )}
      {nextAction && (
        <p className="mt-1.5 rounded-lg bg-brand-soft px-2 py-1 text-xs text-brand">
          Next: {nextAction}
        </p>
      )}
    </CardShell>
  );
}
