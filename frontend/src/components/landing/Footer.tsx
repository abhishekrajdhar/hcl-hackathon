import Link from "next/link";

/** A status line, not a sitemap. Everything the product actually has. */
export function Footer() {
  return (
    <footer className="relative border-t border-line">
      <div className="mx-auto flex max-w-[1400px] flex-col gap-6 px-6 py-10 md:flex-row md:items-center md:justify-between lg:px-12">
        <div className="flex items-center gap-2.5">
          <span className="relative grid h-5 w-5 place-items-center">
            <span className="absolute inset-0 rounded-full border border-cyan/60" />
            <span className="h-1.5 w-1.5 rounded-full bg-cyan" />
          </span>
          <span className="display text-[13px] font-semibold tracking-tight">PATHWISE</span>
          <span className="label-meta ml-1 text-text-3">v0.1</span>
        </div>

        <div className="flex flex-wrap items-center gap-x-8 gap-y-3">
          <a href="#engine" className="label-meta transition-colors hover:text-cyan">
            Engine
          </a>
          <a href="#pipeline" className="label-meta transition-colors hover:text-cyan">
            Pipeline
          </a>
          <a href="#showcase" className="label-meta transition-colors hover:text-cyan">
            Interface
          </a>
          <Link href="/dashboard" className="label-meta transition-colors hover:text-cyan">
            Launch
          </Link>
        </div>

        <div className="flex items-center gap-2.5">
          <span className="h-1 w-1 animate-pulse rounded-full bg-teal" />
          <span className="label-meta">All systems nominal</span>
        </div>
      </div>
    </footer>
  );
}
