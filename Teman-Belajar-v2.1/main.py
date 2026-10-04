import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routes import router
from api.security import APIGuard
from api.study_routes import router as study_router
from config import get_settings
from services.errors import ServiceError
from services.rag_engine import RAGService
from services.study_service import StudyService

logger = logging.getLogger(__name__)


def create_app(settings=None, service=None):
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app):
        app.state.rag = service if service is not None else RAGService(settings)
        try:
            app.state.study = StudyService(app.state.rag)
            yield
        finally:
            app.state.rag.close()

    app = FastAPI(
        title="Teman Belajar API",
        description="Teman belajar materi kuliah: percakapan, rangkuman, flashcard, dan latihan soal bersumber.",
        version="2.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(APIGuard, settings=settings)
    app.include_router(router, prefix="/api/v1")
    app.include_router(study_router, prefix="/api/v1")

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return JSONResponse({"detail": str(exc)}, status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        # No raw provider exception, API keys, PDF content, or prompt in client/logs.
        logger.error(
            "Request gagal: %s %s (%s)", request.method, request.url.path, type(exc).__name__
        )
        return JSONResponse(
            {"detail": "Pemrosesan gagal. Coba lagi atau periksa konfigurasi layanan."},
            status_code=503,
        )

    @app.get("/")
    def root():
        return {"status": "online", "version": "2.1.0", "docs": "/docs"}

    @app.get("/health")
    def health():
        return {
            "status": "ok",
            "model_configured": bool(settings.google_api_key),
            "authentication": bool(settings.api_keys),
        }

    return app


app = create_app()
