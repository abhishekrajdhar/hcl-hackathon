// Types mirroring the FastAPI backend response schemas (see /openapi.json).

export type UUID = string;

export interface User {
  id: UUID;
  email: string;
  full_name: string | null;
  role: "learner" | "admin";
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface SkillRef {
  id: UUID;
  slug: string;
  name: string;
}

export interface SkillProficiency {
  skill_id: UUID;
  proficiency: number; // 0..1
  confidence: number;
  evidence_source: string;
  target_proficiency: number | null;
  last_practiced_at: string | null;
  updated_at: string;
  skill: SkillRef | null;
}

export interface AssessmentHistoryItem {
  id: UUID;
  assessment_id: UUID;
  score: number;
  max_score: number;
  percentage: number;
  passed: boolean;
  submitted_at: string | null;
}

export interface AssessmentHistorySummary {
  total_attempts: number;
  passed_attempts: number;
  average_percentage: number;
  last_attempt_at: string | null;
  recent: AssessmentHistoryItem[];
}

export interface LearnerProfile {
  id: UUID;
  user_id: UUID;
  goal_text_raw: string | null;
  target_role: string | null;
  experience_level: string;
  weekly_hours: number;
  target_deadline: string | null;
  preferred_modalities: string[];
  interests: string[];
  version: number;
}

export interface FullLearnerProfile {
  profile: LearnerProfile;
  skills: SkillProficiency[];
  skill_count: number;
  assessment_history: AssessmentHistorySummary;
}

export type PathItemStatus =
  | "locked"
  | "available"
  | "in_progress"
  | "completed"
  | "skipped";

export interface RoadmapItem {
  id: UUID;
  kind: string; // resource | assessment | project | review
  title: string;
  status: PathItemStatus;
  estimated_minutes: number;
  resource_id: UUID | null;
  assessment_id: UUID | null;
  is_optional: boolean;
}

export interface RoadmapMilestone {
  skill_id: UUID | null;
  skill_slug: string | null;
  title: string;
  current_level: number;
  required_level: number;
  gap: number;
  prerequisites: string[];
  completion_criteria: string;
  estimated_minutes: number;
  resources: RoadmapItem[];
  assessment: RoadmapItem | null;
  project: RoadmapItem | null;
}

export interface RoadmapPhase {
  index: number;
  title: string;
  objective: string;
  is_capstone: boolean;
  estimated_minutes: number;
  planned_start: string | null;
  planned_end: string | null;
  milestones: RoadmapMilestone[];
}

export interface LearningPathRoadmap {
  path_id: UUID;
  user_id: UUID;
  goal_id: UUID | null;
  title: string;
  version: number;
  status: string;
  total_estimated_minutes: number;
  planned_start: string | null;
  planned_end: string | null;
  feasibility_ok: boolean;
  feasibility_warning: string | null;
  suggestions: string[];
  phases: RoadmapPhase[];
}

export interface ResourceSkillLink {
  skill_id: UUID;
  skill: SkillRef | null;
}

export interface Resource {
  id: UUID;
  provider: string;
  title: string;
  description: string | null;
  url: string;
  resource_type: string;
  modality: string;
  difficulty: number; // 1..5
  estimated_hours: number;
  quality_score: number | null;
  rating: number | null;
  skills: ResourceSkillLink[];
}

export interface RecommendationItem {
  resource: Resource;
  score: number;
  rank: number;
  is_ready: boolean;
  factors: Record<string, number>;
  contributions: Record<string, number>;
  matched_skills: SkillRef[];
  unmet_prerequisites: SkillRef[];
  reason: string;
}

export interface RecommendationResponse {
  user_id: UUID;
  goal_id: UUID | null;
  count: number;
  excluded_unready: number;
  weights: Record<string, number>;
  recommendations: RecommendationItem[];
}

export interface ProgressSummary {
  user_id: UUID;
  total_events: number;
  items_started: number;
  items_completed: number;
  total_time_minutes: number;
  active_path_id: UUID | null;
  active_path_total_items: number;
  active_path_completed_items: number;
  completion_pct: number;
  last_activity_at: string | null;
}

export interface ProgressEvent {
  id: UUID;
  event_type: string;
  progress_pct: number;
  time_spent_minutes: number;
  occurred_at: string;
}

export interface ToolInvocation {
  name: string;
  available: boolean;
  summary: string;
  data: Record<string, unknown>;
}

export interface ChatResponse {
  conversation_id: UUID;
  reply: string;
  intent: string;
  tools_used: ToolInvocation[];
  source: "llm" | "template";
}

export interface ChatMessageRead {
  id: UUID;
  role: string;
  content: string;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface ConversationRead {
  id: UUID;
  title: string | null;
  created_at: string;
}

export interface ConversationDetail extends ConversationRead {
  messages: ChatMessageRead[];
}

// ---- Shapes of `ToolInvocation.data` per tool (see backend chat_tools.py) ----

export interface ChatRecommendationDatum {
  title: string | null;
  score: number;
  reason: string;
}

export interface ChatRoadmapPhaseDatum {
  phase: string;
  is_capstone: boolean;
  milestones: string[];
}

export interface ChatSkillGapDatum {
  skill: string;
  current_level: number;
  required_level: number;
  gap: number;
}

export interface ChatSearchResultDatum {
  title: string;
  type: string;
  similarity: number;
}

export interface ChatUpdatedSkillDatum {
  skill: string;
  previous: number;
  new: number;
  mastery: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
