from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import router as v1_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.ids import new_id
from app.core.security import CSRF_HEADER, CSRF_VALUE

MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="ProvaMüşteri API", version=settings.version)
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = f"req_{new_id()}"
        # CSRF: özel başlık tarayıcıyı CORS preflight'a zorlar; başka sitedeki form bunu gönderemez.
        if request.method in MUTATING and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
            return JSONResponse(status_code=403, content={"error": {
                "code": "csrf_header_missing", "message": "İstek reddedildi.",
                "request_id": request.state.request_id}})
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    # CORS en dışta olmalı ki preflight ve hata cevapları da başlık alsın.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-Requested-With"],
        expose_headers=["X-Request-ID"],
    )
    app.include_router(v1_router)
    return app


app = create_app()
