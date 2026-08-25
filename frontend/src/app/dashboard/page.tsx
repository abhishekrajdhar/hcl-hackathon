"use client";

import { useState } from "react";
import { Shell } from "@/components/dashboard/Shell";
import { SignIn } from "@/components/dashboard/SignIn";
import { Overview } from "@/components/dashboard/Overview";
import { NextAction } from "@/components/dashboard/NextAction";
import { Roadmap } from "@/components/dashboard/roadmap/Roadmap";
import { LearningPath } from "@/components/dashboard/LearningPath";
import { SkillProgress } from "@/components/dashboard/SkillProgress";
import { KnowledgeGraph } from "@/components/dashboard/graph/KnowledgeGraph";
import { Universe } from "@/components/dashboard/universe/Universe";
import { StatusHud } from "@/components/dashboard/StatusHud";
import { Milestones } from "@/components/dashboard/Milestones";
import { Recommendations } from "@/components/dashboard/Recommendations";
import { Assessments } from "@/components/dashboard/Assessments";
import { LearningActivity } from "@/components/dashboard/LearningActivity";
import { Assistant } from "@/components/dashboard/Assistant";
import { Skeleton } from "@/components/ui/Skeleton";
import { Toaster } from "@/components/ui/Toaster";
import { ToastProvider } from "@/lib/hooks/useToast";
import { ProgressProvider } from "@/lib/progress-context";
import { useAuth } from "@/lib/hooks/useAuth";
import { useDashboardData } from "@/lib/hooks/useDashboardData";

export default function DashboardPage() {
  const { user, ready, signIn, signOut } = useAuth();
  const { data, loading, isDemo, reload, applyAdaptive } = useDashboardData();
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
    <ToastProvider>
      <ProgressProvider
        data={data}
        isDemo={isDemo}
        userId={user?.id ?? null}
        applyAdaptive={applyAdaptive}
        reload={reload}
      >
        <Shell
          userLabel={user?.full_name || user?.email?.split("@")[0] || "Learner"}
          isDemo={isDemo}
          onSignOut={() => {
            signOut();
            setDemoMode(false);
          }}
          hud={<StatusHud data={data} />}
        >
          {/* The world first, full-bleed and edge to edge — the page opens
              inside it rather than scrolling down to find it. */}
          <div id="universe" className="scroll-mt-12">
            <Universe data={data} />
          </div>

          {/* Everything below is the briefing on that world. */}
          <div className="mx-auto max-w-[1400px] space-y-4 px-4 pt-4 lg:px-8 lg:pt-6">
            <div id="overview" className="scroll-mt-16">
              <Overview data={data} />
            </div>
            <div id="next-action" className="scroll-mt-16">
              <NextAction data={data} />
            </div>

            <div id="roadmap" className="scroll-mt-16">
              <Roadmap data={data} />
            </div>

            <div className="grid gap-4 lg:grid-cols-3">
              <div id="path" className="lg:col-span-2 scroll-mt-16">
                <LearningPath data={data} />
              </div>
              <div id="milestones" className="scroll-mt-16">
                <Milestones data={data} />
              </div>
            </div>

            <div id="skills" className="scroll-mt-16">
              <SkillProgress data={data} />
            </div>

            <div id="graph" className="scroll-mt-16">
              <KnowledgeGraph data={data} />
            </div>

            <div id="recommendations" className="scroll-mt-16">
              <Recommendations data={data} />
            </div>

            <div className="grid gap-4 lg:grid-cols-2">
              <div id="assessments" className="scroll-mt-16">
                <Assessments data={data} />
              </div>
              <div id="activity" className="scroll-mt-16">
                <LearningActivity data={data} />
              </div>
            </div>

            <div id="assistant" className="scroll-mt-16">
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
        <Toaster />
      </ProgressProvider>
    </ToastProvider>
  );
}
