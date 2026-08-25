/**
 * A readout. Deliberately unboxed — nesting a bordered card inside a bordered
 * panel is what makes a dashboard look like a dashboard. Separation comes from
 * the hairline rules of the grid it sits in.
 */
export function Stat({
  label,
  value,
  hint,
  icon,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  icon?: React.ReactNode;
  /** `active` lights the figure cyan; `achievement` lights it amber. */
  tone?: "default" | "active" | "achievement";
}) {
  const valueColor =
    tone === "active" ? "text-cyan" : tone === "achievement" ? "text-amber" : "text-text";
  return (
    <div className="px-4 py-3">
      <div className="flex items-center gap-1.5">
        {icon && <span className="text-text-3">{icon}</span>}
        <span className="label-meta">{label}</span>
      </div>
      <div className={`readout display mt-2 text-[26px] font-semibold leading-none ${valueColor}`}>
        {value}
      </div>
      {hint && <div className="mt-1.5 text-[11px] leading-snug text-text-2">{hint}</div>}
    </div>
  );
}
