// Bundled demo knowledge graph, so the tab is meaningful before/without a
// seeded backend account. The structure is a faithful subset of the real
// seeded skill graph (`backend/app/db/seeds/skill_graph.py`) and the
// proficiencies match the rest of the demo dashboard, so demo and live mode
// exercise identical rendering code.

import type { EdgeKind, GraphEdge, GraphModel, GraphNode } from "@/lib/graph-view";
import { masteryState } from "@/lib/graph-view";

interface Seed {
  slug: string;
  name: string;
  category: string;
  difficulty: number;
  /** null = no record at all, painted "not started". */
  proficiency: number | null;
  required: number | null;
}

const SEEDS: Seed[] = [
  { slug: "programming-fundamentals", name: "Programming Fundamentals", category: "Programming", difficulty: 1, proficiency: 0.95, required: null },
  { slug: "python", name: "Python", category: "Programming", difficulty: 1, proficiency: 0.9, required: 0.9 },
  { slug: "linear-algebra", name: "Linear Algebra", category: "Mathematics", difficulty: 3, proficiency: 0.82, required: null },
  { slug: "calculus", name: "Calculus", category: "Mathematics", difficulty: 3, proficiency: 0.55, required: null },
  { slug: "probability", name: "Probability", category: "Statistics", difficulty: 3, proficiency: 0.7, required: null },
  { slug: "statistics", name: "Statistics", category: "Statistics", difficulty: 3, proficiency: 0.65, required: 0.8 },
  { slug: "data-wrangling", name: "Data Wrangling", category: "Data Engineering", difficulty: 2, proficiency: 0.72, required: null },
  { slug: "optimization", name: "Optimization", category: "Mathematics", difficulty: 4, proficiency: 0.3, required: null },
  { slug: "machine-learning", name: "Machine Learning", category: "Machine Learning", difficulty: 3, proficiency: 0.75, required: 0.85 },
  { slug: "supervised-learning", name: "Supervised Learning", category: "Machine Learning", difficulty: 3, proficiency: 0.6, required: null },
  { slug: "unsupervised-learning", name: "Unsupervised Learning", category: "Machine Learning", difficulty: 3, proficiency: 0.45, required: null },
  { slug: "model-evaluation", name: "Model Evaluation", category: "Machine Learning", difficulty: 3, proficiency: 0.48, required: null },
  { slug: "neural-networks", name: "Neural Networks", category: "Deep Learning", difficulty: 4, proficiency: 0.38, required: null },
  { slug: "pytorch", name: "PyTorch", category: "Deep Learning", difficulty: 3, proficiency: 0.31, required: 0.7 },
  { slug: "deep-learning", name: "Deep Learning", category: "Deep Learning", difficulty: 4, proficiency: 0.42, required: 0.8 },
  { slug: "cnn", name: "CNN", category: "Deep Learning", difficulty: 4, proficiency: null, required: 0.7 },
  { slug: "rnn", name: "RNN", category: "Deep Learning", difficulty: 4, proficiency: null, required: null },
  { slug: "transformers", name: "Transformers", category: "Deep Learning", difficulty: 5, proficiency: null, required: null },
  { slug: "image-processing", name: "Image Processing", category: "Computer Vision", difficulty: 2, proficiency: null, required: null },
  { slug: "computer-vision", name: "Computer Vision", category: "Computer Vision", difficulty: 4, proficiency: null, required: null },
  { slug: "nlp-fundamentals", name: "NLP Fundamentals", category: "NLP", difficulty: 3, proficiency: null, required: null },
  { slug: "word-embeddings", name: "Word Embeddings", category: "NLP", difficulty: 3, proficiency: null, required: null },
  { slug: "language-models", name: "Language Models", category: "NLP", difficulty: 5, proficiency: null, required: null },
  { slug: "generative-ai", name: "Generative AI", category: "Generative AI", difficulty: 5, proficiency: null, required: null },
  { slug: "large-language-models", name: "Large Language Models", category: "Generative AI", difficulty: 5, proficiency: null, required: null },
];

