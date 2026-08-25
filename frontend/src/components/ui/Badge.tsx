import { clsx } from "@/lib/cn";

type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "accent";

/**
 * A status tag: hairline outline, uppercase, tracked. Tones map onto the
 * world's colour semantics — `success` is an achievement (amber), `warning`
 * is active learning (cyan), `danger` needs attention (coral).
 */
const tones: Record<Tone, string> = {
  neutral: "border-line-strong text-text-2",
  brand: "border-cyan/40 text-cyan",
  success: "border-amber/40 text-amber",
  warning: "border-cyan/40 text-cyan",
  danger: "border-coral/40 text-coral",
  accent: "border-teal/50 text-teal",
};

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: React.ReactNode;
  tone?: Tone;
  className?: string;
}) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-sm border px-1.5 py-[3px] text-[10px] font-medium uppercase leading-none tracking-[0.1em]",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
