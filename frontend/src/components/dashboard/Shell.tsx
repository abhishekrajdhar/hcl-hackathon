"use client";

import { clsx } from "@/lib/cn";
import { Badge } from "@/components/ui/Badge";
import { IconLogout, IconTarget, IconPath, IconChart, IconFlag, IconBook, IconClipboard, IconActivity, IconChat, IconSpark, IconLayers, IconGraph } from "@/components/ui/icons";

const NAV = [
  { id: "overview", label: "Overview", icon: IconTarget },
  { id: "next-action", label: "Next Action", icon: IconSpark },
  { id: "roadmap", label: "Roadmap", icon: IconLayers },
  { id: "path", label: "Learning Path", icon: IconPath },
  { id: "skills", label: "Skill Progress", icon: IconChart },
  { id: "graph", label: "Knowledge Graph", icon: IconGraph },
  { id: "milestones", label: "Milestones", icon: IconFlag },
  { id: "recommendations", label: "Recommended", icon: IconBook },
  { id: "assessments", label: "Assessments", icon: IconClipboard },
  { id: "activity", label: "Activity", icon: IconActivity },
  { id: "assistant", label: "AI Assistant", icon: IconChat },
];

export function Shell({
  children,
  userLabel,
  isDemo,
  theme,
  onToggleTheme,
  onSignOut,
}: {
  children: React.ReactNode;
  userLabel: string;
  isDemo: boolean;
  theme: string;
  onToggleTheme: () => void;
  onSignOut: () => void;
}) {
  return (
    <div className="min-h-screen bg-bg text-fg">
      <div className="mx-auto flex max-w-[1400px] gap-6 px-4 py-6 lg:px-6">
        {/* Sidebar (desktop) */}
        <aside className="sticky top-6 hidden h-[calc(100vh-3rem)] w-56 shrink-0 flex-col rounded-2xl border border-border bg-surface p-4 lg:flex">
          <div className="mb-6 flex items-center gap-2 px-1">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-brand text-white">◆</span>
            <div className="text-sm font-semibold leading-tight">
              Learning<br />Dashboard
            </div>
          </div>
          <nav className="flex-1 space-y-0.5">
            {NAV.map((n) => (
              <a
                key={n.id}
                href={`#${n.id}`}
                className="flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-muted transition-colors hover:bg-surface-2 hover:text-fg"
              >
                <n.icon className="h-4 w-4" />
                {n.label}
              </a>
            ))}
          </nav>
          <button
            onClick={onSignOut}
            className="mt-2 flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-muted hover:bg-surface-2 hover:text-fg"
          >
            <IconLogout className="h-4 w-4" /> Sign out
          </button>
        </aside>

        {/* Main */}
        <main className="min-w-0 flex-1">
          <header className="mb-5 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-muted">Welcome back,</span>
              <span className="text-sm font-semibold">{userLabel}</span>
              {isDemo && <Badge tone="accent">demo data</Badge>}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={onToggleTheme}
                className="rounded-xl border border-border bg-surface px-3 py-1.5 text-xs text-muted hover:text-fg"
                aria-label="Toggle theme"
              >
                {theme === "dark" ? "☾ Dark" : "☀ Light"}
              </button>
            </div>
          </header>
          {children}
        </main>
      </div>
    </div>
  );
}