/** Slugs the demo goal ("Machine Learning Engineer") asks for directly. */
const TARGETS = new Set(["statistics", "machine-learning", "deep-learning", "pytorch", "cnn"]);

/** [dependent, prerequisite, kind] — mirrors the seeded EDGES exactly. */
const EDGES: [string, string, EdgeKind][] = [
  ["python", "programming-fundamentals", "hard_prerequisite"],
  ["optimization", "calculus", "hard_prerequisite"],
  ["optimization", "linear-algebra", "hard_prerequisite"],
  ["statistics", "probability", "hard_prerequisite"],
  ["probability", "calculus", "soft_prerequisite"],
  ["data-wrangling", "python", "hard_prerequisite"],
  ["machine-learning", "python", "hard_prerequisite"],
  ["machine-learning", "linear-algebra", "hard_prerequisite"],
  ["machine-learning", "statistics", "hard_prerequisite"],
  ["machine-learning", "calculus", "soft_prerequisite"],
  ["machine-learning", "data-wrangling", "recommended"],
  ["supervised-learning", "machine-learning", "hard_prerequisite"],
  ["unsupervised-learning", "machine-learning", "hard_prerequisite"],
  ["model-evaluation", "machine-learning", "hard_prerequisite"],
  ["neural-networks", "machine-learning", "hard_prerequisite"],
  ["neural-networks", "linear-algebra", "hard_prerequisite"],
  ["neural-networks", "optimization", "soft_prerequisite"],
  ["pytorch", "python", "hard_prerequisite"],
  ["pytorch", "neural-networks", "soft_prerequisite"],
  ["deep-learning", "neural-networks", "hard_prerequisite"],
  ["deep-learning", "pytorch", "soft_prerequisite"],
  ["cnn", "deep-learning", "hard_prerequisite"],
  ["rnn", "deep-learning", "hard_prerequisite"],
  ["transformers", "deep-learning", "hard_prerequisite"],
  ["transformers", "rnn", "soft_prerequisite"],
  ["nlp-fundamentals", "machine-learning", "hard_prerequisite"],
  ["nlp-fundamentals", "python", "hard_prerequisite"],
  ["word-embeddings", "nlp-fundamentals", "hard_prerequisite"],
  ["word-embeddings", "neural-networks", "soft_prerequisite"],
  ["language-models", "nlp-fundamentals", "hard_prerequisite"],
  ["language-models", "transformers", "hard_prerequisite"],
  ["language-models", "word-embeddings", "soft_prerequisite"],
  ["image-processing", "python", "hard_prerequisite"],
  ["computer-vision", "image-processing", "hard_prerequisite"],
  ["computer-vision", "cnn", "hard_prerequisite"],
  ["generative-ai", "deep-learning", "hard_prerequisite"],
  ["large-language-models", "transformers", "hard_prerequisite"],
  ["large-language-models", "language-models", "hard_prerequisite"],
  ["large-language-models", "generative-ai", "soft_prerequisite"],
];

const nodes: GraphNode[] = SEEDS.map((s) => ({
  id: s.slug, // demo ids are slugs; live ids are UUIDs. Nothing depends on the form.
  slug: s.slug,
  name: s.name,
  difficulty: s.difficulty,
  category: s.category,
  isTarget: TARGETS.has(s.slug),
  proficiency: s.proficiency,
  required: s.required,
  state: masteryState(s.proficiency, s.required),
}));

const edges: GraphEdge[] = EDGES.map(([dependent, prerequisite, kind]) => ({
  prerequisiteId: prerequisite,
  dependentId: dependent,
  kind,
  strength: kind === "hard_prerequisite" ? 1 : 0.5,
  rationale: null,
}));

export const demoGraph: GraphModel = {
  goal: "Become a Machine Learning Engineer",
  nodes,
  edges,
};
