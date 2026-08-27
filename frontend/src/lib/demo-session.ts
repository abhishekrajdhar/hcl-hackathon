// The demo is a real account, not a bundled dataset. "Explore the demo" signs
// into the seeded demo learner and renders it through the same live API path
// as any other learner — every number on screen was computed by the backend,
// and the coach on top of it is the real assistant.
//
// The credentials are deliberately public: the account exists to be shared.
// They must match DEMO_LEARNER_EMAIL / DEMO_LEARNER_PASSWORD in the backend
// settings (see `app/db/seed.py`).

export const DEMO_EMAIL = process.env.NEXT_PUBLIC_DEMO_EMAIL || "demo@example.com";
export const DEMO_PASSWORD = process.env.NEXT_PUBLIC_DEMO_PASSWORD || "demo-universe";

/** Whether a signed-in session is the shared demo account. */
export function isDemoEmail(email: string | null | undefined): boolean {
  return (email || "").toLowerCase() === DEMO_EMAIL.toLowerCase();
}
