import { clsx } from "@/lib/cn";

export function ProgressBar({
  value,
  target,
  tone = "brand",
  className,
}: {
  value: number; // 0..1
  target?: number; // 0..1 marker
  tone?: "brand" | "accent" | "success" | "warning";
  className?: string;
}) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const toneClass = {
    brand: "bg-brand",
    accent: "bg-accent",
    success: "bg-success",
    warning: "bg-warning",
  }[tone];
  return (
    <div className={clsx("relative h-2 w-full rounded-full bg-surface-2", className)}>
      <div
        className={clsx("h-full rounded-full transition-all", toneClass)}
        style={{ width: `${pct}%` }}
      />
      {target !== undefined && (
        <span
          className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 rounded bg-fg/40"
          style={{ left: `${Math.min(100, target * 100)}%` }}
          title={`Target ${(target * 100).toFixed(0)}%`}
        />
      )}
    </div>
  );
}
