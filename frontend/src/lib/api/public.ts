import type { SkillGraphResponse, SkillListItem } from "@/lib/types";
import { request } from "./client";

/** The demo learner's universe, served without authentication so the landing
 * page can render the real galaxy for a signed-out visitor. */
export interface DemoUniverse {
  available: boolean;
  goal: string | null;
  catalogue: SkillListItem[];
  graph: SkillGraphResponse | null;
  proficiencies: { slug: string; current: number; target: number | null }[];
  target_slugs: string[];
}

export function getDemoUniverse(): Promise<DemoUniverse> {
  return request<DemoUniverse>("/public/demo/universe");
}
