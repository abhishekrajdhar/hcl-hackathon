"""Unit tests for the deterministic assessment engine."""

from __future__ import annotations

import uuid

from app.engines.assessment import (
    SkillFact,
    generate_mc_questions,
    mastery_level,
    recommended_next_action,
    weak_topics,
)


def test_mastery_bands_match_spec() -> None:
    assert mastery_level(0.95) == "strong_mastery"
    assert mastery_level(0.90) == "strong_mastery"
    assert mastery_level(0.75) == "good_understanding"
    assert mastery_level(0.70) == "good_understanding"
    assert mastery_level(0.55) == "partial_understanding"
    assert mastery_level(0.50) == "partial_understanding"
    assert mastery_level(0.49) == "requires_remediation"
    assert mastery_level(0.0) == "requires_remediation"


def test_next_action_depends_on_band_and_weak_topics() -> None:
    assert "Advance" in recommended_next_action(0.95, [])
    assert "Remediate" in recommended_next_action(0.2, [])
    with_focus = recommended_next_action(0.55, ["Statistics"])
    assert "Statistics" in with_focus


def test_weak_topics_identifies_low_scoring_skills() -> None:
    s1, s2 = uuid.uuid4(), uuid.uuid4()
    responses = [
        {"skill_id": str(s1), "is_correct": True},
        {"skill_id": str(s1), "is_correct": True},
        {"skill_id": str(s2), "is_correct": False},
        {"skill_id": str(s2), "is_correct": False},
    ]
    weak = weak_topics(responses, {s1: "Strong Skill", s2: "Weak Skill"})
    assert [w.skill_name for w in weak] == ["Weak Skill"]  # s1 at 100% is not weak
    assert weak[0].correct == 0 and weak[0].total == 2


def test_question_generation_is_valid_and_gradeable() -> None:
    skill = SkillFact(uuid.uuid4(), "Machine Learning", "Supervised learning", "Machine Learning")
    distractors = [
        SkillFact(uuid.uuid4(), "Statistics", "Inference"),
        SkillFact(uuid.uuid4(), "Python", "Programming"),
        SkillFact(uuid.uuid4(), "Deep Learning", "Neural nets"),
    ]
    questions = generate_mc_questions(skill, distractors, count=5, difficulty=2)
    assert len(questions) == 5
    for q in questions:
        assert len(q.options) >= 2
        keys = [o["key"] for o in q.options]
        assert len(keys) == len(set(keys))          # unique keys
        assert q.correct_key in keys                # correct key is a real option
        assert q.stem and q.explanation


def test_question_generation_is_deterministic() -> None:
    skill = SkillFact(uuid.uuid5(uuid.NAMESPACE_DNS, "ml"), "ML", "desc", "ML")
    distractors = [SkillFact(uuid.uuid5(uuid.NAMESPACE_DNS, f"d{i}"), f"D{i}", "x") for i in range(3)]
    a = generate_mc_questions(skill, distractors, count=4, difficulty=2)
    b = generate_mc_questions(skill, distractors, count=4, difficulty=2)
    assert [(q.stem, q.correct_key, [o["text"] for o in q.options]) for q in a] == \
           [(q.stem, q.correct_key, [o["text"] for o in q.options]) for q in b]


def test_generated_questions_pass_pydantic_validation() -> None:
    from app.llm.schemas import GeneratedQuestion

    skill = SkillFact(uuid.uuid4(), "ML", "desc")
    distractors = [SkillFact(uuid.uuid4(), f"D{i}", "x") for i in range(3)]
    for q in generate_mc_questions(skill, distractors, count=3, difficulty=2):
        # the template output must satisfy the same schema an LLM must
        GeneratedQuestion.model_validate(
            {"stem": q.stem, "options": q.options, "correct_key": q.correct_key,
             "explanation": q.explanation, "difficulty": q.difficulty}
        )


def test_llm_schema_rejects_bad_correct_key() -> None:
    import pytest
    from pydantic import ValidationError

    from app.llm.schemas import GeneratedQuestion

    with pytest.raises(ValidationError):
        GeneratedQuestion.model_validate(
            {"stem": "Q", "options": [{"key": "a", "text": "x"}, {"key": "b", "text": "y"}],
             "correct_key": "z"}  # not an option key
        )
