"""Declarative seed data for the learning-resource catalogue.

Pure data — no I/O. `seed.py` upserts these. Resources reference skills by
slug (resolved to ids by the loader), so the catalogue stays decoupled from
skill uuids. URLs are deliberately mock/example URLs; the provider +
external_id pair keeps every row addressable so a real catalogue can replace
the mocks later without a schema change.

difficulty: 1..5, estimated_hours: fractional, quality_score/rating in their
own scales. `teaches` bands and prerequisite `min_proficiency` are on the same
0..1 proficiency scale the learner profile uses.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TeachSeed:
    skill: str  # skill slug
    level_from: float = 0.0
    level_to: float = 0.6
    is_primary: bool = False


@dataclass(frozen=True)
class ResourceSeed:
    external_id: str
    title: str
    resource_type: str
    provider: str
    url: str
    difficulty: int
    estimated_hours: float
    description: str
    teaches: tuple[TeachSeed, ...]
    prerequisites: tuple[tuple[str, float], ...] = ()  # (skill_slug, min_proficiency)
    quality_score: float | None = None
    rating: float | None = None
    rating_count: int = 0
    modality: str = "mixed"
    metadata: dict = field(default_factory=dict)


def _t(skill: str, lo: float = 0.0, hi: float = 0.6, primary: bool = True) -> TeachSeed:
    return TeachSeed(skill=skill, level_from=lo, level_to=hi, is_primary=primary)


RESOURCES: tuple[ResourceSeed, ...] = (
    # ---------------------------------------------------------------- Python
    ResourceSeed(
        "py-course-basics", "Python for Everybody", "course", "Coursera",
        "https://example.com/resources/python-for-everybody", 1, 20.0,
        "A gentle, project-based introduction to Python programming.",
        (_t("python", 0.0, 0.6),), (), 0.92, 4.8, 21000, "video",
    ),
    ResourceSeed(
        "py-project-cli", "Build a Command-Line To-Do App", "project", "MockLabs",
        "https://example.com/resources/python-cli-todo", 2, 6.0,
        "Apply core Python by building a persistent CLI to-do application.",
        (_t("python", 0.4, 0.8),), (("python", 0.3),), 0.80, 4.5, 900, "project",
    ),
    ResourceSeed(
        "py-assessment-core", "Python Fundamentals Assessment", "assessment", "SkillCheck",
        "https://example.com/resources/python-assessment", 2, 1.0,
        "Diagnostic quiz covering data types, control flow and functions.",
        (_t("python", 0.0, 0.7),), (), 0.85, None, 0, "interactive",
    ),
    # ------------------------------------------------------------ Statistics
    ResourceSeed(
        "stats-course-intro", "Statistics with Python", "course", "Coursera",
        "https://example.com/resources/statistics-with-python", 3, 25.0,
        "Descriptive and inferential statistics taught with Python.",
        (_t("statistics", 0.0, 0.7), _t("probability", 0.0, 0.5, False)),
        (("python", 0.4),), 0.88, 4.6, 8400, "video",
    ),
    ResourceSeed(
        "stats-project-ab", "Run an A/B Test End to End", "project", "MockLabs",
        "https://example.com/resources/ab-test-project", 3, 8.0,
        "Design, run and analyse an A/B test on a sample dataset.",
        (_t("statistics", 0.5, 0.85),), (("statistics", 0.4),), 0.79, 4.4, 640, "project",
    ),
    # ----------------------------------------------------- Machine Learning
    ResourceSeed(
        "ml-course-andrewng", "Machine Learning Specialization", "course", "Coursera",
        "https://example.com/resources/ml-specialization", 3, 60.0,
        "Foundational supervised and unsupervised machine learning.",
        (_t("machine-learning", 0.0, 0.7), _t("supervised-learning", 0.0, 0.6, False)),
        (("python", 0.5), ("linear-algebra", 0.3), ("statistics", 0.3)),
        0.95, 4.9, 45000, "video",
    ),
    ResourceSeed(
        "ml-project-churn", "Predict Customer Churn", "project", "MockLabs",
        "https://example.com/resources/ml-churn-project", 3, 12.0,
        "Build, evaluate and tune a churn-prediction classifier.",
        (_t("machine-learning", 0.5, 0.8), _t("model-evaluation", 0.4, 0.7, False)),
        (("machine-learning", 0.4),), 0.82, 4.5, 1200, "project",
    ),
    ResourceSeed(
        "ml-assessment", "Machine Learning Concepts Assessment", "assessment", "SkillCheck",
        "https://example.com/resources/ml-assessment", 3, 1.5,
        "Checkpoint on bias-variance, metrics and core algorithms.",
        (_t("machine-learning", 0.0, 0.8),), (("machine-learning", 0.3),),
        0.86, None, 0, "interactive",
    ),
    ResourceSeed(
        "ml-doc-sklearn", "scikit-learn User Guide", "documentation", "scikit-learn",
        "https://example.com/resources/sklearn-user-guide", 2, 5.0,
        "Reference documentation for classical ML with scikit-learn.",
        (_t("machine-learning", 0.3, 0.7),), (("python", 0.5),), 0.90, 4.7, 3000, "text",
    ),
    # -------------------------------------------------------- Deep Learning
    ResourceSeed(
        "dl-course-specialization", "Deep Learning Specialization", "course", "Coursera",
        "https://example.com/resources/deep-learning-specialization", 4, 80.0,
        "Neural networks, optimization and modern deep learning practice.",
        (_t("deep-learning", 0.0, 0.7), _t("neural-networks", 0.0, 0.7, False)),
        (("machine-learning", 0.5), ("linear-algebra", 0.4)),
        0.94, 4.8, 39000, "video",
    ),
    ResourceSeed(
        "dl-book-goodfellow", "Deep Learning (Goodfellow et al.)", "book", "MIT Press",
        "https://example.com/resources/deep-learning-book", 5, 100.0,
        "The comprehensive theoretical reference on deep learning.",
        (_t("deep-learning", 0.4, 0.95),), (("deep-learning", 0.4), ("calculus", 0.5)),
        0.89, 4.6, 5200, "text",
    ),
    # -------------------------------------------------------------- PyTorch
    ResourceSeed(
        "pytorch-tutorial-official", "PyTorch 60-Minute Blitz", "tutorial", "PyTorch",
        "https://example.com/resources/pytorch-blitz", 3, 2.0,
        "Hands-on introduction to tensors, autograd and training loops.",
        (_t("pytorch", 0.0, 0.6),), (("python", 0.5),), 0.87, 4.6, 6100, "interactive",
    ),
    ResourceSeed(
        "pytorch-project-classifier", "Train an Image Classifier in PyTorch", "project", "MockLabs",
        "https://example.com/resources/pytorch-classifier", 4, 10.0,
        "Build and train a CNN image classifier from scratch in PyTorch.",
        (_t("pytorch", 0.4, 0.8), _t("cnn", 0.3, 0.6, False)),
        (("pytorch", 0.3), ("deep-learning", 0.4)), 0.83, 4.5, 1500, "project",
    ),
    # ------------------------------------------------------ Computer Vision
    ResourceSeed(
        "cv-course-stanford", "Convolutional Networks for Visual Recognition", "course", "Stanford",
        "https://example.com/resources/cs231n", 4, 70.0,
        "Deep learning for computer vision: CNNs, detection and segmentation.",
        (_t("computer-vision", 0.0, 0.75), _t("cnn", 0.2, 0.7, False)),
        (("deep-learning", 0.5), ("image-processing", 0.3)),
        0.93, 4.8, 12000, "video",
    ),
    ResourceSeed(
        "cv-project-detection", "Object Detection with YOLO", "project", "MockLabs",
        "https://example.com/resources/yolo-detection-project", 5, 14.0,
        "Fine-tune a YOLO model for a custom object-detection task.",
        (_t("object-detection", 0.4, 0.8), _t("computer-vision", 0.5, 0.8, False)),
        (("computer-vision", 0.5),), 0.81, 4.4, 720, "project",
    ),
    # ------------------------------------------------------------------- NLP
    ResourceSeed(
        "nlp-course-specialization", "Natural Language Processing Specialization", "course", "Coursera",
        "https://example.com/resources/nlp-specialization", 4, 60.0,
        "From text classification to sequence models and attention.",
        (_t("nlp-fundamentals", 0.0, 0.7), _t("word-embeddings", 0.2, 0.6, False)),
        (("machine-learning", 0.5), ("python", 0.5)),
        0.90, 4.6, 9800, "video",
    ),
    ResourceSeed(
        "nlp-project-sentiment", "Build a Sentiment Analyzer", "project", "MockLabs",
        "https://example.com/resources/sentiment-project", 3, 8.0,
        "Train and deploy a text-sentiment classifier.",
        (_t("nlp-fundamentals", 0.4, 0.75),), (("nlp-fundamentals", 0.4),),
        0.78, 4.3, 540, "project",
    ),
    # ---------------------------------------------------------- Transformers
    ResourceSeed(
        "transformers-course-hf", "Hugging Face Transformers Course", "course", "Hugging Face",
        "https://example.com/resources/hf-transformers-course", 4, 30.0,
        "Use and fine-tune transformer models with the Transformers library.",
        (_t("transformers", 0.0, 0.7),),
        (("deep-learning", 0.5), ("nlp-fundamentals", 0.4)),
        0.91, 4.7, 8700, "interactive",
    ),
    ResourceSeed(
        "transformers-article-attention", "The Illustrated Transformer", "article", "Blog",
        "https://example.com/resources/illustrated-transformer", 4, 1.5,
        "A visual, intuitive walkthrough of the attention mechanism.",
        (_t("transformers", 0.2, 0.6),), (("deep-learning", 0.4),),
        0.94, 4.9, 15000, "text",
    ),
    # ------------------------------------------------------------------ LLMs
    ResourceSeed(
        "llm-course-fullstack", "Building LLM Applications", "course", "MockAcademy",
        "https://example.com/resources/llm-applications", 4, 25.0,
        "Design, prompt, evaluate and ship applications on large language models.",
        (_t("large-language-models", 0.0, 0.7), _t("prompt-engineering", 0.0, 0.6, False)),
        (("transformers", 0.4),), 0.86, 4.5, 3100, "video",
    ),
    ResourceSeed(
        "llm-project-rag", "Build a Retrieval-Augmented Chatbot", "project", "MockLabs",
        "https://example.com/resources/rag-chatbot-project", 5, 16.0,
        "Ground an LLM on your own documents with a RAG pipeline.",
        (_t("rag-systems", 0.4, 0.85), _t("large-language-models", 0.5, 0.8, False)),
        (("large-language-models", 0.5),), 0.84, 4.6, 980, "project",
    ),
    ResourceSeed(
        "llm-assessment", "LLM Fundamentals Assessment", "assessment", "SkillCheck",
        "https://example.com/resources/llm-assessment", 4, 1.0,
        "Checkpoint on tokenization, prompting, context windows and evaluation.",
        (_t("large-language-models", 0.0, 0.8),), (("large-language-models", 0.3),),
        0.85, None, 0, "interactive",
    ),
    # ----------------------------------------------------------------- MLOps
    ResourceSeed(
        "mlops-course-zoomcamp", "MLOps Zoomcamp", "course", "MockAcademy",
        "https://example.com/resources/mlops-zoomcamp", 4, 40.0,
        "Experiment tracking, pipelines, deployment and monitoring for ML.",
        (_t("mlops-fundamentals", 0.0, 0.7), _t("model-deployment", 0.2, 0.6, False)),
        (("machine-learning", 0.5), ("docker-containers", 0.3)),
        0.88, 4.6, 4200, "video",
    ),
    ResourceSeed(
        "mlops-project-deploy", "Deploy and Monitor a Model API", "project", "MockLabs",
        "https://example.com/resources/deploy-model-project", 4, 12.0,
        "Containerize, deploy and add monitoring to a model-serving API.",
        (_t("model-deployment", 0.4, 0.8), _t("ml-monitoring", 0.3, 0.6, False)),
        (("mlops-fundamentals", 0.4), ("docker-containers", 0.4)),
        0.82, 4.4, 610, "project",
    ),
    ResourceSeed(
        "mlops-doc-mlflow", "MLflow Documentation", "documentation", "MLflow",
        "https://example.com/resources/mlflow-docs", 3, 4.0,
        "Reference for experiment tracking and model registry with MLflow.",
        (_t("mlops-fundamentals", 0.3, 0.6),), (("python", 0.5),), 0.87, 4.5, 2100, "text",
    ),
)
