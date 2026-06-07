"""FastAPI application factory and router/exception-handler registration."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import analyze, health
from app.errors import (
    DigitalCoachError,
    InvalidVideoError,
    PoseNotDetectedError,
    StorageDownloadError,
    UnsupportedExerciseError,
    VideoTooLongError,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="DigitalCoach",
        version="0.1.0",
        summary="Calisthenics workout-video technique analysis",
    )
    app.include_router(health.router)
    app.include_router(analyze.router)
    _register_exception_handlers(app)
    return app


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(UnsupportedExerciseError)
    async def _unsupported(_: Request, exc: UnsupportedExerciseError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "supported": exc.supported},
        )

    @app.exception_handler(VideoTooLongError)
    async def _too_long(_: Request, exc: VideoTooLongError) -> JSONResponse:
        return JSONResponse(status_code=413, content={"detail": str(exc)})

    @app.exception_handler(InvalidVideoError)
    async def _invalid(_: Request, exc: InvalidVideoError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(PoseNotDetectedError)
    async def _no_pose(_: Request, exc: PoseNotDetectedError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(StorageDownloadError)
    async def _storage(_: Request, exc: StorageDownloadError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(DigitalCoachError)
    async def _fallback(_: Request, exc: DigitalCoachError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})


app = create_app()
