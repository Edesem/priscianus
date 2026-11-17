"""The HTTP layer: what every endpoint shares, and `POST /api/explain` (ADR-005, Decision 1)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anthropic
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from priscianus.api.schemas import ErrorBody, ExplainRequest, ExplainResponse, explain_response
from priscianus.api.settings import Settings
from priscianus.llm.client import LLMClient, SpendCapExceeded
from priscianus.tutor.explain import ExplainInputError, ExplainModelError, explain
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

    return app


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _add_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    def bad_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(422, "invalid_input", 'Send JSON like {"text": "Arma virumque cano."}.')

    @app.exception_handler(ExplainInputError)
    def bad_text(request: Request, exc: ExplainInputError) -> JSONResponse:
        return _error(422, "invalid_input", str(exc))

    @app.exception_handler(SpendCapExceeded)
    def spend_cap(request: Request, exc: SpendCapExceeded) -> JSONResponse:
        return _error(
            503, "spend_cap", "The tutor has reached its spending limit. Try again later."
        )

    @app.exception_handler(ExplainModelError)
    @app.exception_handler(anthropic.APIError)
    def model_error(request: Request, exc: Exception) -> JSONResponse:
        return _error(503, "model_error", "The tutor could not answer just now. Please try again.")


app = create_app()
