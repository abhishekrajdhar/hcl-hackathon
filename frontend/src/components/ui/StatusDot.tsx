import { clsx } from "@/lib/cn";
import type { PathItemStatus } from "@/lib/types";

const map: Record<string, { color: string; label: string }> = {
  completed: { color: "bg-success", label: "Completed" },
  in_progress: { color: "bg-accent", label: "In progress" },
  available: { color: "bg-brand", label: "Available" },
  locked: { color: "bg-muted/50", label: "Locked" },
  skipped: { color: "bg-warning", label: "Skipped" },
};

export function StatusDot({ status }: { status: PathItemStatus | string }) {
  const s = map[status] ?? map.locked;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span className={clsx("h-2 w-2 rounded-full", s.color)} />
      {s.label}
    </span>
  );
}
