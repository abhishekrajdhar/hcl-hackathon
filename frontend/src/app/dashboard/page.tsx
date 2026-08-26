"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect } from "react";
import { Shell } from "@/components/dashboard/Shell";
import { Overview } from "@/components/dashboard/Overview";
import { NextAction } from "@/components/dashboard/NextAction";
import { Roadmap } from "@/components/dashboard/roadmap/Roadmap";
import { LearningPath } from "@/components/dashboard/LearningPath";
import { SkillProgress } from "@/components/dashboard/SkillProgress";
import { KnowledgeGraph } from "@/components/dashboard/graph/KnowledgeGraph";
import { Universe } from "@/components/dashboard/universe/Universe";
import { StatusHud } from "@/components/dashboard/StatusHud";
import { DemoBanner, LoadErrorBanner } from "@/components/dashboard/DataBanner";
import { Milestones } from "@/components/dashboard/Milestones";
import { Recommendations } from "@/components/dashboard/Recommendations";
import { Assessments } from "@/components/dashboard/Assessments";
import { Assistant } from "@/components/dashboard/Assistant";
import { SystemStatus } from "@/components/dashboard/SystemStatus";
import { Skeleton } from "@/components/ui/Skeleton";
import { Toaster } from "@/components/ui/Toaster";
import { ToastProvider } from "@/lib/hooks/useToast";
import { ProgressProvider } from "@/lib/progress-context";
import { useAuth } from "@/lib/hooks/useAuth";
import { useDashboardData } from "@/lib/hooks/useDashboardData";

function DashboardView() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, ready, signOut } = useAuth();
  const { data, loading, error, isDemo, needsOnboarding, reload, applyAdaptive } = useDashboardData();
  // ?demo=1 lets the login page hand someone straight into the bundled dataset
  // without an account.
  const demoMode = searchParams.get("demo") === "1";

  // Signing in is its own route, so an unauthenticated visitor is sent there
  // rather than shown a form wearing the dashboard's chrome.
  useEffect(() => {
    if (ready && !user && !demoMode) router.replace("/login");
  }, [ready, user, demoMode, router]);

  // A signed-in learner with no profile has never told us anything about
  // themselves. Send them to onboarding rather than showing a demo journey
  // dressed up as their own.
  useEffect(() => {
    if (ready && user && needsOnboarding && !demoMode) router.replace("/onboarding");
  }, [ready, user, needsOnboarding, demoMode, router]);

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

  // The redirect above is in flight; render nothing rather than a flash of
  // dashboard chrome for someone who is not signed in.
  if (!user && !demoMode) return null;
  if (user && needsOnboarding && !demoMode) return null;

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
            router.replace("/login");
          }}
          hud={<StatusHud data={data} />}
        >
          {error ? (
            <div className="mx-auto max-w-[1400px] px-4 pt-6 lg:px-8">
              <LoadErrorBanner message={error} onRetry={reload} />
            </div>
          ) : (
            <>
              {isDemo && (
                <div className="mx-auto max-w-[1400px] px-4 pt-4 lg:px-8">
                  <DemoBanner />
                </div>
              )}
              {/* The world first, full-bleed and edge to edge — the page opens
                  inside it rather than scrolling down to find it. */}
              <div id="universe" className="scroll-mt-12">
                <Universe data={data} />
              </div>
            </>
          )}

          {/* Everything below is the briefing on that world. */}
          <div
            className={`mx-auto max-w-[1400px] space-y-4 px-4 pt-4 lg:px-8 lg:pt-6 ${
              error ? "hidden" : ""
            }`}
          >
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

            <div id="assessments" className="scroll-mt-16">
              <Assessments data={data} />
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

            <div id="system" className="scroll-mt-16">
              <SystemStatus />
            </div>

            {loading && <p className="py-2 text-center text-xs text-muted">Refreshing your data…</p>}
          </div>
        </Shell>
        <Toaster />
      </ProgressProvider>
    </ToastProvider>
  );
}

/**
 * `useSearchParams` (used for ?demo=1) opts the tree out of static rendering,
 * so the view sits behind a Suspense boundary and the route still prerenders
 * its shell.
 */
export default function DashboardPage() {
  return (
    <Suspense fallback={<DashboardBoot />}>
      <DashboardView />
    </Suspense>
  );
}

function DashboardBoot() {
  return (
    <div className="grid min-h-screen place-items-center bg-void">
      <p className="label-meta animate-pulse">Initialising universe…</p>
    </div>
  );
}
