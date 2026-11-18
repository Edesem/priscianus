"""The HTTP layer: what every endpoint shares, `/api/explain`, `/api/drills`, `/api/grade` and
`/api/feedback` (ADR-005, Decision 1).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from priscianus.api.schemas import (
    DrillsRequest,
    DrillsResponse,
    ErrorBody,
    ExplainRequest,
    ExplainResponse,
    FeedbackError,
    FeedbackResponse,
    GradeRequest,
    GradeResponse,
    drills_response,
    explain_response,
    feedback_response,
    grade_response,
)
from priscianus.api.settings import Settings
from priscianus.llm.client import LLMClient, SpendCapExceeded
from priscianus.tutor.drills import DrillInputError, DrillModelError, make_drills
from priscianus.tutor.explain import ExplainInputError, ExplainModelError, explain
from priscianus.tutor.feedback import FeedbackModelError, feedback
from priscianus.tutor.grade import GradeInputError, grade
from priscianus.verifier.index import MorphologyIndex, SqliteIndex


def create_app(
    settings: Settings | None = None,
    *,
    index: MorphologyIndex | None = None,
    client: LLMClient | None = None,
) -> FastAPI:
    """Build the app. Tests pass a fake `index` and a `client` over a scripted API.

    Whatever is not passed is built once at start-up, from `settings`, and shared by all requests.
    """
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.index = index or SqliteIndex(settings.morphology_db)
        app.state.client = client or LLMClient.from_env(db_path=settings.llm_db)
        yield

    app = FastAPI(title="Priscianus", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Client-Id"],
    )
    _add_error_handlers(app)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # A plain `def`, so FastAPI runs it in a worker thread: it waits on the model.
    @app.post("/api/explain", responses={422: {"model": ErrorBody}, 503: {"model": ErrorBody}})
    def explain_endpoint(body: ExplainRequest, request: Request) -> ExplainResponse:
        result = explain(body.text, request.app.state.client, request.app.state.index)
        return explain_response(result)

    @app.post("/api/drills", responses={422: {"model": ErrorBody}, 503: {"model": ErrorBody}})
    def drills_endpoint(body: DrillsRequest, request: Request) -> DrillsResponse:
        result = make_drills(
            body.request, request.app.state.client, request.app.state.index, body.count
        )
        return drills_response(result)

    # No model is called here, so it is free and is not counted against the daily limit.
    @app.post("/api/grade", responses={422: {"model": ErrorBody}})
    def grade_endpoint(body: GradeRequest, request: Request) -> GradeResponse:
        result = grade(body.lemma, body.pos, body.features, body.answer, request.app.state.index)
        return grade_response(result)

    # The grade is free and always comes back. If the model fails, only the feedback is missing.
    @app.post("/api/feedback", responses={422: {"model": ErrorBody}})
    def feedback_endpoint(body: GradeRequest, request: Request) -> FeedbackResponse:
        index, client = request.app.state.index, request.app.state.client
        result = grade(body.lemma, body.pos, body.features, body.answer, index)
        try:
            written = feedback(
                body.lemma, body.pos, body.features, body.answer, result, client, index
            )
        except SpendCapExceeded:
            message = "The tutor has reached its spending limit. Try again later."
            error = FeedbackError(error="spend_cap", message=message)
            return feedback_response(result, None, error)
        except (FeedbackModelError, anthropic.APIError):
            message = "The tutor could not write feedback just now."
            error = FeedbackError(error="model_error", message=message)
            return feedback_response(result, None, error)
        return feedback_response(result, written)

    return app


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    def bad_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        examples = {
            "/api/drills": '{"request": "perfect tense of amo"}',
            "/api/feedback": '{"lemma": "amo", "pos": "verb", "features": {...}, "answer": "amat"}',
            "/api/grade": '{"lemma": "amo", "pos": "verb", "features": {...}, "answer": "amat"}',
        }
        example = examples.get(request.url.path, '{"text": "Arma virumque cano."}')
        return _error(422, "invalid_input", f"Send JSON like {example}.")

    @app.exception_handler(ExplainInputError)
    @app.exception_handler(DrillInputError)
    @app.exception_handler(GradeInputError)
    def bad_text(request: Request, exc: ExplainInputError) -> JSONResponse:
        return _error(422, "invalid_input", str(exc))

    @app.exception_handler(SpendCapExceeded)
    def spend_cap(request: Request, exc: SpendCapExceeded) -> JSONResponse:
        return _error(
            503, "spend_cap", "The tutor has reached its spending limit. Try again later."
        )

    @app.exception_handler(ExplainModelError)
    @app.exception_handler(DrillModelError)
    @app.exception_handler(anthropic.APIError)
    def model_error(request: Request, exc: Exception) -> JSONResponse:
        return _error(503, "model_error", "The tutor could not answer just now. Please try again.")


app = create_app()
