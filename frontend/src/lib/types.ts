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
  /** Actual ÷ estimated effort over completed items; 1.0 until measurable. */
  pace_ratio: number;
  pace_label: "faster" | "on_track" | "slower" | "unknown";
  pace_sample_size: number;
  remaining_estimated_minutes: number;
  /** The remainder re-estimated at this learner's own tempo. */
  remaining_adjusted_minutes: number;
  /** Weeks to finish at the profile's weekly hours; null without a budget. */
  projected_weeks_remaining: number | null;
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

// ---- progress / adaptive / feedback (learner actions) ----------------------

export type ProgressEventType =
  | "started"
  | "progressed"
  | "completed"
  | "skipped"
  | "abandoned";

export interface ProgressEventCreate {
  path_item_id?: UUID;
  resource_id?: UUID;
  event_type: ProgressEventType;
  progress_pct?: number; // 0..100
  time_spent_minutes?: number;
  details?: Record<string, unknown>;
}

export type AdaptiveTrigger =
  | "assessment"
  | "resource_completed"
  | "resource_skipped"
  | "explicit";

export interface ExplicitSkillScore {
  skill_id?: UUID;
  skill_slug?: string;
  score: number; // 0..1
}

/** Exactly one trigger must be set (see backend validator). */
export interface AdaptiveUpdateRequest {
  user_id: UUID;
  assessment_result_id?: UUID;
  completed_resource_id?: UUID;
  skipped_resource_id?: UUID;
  skill_scores?: ExplicitSkillScore[];
  feedback?: string;
  time_spent_minutes?: number;
}

export interface UpdatedSkillRead {
  skill_id: UUID;
  skill_name: string | null;
  previous_proficiency: number;
  new_proficiency: number;
  delta: number;
  mastery_level: string;
  level_band: "advanced" | "intermediate" | "foundational" | "remedial";
}

export interface AdaptiveMilestoneRead {
  skill_id: UUID | null;
  title: string;
  phase_title: string;
  phase_index: number;
}

export interface AdaptiveResourceItemRead {
  resource_id: UUID | null;
  item_id: UUID | null;
  title: string;
  reason: string | null;
}

export interface AdaptiveUpdateResponse {
  user_id: UUID;
  trigger: AdaptiveTrigger;
  updated_skills: UpdatedSkillRead[];
  completed_milestones: AdaptiveMilestoneRead[];
  unlocked_milestones: AdaptiveMilestoneRead[];
  removed_resources: AdaptiveResourceItemRead[];
  newly_recommended_resources: AdaptiveResourceItemRead[];
  next_recommended_action: string;
}

export type FeedbackSignal = "up" | "down" | "too_easy" | "too_hard";

export type FeedbackTargetType =
  | "resource"
  | "path"
  | "path_item"
  | "recommendation"
  | "assessment";

export interface FeedbackCreate {
  target_type: FeedbackTargetType;
  target_id: UUID;
  signal: FeedbackSignal;
  rating?: number; // 1..5
  comment?: string;
}

// ---- skill graph -----------------------------------------------------------

export type RelationshipType =
  | "hard_prerequisite"
  | "soft_prerequisite"
  | "recommended"
  | "related";

export interface SkillSummary {
  id: UUID;
  slug: string;
  name: string;
  difficulty: number;
  category_id: UUID | null;
}

export interface SkillCategoryRead {
  id: UUID;
  slug: string;
  name: string;
}

export interface SkillListItem {
  id: UUID;
  slug: string;
  name: string;
  description: string | null;
  difficulty: number;
  category_id: UUID;
  category: SkillCategoryRead | null;
}

/** A prerequisite edge: `source_skill_id` requires `prerequisite_skill_id`. */
export interface PrerequisiteRead {
  source_skill_id: UUID;
  prerequisite_skill_id: UUID;
  relationship_type: RelationshipType;
  strength: number;
  min_level: number;
  rationale: string | null;
}

export interface SkillGraphNode {
  skill_id: UUID;
  slug: string;
  name: string;
  depth: number;
}

/** GET /skills/{id}/graph — transitive prerequisite closure of one skill. */
export interface SkillGraphResponse {
  root_skill_id: UUID;
  nodes: SkillGraphNode[];
  edges: PrerequisiteRead[];
}

/** GET /skills/{id}/dependencies — full dependency analysis for one skill. */
export interface SkillDependencyAnalysis {
  skill: SkillSummary;
  direct_prerequisites: SkillSummary[];
  all_prerequisites: SkillSummary[];
  total_prerequisites: number;
  max_depth: number;
  critical_path: SkillSummary[];
  critical_path_length: number;
  levels: SkillSummary[][];
  learning_sequence: SkillSummary[];
  unlocks: SkillSummary[];
}
