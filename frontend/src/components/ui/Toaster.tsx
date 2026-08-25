"use client";

import { useEffect, useState } from "react";
import { IconCheck, IconSpark } from "@/components/ui/icons";
import { clsx } from "@/lib/cn";
import { useToast, type Toast } from "@/lib/hooks/useToast";
import type { SkillDelta } from "@/lib/adaptive";

/** Bottom-right notification stack. Mount once near the app root. */
export function Toaster() {
  const { toasts, dismiss } = useToast();
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:inset-x-auto sm:right-4 sm:items-end">
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onClose={() => dismiss(t.id)} />
      ))}
    </div>
  );
}

function ToastCard({ toast, onClose }: { toast: Toast; onClose: () => void }) {
  return (
    <div className="animate-in pointer-events-auto w-full max-w-sm overflow-hidden rounded-2xl border border-border bg-surface shadow-card">
      <div className="flex items-start gap-3 p-3.5">
        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-brand-soft text-brand">
          <IconSpark className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">{toast.title}</p>
          {toast.body && <p className="mt-0.5 text-xs leading-relaxed text-muted">{toast.body}</p>}
          {toast.deltas && toast.deltas.length > 0 && (
            <div className="mt-2 space-y-2">
              {toast.deltas.map((d) => (
                <DeltaBar key={d.name} delta={d} />
              ))}
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          aria-label="Dismiss"
          className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-fg"
        >
          ✕
        </button>
      </div>
      <div className="h-px w-full bg-cyan/70" />
    </div>
  );
}

/** A skill bar that animates from its "before" width to "after" on mount. */
function DeltaBar({ delta }: { delta: SkillDelta }) {
  const [w, setW] = useState(delta.before);
  useEffect(() => {
    const id = window.setTimeout(() => setW(delta.after), 120);
    return () => window.clearTimeout(id);
  }, [delta.after]);
  const improved = delta.after > delta.before;
  return (
    <div>
      <div className="mb-0.5 flex items-center justify-between text-[11px]">
        <span className="font-medium">{delta.name}</span>
        <span className={clsx("inline-flex items-center gap-1", improved ? "text-success" : "text-muted")}>
          {improved && <IconCheck className="h-3 w-3" />}
          {Math.round(delta.before * 100)}% → {Math.round(delta.after * 100)}%
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface-2">
        <div
          className={clsx("h-full rounded-full transition-[width] duration-700 ease-out", improved ? "bg-success" : "bg-brand")}
          style={{ width: `${Math.max(0, Math.min(1, w)) * 100}%` }}
        />
      </div>
    </div>
  );
}
