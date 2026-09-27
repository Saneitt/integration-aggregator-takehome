from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ServiceError(Exception):
    status = 500
    code = "internal_error"
    title = "Internal server error"
    detail = "The request could not be completed."


class InvalidInput(ServiceError):
    status, code, title, detail = (
        422,
        "validation_error",
        "Invalid input",
        "The request is invalid.",
    )


class ReservedProviderName(ServiceError):
    status, code, title, detail = (
        422,
        "reserved_provider_name",
        "Reserved provider name",
        "That name is reserved.",
    )


class ProviderNotFound(ServiceError):
    status, code, title, detail = (
        404,
        "provider_not_found",
        "Provider not found",
        "The provider is not registered.",
    )


class InvalidState(ServiceError):
    status, code, title, detail = (
        400,
        "invalid_state",
        "Invalid OAuth state",
        "The state is invalid or expired.",
    )


class ConsentDenied(ServiceError):
    status, code, title, detail = (
        400,
        "consent_denied",
        "Consent denied",
        "The provider denied authorization.",
    )


class ExchangeFailed(ServiceError):
    status, code, title, detail = (
        502,
        "exchange_failed",
        "Authorization exchange failed",
        "The provider exchange failed.",
    )


class UpstreamUnavailable(ServiceError):
    status, code, title, detail = (
        502,
        "upstream_unavailable",
        "Upstream unavailable",
        "OpenBao is unavailable.",
    )


class QueueFull(ServiceError):
    status, code, title, detail = 503, "queue_full", "Queue full", "Retry the request later."


class RequestNotFound(ServiceError):
    status, code, title, detail = (
        404,
        "request_not_found",
        "Request not found",
        "The request is unknown or expired.",
    )


class OpenBaoError(Exception):
    def __init__(self, message: str = "OpenBao request failed") -> None:
        super().__init__(message)


class NotFound(OpenBaoError):
    pass


class BadRequest(OpenBaoError):
    pass


class PermissionDenied(OpenBaoError):
    pass


class Unavailable(OpenBaoError):
    pass


def problem(status: int, title: str, detail: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": "about:blank",
            "title": title,
            "status": status,
            "detail": detail,
            "code": code,
        },
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def handle_service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return problem(exc.status, exc.title, exc.detail, exc.code)

    @app.exception_handler(ValueError)
    async def handle_value_error(_: Request, exc: ValueError) -> JSONResponse:
        return problem(422, "Invalid input", str(exc), "validation_error")

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return problem(
            422,
            "Invalid input",
            "The request body or path parameters are invalid.",
            "validation_error",
        )

    @app.exception_handler(OpenBaoError)
    async def handle_openbao_error(_: Request, __: OpenBaoError) -> JSONResponse:
        return problem(
            502,
            "Upstream unavailable",
            "The upstream secrets service could not complete the request.",
            "upstream_unavailable",
        )
