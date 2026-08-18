"""FastAPI application factory, middleware and exception handling."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.errors import AppError, ConflictError
from app.core.logging import configure_logging, get_logger, request_id_ctx
from app.db.session import SessionLocal, dispose_engine
from app.routers import api_router, health_router

configure_logging()
logger = get_logger(__name__)

PROBLEM_JSON = "application/problem+json"
REQUEST_ID_HEADER = "X-Request-ID"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "starting application",
        extra={"environment": settings.ENVIRONMENT, "version": settings.APP_VERSION},
    )
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("database connection verified")
    except Exception as exc:  # noqa: BLE001 - startup must not hard-fail on a cold DB
        # Kubernetes/Compose will keep restarting or hold traffic via the
        # readiness probe; crashing here would only mask the reason.
        logger.error("database unreachable at startup", extra={"error": str(exc)})

    yield

    await dispose_engine()
    logger.info("shutdown complete")


def _problem_response(
    status_code: int, payload: dict, request_id: str | None = None
) -> JSONResponse:
    headers = {REQUEST_ID_HEADER: request_id} if request_id else None
    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(payload),
        media_type=PROBLEM_JSON,
        headers=headers,
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "Backend for the AI-Powered Personalized Learning Path Recommender. "
            "Deterministic core: profile, skills, prerequisite graph, resources, "
            "paths, assessments and progress."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "unhandled exception",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                },
            )
            raise
        finally:
            request_id_ctx.reset(token)

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "request_id": request_id,
            },
        )
        return response

    # --- exception handlers ------------------------------------------------
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        request_id = request_id_ctx.get()
        log = logger.warning if exc.status_code < 500 else logger.error
        log(
            "domain error",
            extra={
                "code": exc.error_code,
                "status_code": exc.status_code,
                "path": request.url.path,
            },
        )
        return _problem_response(
            exc.status_code, exc.to_problem(instance=request.url.path), request_id
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _problem_response(
            422,
            {
                "type": "about:blank#validation_error",
                "title": "Validation Failed",
                "status": 422,
                "detail": "The request body or parameters failed validation",
                "code": "validation_error",
                "instance": request.url.path,
                "errors": exc.errors(),
            },
            request_id_ctx.get(),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # A race or a constraint the service layer did not anticipate.
        logger.warning("integrity error", extra={"path": request.url.path, "error": str(exc.orig)})
        problem = ConflictError(
            "The request conflicts with the current state of the database",
            error_code="integrity_error",
        )
        return _problem_response(
            problem.status_code, problem.to_problem(instance=request.url.path), request_id_ctx.get()
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_db_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("database error", extra={"path": request.url.path})
        return _problem_response(
            503,
            {
                "type": "about:blank#database_error",
                "title": "Service Unavailable",
                "status": 503,
                "detail": "A database error prevented this request from completing",
                "code": "database_error",
                "instance": request.url.path,
            },
            request_id_ctx.get(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return _problem_response(
            exc.status_code,
            {
                "type": "about:blank#http_error",
                "title": "HTTP Error",
                "status": exc.status_code,
                "detail": str(exc.detail),
                "code": "http_error",
                "instance": request.url.path,
            },
            request_id_ctx.get(),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", extra={"path": request.url.path})
        detail = str(exc) if settings.DEBUG else "An unexpected error occurred"
        return _problem_response(
            500,
            {
                "type": "about:blank#internal_error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": detail,
                "code": "internal_error",
                "instance": request.url.path,
            },
            request_id_ctx.get(),
        )

    # --- routes ------------------------------------------------------------
    app.include_router(health_router)
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
