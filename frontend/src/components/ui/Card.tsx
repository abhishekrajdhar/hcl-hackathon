import { clsx } from "@/lib/cn";

/**
 * An instrument panel. Not a card: hairline edge, near-square corners, and a
 * translucent graphite ground so the world's light still reads behind it.
 */
export function Card({
  className,
  children,
  bracket = true,
}: {
  className?: string;
  children: React.ReactNode;
  /** Corner brackets. On by default; off for panels nested inside another. */
  bracket?: boolean;
}) {
  return (
    <section className={clsx("hud", bracket && "hud-bracket", className)}>{children}</section>
  );
}

/**
 * Section header. The title is the instrument's name — small, uppercase and
 * tracked — with the human sentence underneath it, so a page of panels scans
 * as a console rather than as a stack of headlines.
 */
export function CardHeader({
  title,
  subtitle,
  icon,
  action,
}: {
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <header className="flex items-start justify-between gap-4 px-5 pb-3 pt-4">
      <div className="flex min-w-0 items-start gap-2.5">
        {icon && <span className="mt-[1px] text-cyan/70">{icon}</span>}
        <div className="min-w-0">
          <h2 className="label-meta text-text-2">{title}</h2>
          {subtitle && (
            <p className="mt-1.5 truncate text-[13px] leading-snug text-text">{subtitle}</p>
          )}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </header>
  );
}

export function CardBody({
  className,
  children,
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <div className={clsx("border-t border-line px-5 py-4", className)}>{children}</div>
  );
}
