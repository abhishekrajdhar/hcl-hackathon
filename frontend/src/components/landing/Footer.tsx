import Link from "next/link";

const COLS = [
  { title: "Product", links: ["Features", "How it works", "Showcase", "Pricing"] },
  { title: "Company", links: ["About", "Careers", "Blog", "Contact"] },
  { title: "Resources", links: ["Docs", "Guides", "Changelog", "Status"] },
];

export function Footer() {
  return (
    <footer className="relative border-t border-border bg-surface/40 backdrop-blur">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:grid-cols-2 lg:grid-cols-5 lg:px-6">
        <div className="lg:col-span-2">
          <div className="flex items-center gap-2">
            <span className="grid h-8 w-8 place-items-center rounded-xl bg-gradient-to-br from-brand to-accent text-white">◆</span>
            <span className="text-[15px] font-bold tracking-tight">Pathwise</span>
          </div>
          <p className="mt-3 max-w-xs text-sm text-muted">
            The adaptive learning platform that turns a goal into a roadmap that rewrites itself as you grow.
          </p>
          <Link
            href="/dashboard"
            className="mt-5 inline-flex rounded-xl bg-gradient-to-r from-brand to-accent px-4 py-2 text-sm font-semibold text-white shadow-card transition-transform hover:scale-[1.03]"
          >
            Get started
          </Link>
        </div>

        {COLS.map((c) => (
          <div key={c.title}>
            <h4 className="text-sm font-semibold">{c.title}</h4>
            <ul className="mt-3 space-y-2">
              {c.links.map((l) => (
                <li key={l}>
                  <a href="#" className="text-sm text-muted transition-colors hover:text-fg">
                    {l}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="border-t border-border">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-2 px-4 py-5 text-xs text-muted sm:flex-row lg:px-6">
          <span>© {2026} Pathwise. Crafted for lifelong learners.</span>
          <div className="flex gap-4">
            <a href="#" className="transition-colors hover:text-fg">Privacy</a>
            <a href="#" className="transition-colors hover:text-fg">Terms</a>
            <a href="#" className="transition-colors hover:text-fg">Security</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
