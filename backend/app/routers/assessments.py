from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.core.deps import AdminUser, CurrentUser, PaginationDep, SessionDep
from app.models.enums import AssessmentType
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentDetail,
    AssessmentRead,
    AssessmentResultRead,
    AssessmentSubmission,
    AssessmentUpdate,
    QuestionAdminRead,
    QuestionCreate,
    QuestionUpdate,
)
from app.schemas.common import Page
from app.services.assessment_service import AssessmentService

router = APIRouter(prefix="/assessments", tags=["assessments"])
results_router = APIRouter(prefix="/me/assessment-results", tags=["assessments"])


def _to_read(assessment, question_count: int | None = None) -> AssessmentRead:  # type: ignore[no-untyped-def]
    data = AssessmentRead.model_validate(assessment)
    return data.model_copy(
        update={
            "question_count": question_count
            if question_count is not None
            else len(assessment.questions)
        }
    )


@router.get("", response_model=Page[AssessmentRead])
async def list_assessments(
    session: SessionDep,
    pagination: PaginationDep,
    _: CurrentUser,
    skill_id: uuid.UUID | None = None,
    type: AssessmentType | None = None,
    is_active: bool | None = True,
) -> Page[AssessmentRead]:
    service = AssessmentService(session)
    items, total = await service.list(
        limit=pagination.limit,
        offset=pagination.offset,
        skill_id=skill_id,
        assessment_type=type,
        is_active=is_active,
    )
    counts = await service.assessments.question_counts([a.id for a in items])
    return Page[AssessmentRead](
        items=[_to_read(a, counts.get(a.id, 0)) for a in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@router.post("", response_model=AssessmentDetail, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    payload: AssessmentCreate, session: SessionDep, _: AdminUser
) -> AssessmentDetail:
    assessment = await AssessmentService(session).create(payload)
    detail = AssessmentDetail.model_validate(assessment)
    return detail.model_copy(update={"question_count": len(assessment.questions)})


@router.get(
    "/{assessment_id}",
    response_model=AssessmentDetail,
    summary="Assessment with its questions (answer keys withheld)",
)
async def get_assessment(
    assessment_id: uuid.UUID, session: SessionDep, _: CurrentUser
) -> AssessmentDetail:
    assessment = await AssessmentService(session).get(assessment_id)
    detail = AssessmentDetail.model_validate(assessment)
    return detail.model_copy(update={"question_count": len(assessment.questions)})


@router.patch("/{assessment_id}", response_model=AssessmentRead)
async def update_assessment(
    assessment_id: uuid.UUID, payload: AssessmentUpdate, session: SessionDep, _: AdminUser
) -> AssessmentRead:
    assessment = await AssessmentService(session).update(assessment_id, payload)
    return _to_read(assessment)


@router.delete("/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_assessment(
    assessment_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> None:
    await AssessmentService(session).delete(assessment_id)


# --- questions -------------------------------------------------------------
@router.get(
    "/{assessment_id}/questions",
    response_model=list[QuestionAdminRead],
    summary="Questions including answer keys (admin)",
)
async def list_questions(
    assessment_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> list[QuestionAdminRead]:
    questions = await AssessmentService(session).list_questions(assessment_id)
    return [QuestionAdminRead.model_validate(q) for q in questions]


@router.post(
    "/{assessment_id}/questions", response_model=QuestionAdminRead, status_code=status.HTTP_201_CREATED
)
async def add_question(
    assessment_id: uuid.UUID, payload: QuestionCreate, session: SessionDep, _: AdminUser
) -> QuestionAdminRead:
    question = await AssessmentService(session).add_question(assessment_id, payload)
    return QuestionAdminRead.model_validate(question)


@router.patch("/{assessment_id}/questions/{question_id}", response_model=QuestionAdminRead)
async def update_question(
    assessment_id: uuid.UUID,
    question_id: uuid.UUID,
    payload: QuestionUpdate,
    session: SessionDep,
    _: AdminUser,
) -> QuestionAdminRead:
    question = await AssessmentService(session).update_question(
        assessment_id, question_id, payload
    )
    return QuestionAdminRead.model_validate(question)


@router.delete(
    "/{assessment_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None
)
async def delete_question(
    assessment_id: uuid.UUID, question_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> None:
    await AssessmentService(session).delete_question(assessment_id, question_id)


# --- attempts --------------------------------------------------------------
@router.post(
    "/{assessment_id}/submit",
    response_model=AssessmentResultRead,
    status_code=status.HTTP_201_CREATED,
    summary="Submit answers and receive a graded result",
)
async def submit_assessment(
    assessment_id: uuid.UUID,
    payload: AssessmentSubmission,
    session: SessionDep,
    current_user: CurrentUser,
) -> AssessmentResultRead:
    result = await AssessmentService(session).submit(assessment_id, current_user.id, payload)
    return AssessmentResultRead.model_validate(result)


@results_router.get("", response_model=Page[AssessmentResultRead])
async def list_my_results(
    session: SessionDep, pagination: PaginationDep, current_user: CurrentUser
) -> Page[AssessmentResultRead]:
    items, total = await AssessmentService(session).list_results(
        current_user.id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[AssessmentResultRead](
        items=[AssessmentResultRead.model_validate(r) for r in items],
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
    )


@results_router.get("/{result_id}", response_model=AssessmentResultRead)
async def get_my_result(
    result_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> AssessmentResultRead:
    result = await AssessmentService(session).get_result(result_id, current_user.id)
    return AssessmentResultRead.model_validate(result)
