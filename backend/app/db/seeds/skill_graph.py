"""Declarative seed data for the skill knowledge graph.

Pure data — no I/O. `seed.py` reads these definitions and upserts them. Edges
reference skills by slug; the loader resolves slugs to ids and refuses to write
an edge that would create a cycle, so this file cannot corrupt the DAG even if
it is edited carelessly.

difficulty: 1 (introductory) .. 5 (expert), intrinsic to the skill.
relationship_type: hard_prerequisite | soft_prerequisite | recommended | related
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CategorySeed:
    slug: str
    name: str
    description: str
    display_order: int


@dataclass(frozen=True)
class SkillSeed:
    slug: str
    name: str
    category: str  # category slug
    difficulty: int
    description: str
    aliases: tuple[str, ...] = ()
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeSeed:
    source: str  # slug of the skill that has the prerequisite
    prerequisite: str  # slug of the required skill
    relationship_type: str = "hard_prerequisite"
    strength: float = 1.0
    min_level: float = 1.0


CATEGORIES: tuple[CategorySeed, ...] = (
    CategorySeed("programming", "Programming", "Software development foundations and languages", 1),
    CategorySeed("mathematics", "Mathematics", "Mathematical foundations for computing and ML", 2),
    CategorySeed("statistics", "Statistics", "Probability, inference and statistical reasoning", 3),
    CategorySeed("data-engineering", "Data Engineering", "Data storage, pipelines and processing", 4),
    CategorySeed("machine-learning", "Machine Learning", "Classical ML theory and practice", 5),
    CategorySeed("deep-learning", "Deep Learning", "Neural networks and their architectures", 6),
    CategorySeed("nlp", "Natural Language Processing", "Language understanding and generation", 7),
    CategorySeed("computer-vision", "Computer Vision", "Image and video understanding", 8),
    CategorySeed("generative-ai", "Generative AI", "LLMs, diffusion and generative systems", 9),
    CategorySeed("mlops", "MLOps", "Deploying, serving and operating ML systems", 10),
    CategorySeed("design", "Design", "Interface, interaction and visual design", 11),
    CategorySeed("game-development", "Game Development", "Engines, graphics and game design", 12),
)


SKILLS: tuple[SkillSeed, ...] = (
    # --- programming ---
    SkillSeed("programming-fundamentals", "Programming Fundamentals", "programming", 1,
              "Variables, control flow, functions and basic data structures.",
              ("coding basics", "intro to programming")),
    SkillSeed("python", "Python", "programming", 1,
              "General-purpose Python: syntax, standard library, idioms.", ("python3",)),
    SkillSeed("data-structures-algorithms", "Data Structures & Algorithms", "programming", 3,
              "Core data structures, complexity analysis and algorithm design.", ("dsa", "algorithms")),
    SkillSeed("sql", "SQL", "programming", 2,
              "Relational querying: joins, aggregation, subqueries.", ("structured query language",)),
    SkillSeed("version-control-git", "Version Control (Git)", "programming", 1,
              "Branching, merging and collaborative workflows with Git.", ("git",)),
    SkillSeed("shell-scripting", "Shell & CLI", "programming", 2,
              "Unix shell, scripting and command-line tooling.", ("bash", "linux cli")),
    SkillSeed("operating-systems", "Operating Systems", "programming", 3,
              "Processes, threads, scheduling, memory and file systems.",
              ("os", "operating system")),
    SkillSeed("computer-networks", "Computer Networks", "programming", 3,
              "Layered networking, TCP/IP, routing and the OSI model.",
              ("networking", "computer networking")),
    SkillSeed("testing-and-debugging", "Testing & Debugging", "programming", 2,
              "Unit tests, fixtures and systematic debugging.",
              ("unit testing", "software testing", "pytest")),

    # --- mathematics ---
    SkillSeed("linear-algebra", "Linear Algebra", "mathematics", 3,
              "Vectors, matrices, eigenvalues and decompositions."),
    SkillSeed("calculus", "Calculus", "mathematics", 3,
              "Differentiation, integration and multivariate calculus."),
    SkillSeed("optimization", "Mathematical Optimization", "mathematics", 4,
              "Convexity, gradient methods and constrained optimization.", ("convex optimization",)),

    # --- statistics ---
    SkillSeed("probability", "Probability", "statistics", 3,
              "Random variables, distributions and expectation."),
    SkillSeed("statistics", "Statistics", "statistics", 3,
              "Estimation, hypothesis testing and confidence intervals.", ("statistical inference",)),
    SkillSeed("experiment-design", "Experiment Design & A/B Testing", "statistics", 4,
              "Designing controlled experiments and analysing results.", ("ab testing",)),

    # --- data engineering ---
    SkillSeed("data-wrangling", "Data Wrangling", "data-engineering", 2,
              "Cleaning, reshaping and joining messy real-world data.", ("pandas", "data cleaning")),
    SkillSeed("data-visualization", "Data Visualization", "data-engineering", 2,
              "Communicating data with effective charts.", ("dataviz", "matplotlib")),
    SkillSeed("etl-pipelines", "ETL & Data Pipelines", "data-engineering", 3,
              "Batch and streaming pipelines for moving and transforming data.", ("etl",)),
    SkillSeed("big-data-spark", "Big Data (Spark)", "data-engineering", 4,
              "Distributed processing of large datasets with Spark.", ("apache spark",)),
    SkillSeed("data-warehousing", "Data Warehousing", "data-engineering", 3,
              "Dimensional modelling and analytical data stores."),
    SkillSeed("feature-engineering", "Feature Engineering", "data-engineering", 3,
              "Constructing predictive features from raw data."),

    # --- machine learning ---
    SkillSeed("machine-learning", "Machine Learning Foundations", "machine-learning", 3,
              "Supervised/unsupervised learning, bias-variance, evaluation.", ("ml", "ml foundations")),
    SkillSeed("supervised-learning", "Supervised Learning", "machine-learning", 3,
              "Regression and classification algorithms."),
    SkillSeed("unsupervised-learning", "Unsupervised Learning", "machine-learning", 3,
              "Clustering, dimensionality reduction and density estimation."),
    SkillSeed("model-evaluation", "Model Evaluation", "machine-learning", 3,
              "Cross-validation, metrics and error analysis."),
    SkillSeed("ensemble-methods", "Ensemble Methods", "machine-learning", 4,
              "Bagging, boosting and stacking.", ("xgboost", "random forest")),
    SkillSeed("recommender-systems", "Recommender Systems", "machine-learning", 4,
              "Collaborative filtering and content-based recommendation."),

    # --- deep learning ---
    SkillSeed("neural-networks", "Neural Networks", "deep-learning", 4,
              "Perceptrons, backpropagation and training dynamics.", ("ann",)),
    SkillSeed("deep-learning", "Deep Learning", "deep-learning", 4,
              "Deep architectures, regularization and optimization at scale.", ("dl",)),
    SkillSeed("cnn", "Convolutional Neural Networks", "deep-learning", 4,
              "Convolutional architectures for spatial data.", ("convnets", "cnns")),
    SkillSeed("rnn", "Recurrent Neural Networks", "deep-learning", 4,
              "Sequence models: RNNs, LSTMs and GRUs.", ("lstm", "rnns")),
    SkillSeed("transformers", "Transformers", "deep-learning", 5,
              "Attention-based architectures underpinning modern models.", ("attention",)),
    SkillSeed("pytorch", "PyTorch", "deep-learning", 3,
              "Building and training neural networks with PyTorch.", ("torch",)),

    # --- nlp ---
    SkillSeed("nlp-fundamentals", "NLP Fundamentals", "nlp", 3,
              "Tokenization, embeddings and text classification.", ("natural language processing",)),
    SkillSeed("word-embeddings", "Word Embeddings", "nlp", 3,
              "Distributed word representations (word2vec, GloVe).", ("word2vec",)),
    SkillSeed("language-models", "Language Models", "nlp", 5,
              "Statistical and neural language modelling.", ("lm",)),
    SkillSeed("named-entity-recognition", "Named Entity Recognition", "nlp", 4,
              "Sequence labelling and information extraction.", ("ner",)),

    # --- computer vision ---
    SkillSeed("image-processing", "Image Processing", "computer-vision", 2,
              "Filtering, transforms and classical image operations."),
    SkillSeed("computer-vision", "Computer Vision", "computer-vision", 4,
              "Recognition, detection and segmentation of images.", ("cv",)),
    SkillSeed("object-detection", "Object Detection", "computer-vision", 5,
              "Localizing and classifying objects (YOLO, Faster R-CNN).", ("yolo",)),
    SkillSeed("image-segmentation", "Image Segmentation", "computer-vision", 5,
              "Pixel-level classification and mask prediction."),

    # --- generative ai ---
    SkillSeed("generative-ai", "Generative AI", "generative-ai", 5,
              "Foundations of generative modelling across modalities.", ("genai",)),
    SkillSeed("large-language-models", "Large Language Models", "generative-ai", 5,
              "Pretraining, scaling and using LLMs.", ("llm", "llms")),
    SkillSeed("prompt-engineering", "Prompt Engineering", "generative-ai", 2,
              "Designing effective prompts for LLMs."),
    SkillSeed("rag-systems", "Retrieval-Augmented Generation", "generative-ai", 4,
              "Grounding LLMs with retrieval over external knowledge.", ("rag",)),
    SkillSeed("fine-tuning-llms", "Fine-tuning LLMs", "generative-ai", 5,
              "Adapting pretrained LLMs with SFT, LoRA and RLHF.", ("lora", "sft")),
    SkillSeed("diffusion-models", "Diffusion Models", "generative-ai", 5,
              "Score-based and denoising diffusion generative models.", ("stable diffusion",)),

    # --- mlops ---
    SkillSeed("docker-containers", "Docker & Containers", "mlops", 2,
              "Packaging applications into portable containers.", ("docker", "containers")),
    SkillSeed("model-deployment", "Model Deployment", "mlops", 4,
              "Serving models behind APIs with versioning and rollback."),
    SkillSeed("ml-monitoring", "ML Monitoring", "mlops", 4,
              "Tracking drift, data quality and model performance in production."),
    SkillSeed("ci-cd-ml", "CI/CD for ML", "mlops", 4,
              "Automated testing and delivery pipelines for ML systems.", ("cicd",)),
    SkillSeed("mlops-fundamentals", "MLOps Fundamentals", "mlops", 4,
              "Reproducibility, experiment tracking and the ML lifecycle.", ("mlops",)),

    # --- design ---
    SkillSeed("user-interface-design", "User Interface Design", "design", 2,
              "Layout, hierarchy, typography and wireframing interfaces.",
              ("ui design", "ui/ux", "ux design")),

    # --- game development ---
    SkillSeed("graphics-programming", "Graphics Programming", "game-development", 4,
              "Rendering pipelines, shaders and real-time graphics APIs.",
              ("opengl", "rendering", "3d graphics")),
    SkillSeed("game-development-frameworks", "Game Engines & Frameworks", "game-development", 2,
              "Building games with an engine: scenes, components and physics.",
              ("unity", "godot", "game engine")),
    SkillSeed("game-design-principles", "Game Design Principles", "game-development", 2,
              "Mechanics, pacing, difficulty curves and level design.",
              ("game design", "level design")),
)


# Edges read as: `source` requires `prerequisite`.
EDGES: tuple[EdgeSeed, ...] = (
    # programming spine
    EdgeSeed("python", "programming-fundamentals"),
    EdgeSeed("data-structures-algorithms", "python"),
    EdgeSeed("data-structures-algorithms", "programming-fundamentals"),
    EdgeSeed("sql", "programming-fundamentals"),
    EdgeSeed("shell-scripting", "programming-fundamentals"),

    # mathematics
    EdgeSeed("optimization", "calculus"),
    EdgeSeed("optimization", "linear-algebra"),

    # statistics
    EdgeSeed("statistics", "probability"),
    EdgeSeed("probability", "calculus", "soft_prerequisite", 0.6),
    EdgeSeed("experiment-design", "statistics"),

    # data engineering
    EdgeSeed("data-wrangling", "python"),
    EdgeSeed("data-visualization", "python"),
    EdgeSeed("data-visualization", "data-wrangling", "soft_prerequisite", 0.5),
    EdgeSeed("etl-pipelines", "python"),
    EdgeSeed("etl-pipelines", "sql"),
    EdgeSeed("data-warehousing", "sql"),
    EdgeSeed("big-data-spark", "etl-pipelines"),
    EdgeSeed("big-data-spark", "data-structures-algorithms", "soft_prerequisite", 0.6),
    EdgeSeed("feature-engineering", "data-wrangling"),
    EdgeSeed("feature-engineering", "statistics", "soft_prerequisite", 0.7),

    # machine learning core
    EdgeSeed("machine-learning", "python"),
    EdgeSeed("machine-learning", "linear-algebra"),
    EdgeSeed("machine-learning", "statistics"),
    EdgeSeed("machine-learning", "calculus", "soft_prerequisite", 0.6),
    EdgeSeed("machine-learning", "data-wrangling", "recommended", 0.5),
    EdgeSeed("supervised-learning", "machine-learning"),
    EdgeSeed("unsupervised-learning", "machine-learning"),
    EdgeSeed("model-evaluation", "machine-learning"),
    EdgeSeed("ensemble-methods", "supervised-learning"),
    EdgeSeed("ensemble-methods", "model-evaluation", "soft_prerequisite", 0.6),
    EdgeSeed("recommender-systems", "machine-learning"),
    EdgeSeed("recommender-systems", "linear-algebra", "soft_prerequisite", 0.6),
    EdgeSeed("feature-engineering", "machine-learning", "recommended", 0.4),

    # deep learning
    EdgeSeed("neural-networks", "machine-learning"),
    EdgeSeed("neural-networks", "linear-algebra"),
    EdgeSeed("neural-networks", "optimization", "soft_prerequisite", 0.7),
    EdgeSeed("deep-learning", "neural-networks"),
    EdgeSeed("pytorch", "python"),
    EdgeSeed("pytorch", "neural-networks", "soft_prerequisite", 0.7),
    EdgeSeed("deep-learning", "pytorch", "soft_prerequisite", 0.6),
    EdgeSeed("cnn", "deep-learning"),
    EdgeSeed("rnn", "deep-learning"),
    EdgeSeed("transformers", "deep-learning"),
    EdgeSeed("transformers", "rnn", "soft_prerequisite", 0.4),

    # nlp
    EdgeSeed("nlp-fundamentals", "machine-learning"),
    EdgeSeed("nlp-fundamentals", "python"),
    EdgeSeed("word-embeddings", "nlp-fundamentals"),
    EdgeSeed("word-embeddings", "neural-networks", "soft_prerequisite", 0.6),
    EdgeSeed("language-models", "nlp-fundamentals"),
    EdgeSeed("language-models", "transformers"),
    EdgeSeed("language-models", "word-embeddings", "soft_prerequisite", 0.5),
    EdgeSeed("named-entity-recognition", "nlp-fundamentals"),
    EdgeSeed("named-entity-recognition", "rnn", "soft_prerequisite", 0.5),

    # computer vision
    EdgeSeed("image-processing", "python"),
    EdgeSeed("computer-vision", "image-processing"),
    EdgeSeed("computer-vision", "cnn"),
    EdgeSeed("object-detection", "computer-vision"),
    EdgeSeed("image-segmentation", "computer-vision"),

    # generative ai
    EdgeSeed("generative-ai", "deep-learning"),
    EdgeSeed("large-language-models", "transformers"),
    EdgeSeed("large-language-models", "language-models"),
    EdgeSeed("large-language-models", "generative-ai", "soft_prerequisite", 0.5),
    EdgeSeed("prompt-engineering", "large-language-models", "soft_prerequisite", 0.4),
    EdgeSeed("rag-systems", "large-language-models"),
    EdgeSeed("rag-systems", "nlp-fundamentals", "soft_prerequisite", 0.5),
    EdgeSeed("fine-tuning-llms", "large-language-models"),
    EdgeSeed("diffusion-models", "generative-ai"),
    EdgeSeed("diffusion-models", "cnn", "soft_prerequisite", 0.6),

    # mlops
    EdgeSeed("mlops-fundamentals", "machine-learning"),
    EdgeSeed("mlops-fundamentals", "version-control-git"),
    EdgeSeed("docker-containers", "shell-scripting", "soft_prerequisite", 0.6),

    # systems spine — the backbone of every non-ML engineering role
    EdgeSeed("operating-systems", "programming-fundamentals"),
    EdgeSeed("computer-networks", "programming-fundamentals"),
    EdgeSeed("shell-scripting", "operating-systems", "soft_prerequisite", 0.4),
    EdgeSeed("testing-and-debugging", "programming-fundamentals"),

    # game development
    EdgeSeed("graphics-programming", "programming-fundamentals"),
    EdgeSeed("graphics-programming", "linear-algebra", "soft_prerequisite", 0.5),
    EdgeSeed("game-development-frameworks", "programming-fundamentals"),
    # No edge between game design and engines. The route designer had already
    # drawn `frameworks <- design-principles` at runtime, and asserting the
    # reverse here made a cycle the graph correctly refused. Design theory and
    # engine mechanics are complementary rather than sequential, so the seed
    # states neither direction and leaves the runtime edge standing.
    EdgeSeed("model-deployment", "mlops-fundamentals"),
    EdgeSeed("model-deployment", "docker-containers"),
    EdgeSeed("ml-monitoring", "model-deployment"),
    EdgeSeed("ci-cd-ml", "mlops-fundamentals"),
    EdgeSeed("ci-cd-ml", "docker-containers"),
)
