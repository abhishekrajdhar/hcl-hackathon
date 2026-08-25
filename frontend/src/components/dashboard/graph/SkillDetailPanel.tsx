"use client";

import { useEffect, useMemo, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { IconArrow, IconCheck, IconLock, IconSpark, IconTarget } from "@/components/ui/icons";
import { getToken, graphApi } from "@/lib/api";
import { clsx } from "@/lib/cn";
import { difficultyLabel, pct } from "@/lib/format";
import {
  STATE_COLOR,
  STATE_LABEL,
  directDependents,
  directPrerequisites,
  edgeBetween,
  masteryState,
  transitive,
  type GraphModel,
  type GraphNode,
  type MasteryState,
} from "@/lib/graph-view";
import type { GraphProficiency } from "@/lib/graph-derive";

const TONE: Record<MasteryState, "success" | "warning" | "danger" | "neutral"> = {
  mastered: "success",
  learning: "warning",
  weak: "danger",
  not_started: "neutral",
};

/**
 * Answers the three questions a learner actually has about a node they clicked.
 * Every answer is read off the graph or the API — where there is no evidence
 * the panel says so rather than filling the gap.
 */
export function SkillDetailPanel({
  skill,
  model,
  proficiencies,
  isDemo,
  onSelect,
}: {
  skill: GraphNode | null;
  model: GraphModel;
  /**
   * The learner's full proficiency list. Skills the API reports as unlocked may
   * sit outside the drawn graph, and their state has to come from here — the
   * panel must not assume "not started" for a skill it simply hasn't drawn.
   */
  proficiencies: GraphProficiency[];
  isDemo: boolean;
  onSelect: (id: string) => void;
}) {
  // The graph only holds the part of the catalogue on this learner's route, so
  // "what does this unlock" is asked of the backend, which sees all of it.
  const [wider, setWider] = useState<GraphNode[] | null>(null);

  const bySlug = useMemo(
    () => new Map(proficiencies.map((p) => [p.slug, p])),
    [proficiencies],
  );

  useEffect(() => {
    setWider(null);
    if (!skill || isDemo || !getToken()) return;
    let cancelled = false;
    graphApi
      .getSkillDependencies(skill.id)
      .then((d) => {
        if (cancelled) return;
        setWider(
          d.unlocks.map((u) => {
            // A skill can be unlocked-but-already-learned. Only a skill with no
            // record at all is genuinely "not started".
            const tracked = bySlug.get(u.slug);
            const proficiency = tracked ? tracked.current : null;
            const required = tracked ? tracked.target : null;
            return {
              id: u.id,
              slug: u.slug,
              name: u.name,
              difficulty: u.difficulty,
              category: null,
              isTarget: false,
              proficiency,
              required,
              state: masteryState(proficiency, required),
            };
          }),
        );
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [skill, isDemo, bySlug]);

  if (!skill) {
    return (
      <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border p-6 text-center">
        <IconSpark className="h-5 w-5 text-muted" />
        <p className="text-sm font-medium">Pick a skill</p>
        <p className="max-w-[220px] text-xs text-muted">
          Click any node to see why it is on your path, what it needs first, and what it opens up.
        </p>
      </div>
    );
  }

  const prereqs = directPrerequisites(skill.id, model);
  const unlocksHere = directDependents(skill.id, model);
  const unlocks = mergeUnlocks(unlocksHere, wider);
  const blocking = prereqs.filter((p) => p.state !== "mastered");

  return (
    <div className="flex h-full flex-col gap-4 rounded-xl border border-border bg-surface p-4">
      <header>
        <div className="flex items-start justify-between gap-2">
          <h3 className="text-sm font-semibold leading-tight">{skill.name}</h3>
          <Badge tone={TONE[skill.state]}>{STATE_LABEL[skill.state]}</Badge>
        </div>
        <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted">
          {skill.category && <span>{skill.category}</span>}
          {skill.difficulty > 0 && <span>· {difficultyLabel(skill.difficulty)}</span>}
          {skill.isTarget && <Badge tone="brand">goal skill</Badge>}
        </p>
        {skill.proficiency != null && (
          <div className="mt-2">
            <div className="flex items-center justify-between text-[11px] text-muted">
              <span>{pct(skill.proficiency)} now</span>
              {skill.required != null && skill.required > 0 && <span>{pct(skill.required)} needed</span>}
            </div>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-2">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Math.min(100, skill.proficiency * 100)}%`,
                  background: STATE_COLOR[skill.state],
                }}
              />
            </div>
          </div>
        )}
      </header>

      <Question icon={<IconTarget className="h-3.5 w-3.5" />} title="Why do I need this?">
        <WhyText skill={skill} model={model} />
      </Question>

      <Question icon={<IconLock className="h-3.5 w-3.5" />} title="What do I need before this?">
        {prereqs.length === 0 ? (
          <p className="text-xs text-muted">
            Nothing — this is a starting point, you can begin it today.
          </p>
        ) : (
          <>
            <SkillChips skills={prereqs} model={model} onSelect={onSelect} showEdgeTo={skill.id} />
            <p className="mt-2 text-[11px] text-muted">
              {blocking.length === 0 ? (
                <span className="text-success">All prerequisites met — you are ready for this.</span>
              ) : (
                `${blocking.length} of ${prereqs.length} still below mastery.`
              )}
            </p>
          </>
        )}
      </Question>

      <Question
        icon={<IconArrow className="h-3.5 w-3.5" />}
        title="What can I build after learning this?"
      >
        {unlocks.length === 0 ? (
          <p className="text-xs text-muted">
            Nothing further in the catalogue depends on this one — it is an end point of your graph.
          </p>
        ) : (
          <SkillChips skills={unlocks} model={model} onSelect={onSelect} />
        )}
      </Question>
    </div>
  );
}

/**
 * The "why" is derived, never invented: either the goal names this skill, or it
 * is on the route to skills the goal names. The backend's edge rationale is
 * quoted when it has one.
 */
function WhyText({ skill, model }: { skill: GraphNode; model: GraphModel }) {
  const downstream = transitive(skill.id, model, "down");
  const servedTargets = model.nodes.filter((n) => n.isTarget && downstream.has(n.id));
  const rationales = model.edges
    .filter((e) => e.prerequisiteId === skill.id && e.rationale)
    .map((e) => e.rationale as string);

  if (skill.isTarget) {
    return (
      <div className="space-y-1.5 text-xs text-muted">
        <p>
          <span className="text-fg">Your goal asks for this skill directly.</span>{" "}
          {skill.required != null && skill.required > 0 && skill.proficiency != null
            ? `It needs ${pct(skill.required)} and you are at ${pct(skill.proficiency)}.`
            : "It is one of the skills your path is built around."}
        </p>
        {servedTargets.length > 0 && (
          <p>It also feeds {servedTargets.length} further goal skill{servedTargets.length > 1 ? "s" : ""}.</p>
        )}
      </div>
    );
  }

  if (servedTargets.length === 0) {
    return (
      <p className="text-xs text-muted">
        Nothing on your current path depends on this — it is here as context for the skills around it.
      </p>
    );
  }

  return (
    <div className="space-y-1.5 text-xs text-muted">
      <p>
        It stands between you and{" "}
        <span className="text-fg">
          {servedTargets
            .slice(0, 3)
            .map((t) => t.name)
            .join(", ")}
        </span>
        {servedTargets.length > 3 && ` and ${servedTargets.length - 3} more`} on your path.
      </p>
      {rationales.length > 0 && <p className="italic">“{rationales[0]}”</p>}
    </div>
  );
}

function Question({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section>
      <h4 className="mb-1.5 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted">
        {icon}
        {title}
      </h4>
      {children}
    </section>
  );
}

function SkillChips({
  skills,
  model,
  onSelect,
  showEdgeTo,
}: {
  skills: GraphNode[];
  model: GraphModel;
  onSelect: (id: string) => void;
  /** When set, marks which chips are hard prerequisites of that skill. */
  showEdgeTo?: string;
}) {
  const known = new Set(model.nodes.map((n) => n.id));
  return (
    <ul className="flex flex-wrap gap-1.5">
      {skills.map((s) => {
        const edge = showEdgeTo ? edgeBetween(s.id, showEdgeTo, model) : null;
        const optional = edge != null && edge.kind !== "hard_prerequisite";
        const clickable = known.has(s.id);
        return (
          <li key={s.id}>
            <button
              type="button"
              disabled={!clickable}
              onClick={() => clickable && onSelect(s.id)}
              title={clickable ? `Show ${s.name}` : `${s.name} is outside your current path`}
              className={clsx(
                "flex items-center gap-1.5 rounded-lg border border-border px-2 py-1 text-[11px] transition-colors",
                clickable ? "hover:border-brand hover:text-brand" : "cursor-default opacity-70",
              )}
            >
              <span
                className="h-2 w-2 shrink-0 rounded-full"
                style={{ background: STATE_COLOR[s.state] }}
              />
              {s.name}
              {s.state === "mastered" && <IconCheck className="h-3 w-3 text-success" />}
              {optional && <span className="text-muted">(helpful)</span>}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

/** Graph dependents first (they carry real state), then anything only the API knew about. */
function mergeUnlocks(local: GraphNode[], wider: GraphNode[] | null): GraphNode[] {
  if (!wider) return local;
  const seen = new Set(local.map((n) => n.id));
  return [...local, ...wider.filter((n) => !seen.has(n.id))];
}
