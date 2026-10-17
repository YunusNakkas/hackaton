"""Sözleşmedeki hata formatı: {error: {code, message, request_id, details?}}."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("provamusteri")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict[str, Any] | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details


def unauthorized() -> ApiError:
    return ApiError(401, "unauthorized", "Oturum açmanız gerekiyor.")


def forbidden() -> ApiError:
    return ApiError(403, "forbidden", "Bu işlem için yetkiniz yok.")


def not_found(what: str = "Kayıt") -> ApiError:
    return ApiError(404, "not_found", f"{what} bulunamadı.")


def conflict(code: str, message: str) -> ApiError:
    return ApiError(409, code, message)


def _body(request: Request, code: str, message: str, details: dict | None = None) -> dict:
    err: dict[str, Any] = {
        "code": code,
        "message": message,
        "request_id": getattr(request.state, "request_id", "req_unknown"),
    }
    if details:
        err["details"] = details
    return {"error": err}


_STATUS_CODES = {
    401: ("unauthorized", "Oturum açmanız gerekiyor."),
    403: ("forbidden", "Bu işlem için yetkiniz yok."),
    404: ("not_found", "Kayıt bulunamadı."),
    405: ("not_found", "Kayıt bulunamadı."),
    413: ("payload_too_large", "Dosya çok büyük."),
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        return JSONResponse(_body(request, exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        fields = {}
        for e in exc.errors():
            loc = [str(p) for p in e.get("loc", []) if p not in ("body", "query", "path", "form")]
            fields[".".join(loc) or "_"] = e.get("msg", "Geçersiz değer")
        return JSONResponse(
            _body(request, "validation_error", "Girdi doğrulanamadı.", {"fields": fields}),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code, message = _STATUS_CODES.get(exc.status_code, ("internal_error", "Beklenmeyen bir hata oluştu."))
        return JSONResponse(_body(request, code, message), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("beklenmeyen hata", extra={"request_id": getattr(request.state, "request_id", None)})
        return JSONResponse(_body(request, "internal_error", "Beklenmeyen bir hata oluştu."), status_code=500)
