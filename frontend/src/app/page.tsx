"use client";

import { useState } from "react";
import { Shell } from "@/components/dashboard/Shell";
import { SignIn } from "@/components/dashboard/SignIn";
import { Overview } from "@/components/dashboard/Overview";
import { NextAction } from "@/components/dashboard/NextAction";
import { Roadmap } from "@/components/dashboard/roadmap/Roadmap";
import { LearningPath } from "@/components/dashboard/LearningPath";
import { SkillProgress } from "@/components/dashboard/SkillProgress";
import { Milestones } from "@/components/dashboard/Milestones";
import { Recommendations } from "@/components/dashboard/Recommendations";
import { Assessments } from "@/components/dashboard/Assessments";
import { LearningActivity } from "@/components/dashboard/LearningActivity";
import { Assistant } from "@/components/dashboard/Assistant";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAuth } from "@/lib/hooks/useAuth";
import { useTheme } from "@/lib/hooks/useTheme";
import { useDashboardData } from "@/lib/hooks/useDashboardData";

export default function DashboardPage() {
  const { user, ready, signIn, signOut } = useAuth();
  const { theme, toggle } = useTheme();
  const { data, loading, isDemo, reload } = useDashboardData();
  const [demoMode, setDemoMode] = useState(false);

  if (!ready) {
    return (
      <div className="min-h-screen bg-bg p-6">
        <div className="mx-auto max-w-[1400px] space-y-4">
          <Skeleton className="h-40 w-full" />
          <div className="grid gap-4 lg:grid-cols-3">
            <Skeleton className="h-72 lg:col-span-2" />
            <Skeleton className="h-72" />
          </div>
        </div>
      </div>
    );
  }

  if (!user && !demoMode) {
    return (
      <SignIn
        onSignIn={async (e, p) => {
          await signIn(e, p);
          reload();
        }}
        onDemo={() => setDemoMode(true)}
      />
    );
  }

  return (
    <Shell
      userLabel={user?.full_name || user?.email?.split("@")[0] || "Learner"}
      isDemo={isDemo}
      theme={theme}
      onToggleTheme={toggle}
      onSignOut={() => {
        signOut();
        setDemoMode(false);
      }}
    >
      <div className="space-y-5">
        <div id="overview">
          <Overview data={data} />
        </div>
        <div id="next-action">
          <NextAction data={data} />
        </div>

        <div id="roadmap" className="scroll-mt-6">
          <Roadmap data={data} />
        </div>

        <div className="grid gap-5 lg:grid-cols-3">
          <div id="path" className="lg:col-span-2 scroll-mt-6">
            <LearningPath data={data} />
          </div>
          <div id="milestones" className="scroll-mt-6">
            <Milestones data={data} />
          </div>
        </div>

        <div id="skills" className="scroll-mt-6">
          <SkillProgress data={data} />
        </div>

        <div id="recommendations" className="scroll-mt-6">
          <Recommendations data={data} />
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <div id="assessments" className="scroll-mt-6">
            <Assessments data={data} />
          </div>
          <div id="activity" className="scroll-mt-6">
            <LearningActivity data={data} />
          </div>
        </div>

        <div id="assistant" className="scroll-mt-6">
          <Assistant
            resolveResourceUrl={(title) => {
              const t = title.toLowerCase();
              const hit = data.recommendations.find(
                (r) => r.title.toLowerCase() === t || r.title.toLowerCase().includes(t) || t.includes(r.title.toLowerCase()),
              );
              return hit?.url ?? null;
            }}
          />
        </div>

        {loading && <p className="py-2 text-center text-xs text-muted">Refreshing your data…</p>}
      </div>
    </Shell>
  );
}
