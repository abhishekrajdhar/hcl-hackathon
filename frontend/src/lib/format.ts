export const pct = (v: number, digits = 0): string => `${(v * 100).toFixed(digits)}%`;

export const hoursFromMinutes = (m: number): string => {
  const h = m / 60;
  return h >= 1 ? `${h % 1 === 0 ? h : h.toFixed(1)}h` : `${m}m`;
};

export const difficultyLabel = (d: number): string =>
  ["", "Beginner", "Easy", "Intermediate", "Advanced", "Expert"][d] ?? "—";

export const titleCase = (s: string): string =>
  s.replace(/[_-]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export const relativeDate = (iso: string | null): string => {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
};

// Deterministic accent for a skill/category name (stable across renders).
export const hashHue = (s: string): number => {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) % 360;
  return h;
};
