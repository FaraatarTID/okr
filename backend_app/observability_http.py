from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import time
import uuid

from src.observability import observability_context
from backend_app.data_access_mode import current_data_access_context
from src.observability_metrics import (
    log_payload as build_observability_log_payload,
    record_api_request,
)


def _normalize_observability_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return text[:128]


def _resolve_request_observability_ids(request: Request) -> tuple[str, str]:
    request_state = getattr(request, "state", None)
    if request_state is not None:
        state_correlation_id = getattr(request_state, "correlation_id", None)
        state_request_id = getattr(request_state, "request_id", None)
        if state_correlation_id or state_request_id:
            correlation_id = _normalize_observability_id(
                state_correlation_id
                or state_request_id
            )
            request_id = _normalize_observability_id(state_request_id or state_correlation_id)
            if not correlation_id:
                correlation_id = f"req-{uuid.uuid4().hex}"
            if not request_id:
                request_id = correlation_id
            return correlation_id, request_id
    headers = request.headers
    request_id = _normalize_observability_id(
        headers.get("x-request-id") or headers.get("x-okr-request-id")
    )
    correlation_id = _normalize_observability_id(
        headers.get("x-correlation-id")
        or headers.get("x-okr-correlation-id")
        or request_id
    )
    if not correlation_id:
        correlation_id = f"req-{uuid.uuid4().hex}"
    if not request_id:
        request_id = correlation_id
    return correlation_id, request_id


def _get_request_start_time(request: Request) -> float:
    return float(getattr(getattr(request, "state", None), "start_time", time.perf_counter()))


def _normalize_error_detail(detail: Any) -> Any:
    if isinstance(detail, list | tuple):
        return [_normalize_error_detail(item) for item in detail]
    if isinstance(detail, dict):
        return {key: _normalize_error_detail(value) for key, value in detail.items()}
    if detail is None:
        return None
    if isinstance(detail, (str, int, float, bool)):
        return detail
    if isinstance(detail, Exception):
        return str(detail)
    return str(detail)


def build_error_envelope(
    status_code: int,
    detail: Any,
    request_id: str,
    correlation_id: str,
) -> dict[str, Any]:
    message = str(detail if isinstance(detail, (str, int, float, bool)) else "Request failed.")
    return {
        "code": f"HTTP_{status_code}",
        "error": message,
        "message": message,
        "detail": _normalize_error_detail(detail),
        "request_id": request_id,
        "correlation_id": correlation_id,
    }


def install_observability_handlers(app: FastAPI, logger) -> None:
    @app.middleware("http")
    async def _inject_observability_context(request: Request, call_next):
        correlation_id, request_id = _resolve_request_observability_ids(request)
        request.state.correlation_id = correlation_id
        request.state.request_id = request_id
        request.state.start_time = start_time = time.perf_counter()
        route = request.url.path
        route_obj = request.scope.get("route")
        if route_obj is not None:
            route = str(getattr(route_obj, "path", route))

        actor = request.headers.get("x-okr-actor")
        status_code = 500
        from backend_app.data_access_mode import data_access_context

        with data_access_context(
            actor=actor,
            request_id=request_id,
            correlation_id=correlation_id,
        ), observability_context(
            correlation_id=correlation_id, request_id=request_id
        ):
            try:
                response = await call_next(request)
                status_code = int(getattr(response, "status_code", 500) or 500)
                response.headers["X-Correlation-ID"] = correlation_id
                response.headers["X-Request-ID"] = request_id
            except Exception:
                duration_ms = (time.perf_counter() - start_time) * 1000
                record_api_request(
                    method=request.method,
                    route=route,
                    status_code=500,
                    duration_ms=duration_ms,
                    actor=actor,
                    strategy=(
                        current_data_access_context().effective_mode
                        if current_data_access_context()
                        else None
                    ),
                    fallback_reason=(
                        current_data_access_context().fallback_reason
                        if current_data_access_context()
                        else None
                    ),
                    resolver_state=(
                        current_data_access_context().resolver_state
                        if current_data_access_context()
                        else None
                    ),
                )
                logger.exception(
                    build_observability_log_payload(
                        event="http_request_unhandled_error",
                        method=request.method,
                        route=route,
                        status=500,
                        actor=actor,
                        correlation_id=correlation_id,
                        request_id=request_id,
                        duration_ms=round(duration_ms, 3),
                        error_code="UNHANDLED_EXCEPTION",
                    )
                )
                response = JSONResponse(
                    status_code=500,
                    content=build_error_envelope(
                        status_code=500,
                        detail="Internal server error.",
                        request_id=request_id,
                        correlation_id=correlation_id,
                    ),
                )
                response.headers["X-Correlation-ID"] = correlation_id
                response.headers["X-Request-ID"] = request_id
                status_code = 500
        duration_ms = (time.perf_counter() - start_time) * 1000
        record_api_request(
            method=request.method,
            route=route,
            status_code=status_code,
            duration_ms=duration_ms,
            actor=actor,
            strategy=(
                current_data_access_context().effective_mode
                if current_data_access_context()
                else None
            ),
            fallback_reason=(
                current_data_access_context().fallback_reason
                if current_data_access_context()
                else None
            ),
            resolver_state=(
                current_data_access_context().resolver_state
                if current_data_access_context()
                else None
            ),
        )
        logger.info(
            build_observability_log_payload(
                event="http_request",
                method=request.method,
                route=route,
                status=status_code,
                actor=actor,
                duration_ms=round(duration_ms, 3),
                correlation_id=correlation_id,
                request_id=request_id,
            )
        )
        return response

    @app.exception_handler(HTTPException)
    async def _http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        correlation_id, request_id = _resolve_request_observability_ids(request)
        payload = build_error_envelope(
            status_code=exc.status_code,
            detail=exc.detail,
            request_id=request_id,
            correlation_id=correlation_id,
        )
        response = JSONResponse(status_code=exc.status_code, content=payload)
        headers = getattr(exc, "headers", None)
        if headers:
            for header_name, header_value in headers.items():
                response.headers[str(header_name)] = str(header_value)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = request_id
        logger.warning(
            build_observability_log_payload(
                event="http_request_http_exception",
                method=request.method,
                route=str(request.url.path),
                status=exc.status_code,
                error_code=f"HTTP_{exc.status_code}",
                error_type=type(exc).__name__,
                correlation_id=correlation_id,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - _get_request_start_time(request)) * 1000, 3),
                actor=request.headers.get("x-okr-actor"),
            )
        )
        if (
            exc.status_code == 429
            and "retry-after" not in response.headers
            and isinstance(exc.detail, dict)
            and (retry_after_seconds := exc.detail.get("retry_after_seconds")) is not None
        ):
            response.headers["Retry-After"] = str(retry_after_seconds)
        duration_ms = (time.perf_counter() - _get_request_start_time(request)) * 1000
        record_api_request(
            method=request.method,
            route=str(request.url.path),
            status_code=exc.status_code,
            duration_ms=duration_ms,
            actor=request.headers.get("x-okr-actor"),
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def _request_validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        correlation_id, request_id = _resolve_request_observability_ids(request)
        payload = build_error_envelope(
            status_code=422,
            detail=exc.errors(),
            request_id=request_id,
            correlation_id=correlation_id,
        )
        response = JSONResponse(status_code=422, content=payload)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = request_id
        logger.warning(
            build_observability_log_payload(
                event="http_request_validation_error",
                method=request.method,
                route=str(request.url.path),
                status=422,
                error_code="HTTP_422",
                error_type="RequestValidationError",
                correlation_id=correlation_id,
                request_id=request_id,
                duration_ms=round((time.perf_counter() - _get_request_start_time(request)) * 1000, 3),
                actor=request.headers.get("x-okr-actor"),
                validation_error_count=len(exc.errors()),
            )
        )
        duration_ms = (time.perf_counter() - _get_request_start_time(request)) * 1000
        record_api_request(
            method=request.method,
            route=str(request.url.path),
            status_code=422,
            duration_ms=duration_ms,
            actor=request.headers.get("x-okr-actor"),
        )
        return response

    @app.exception_handler(Exception)
    async def _generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id, request_id = _resolve_request_observability_ids(request)
        logger.exception(
            build_observability_log_payload(
                event="backend_unhandled_exception",
                method=request.method,
                route=str(request.url.path),
                status=500,
                error_code="UNHANDLED_EXCEPTION",
                error_type=type(exc).__name__,
                request_id=request_id,
                correlation_id=correlation_id,
            )
        )
        payload = build_error_envelope(
            status_code=500,
            detail="Internal server error.",
            request_id=request_id,
            correlation_id=correlation_id,
        )
        response = JSONResponse(status_code=500, content=payload)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Request-ID"] = request_id
        duration_ms = (time.perf_counter() - _get_request_start_time(request)) * 1000
        record_api_request(
            method=request.method,
            route=str(request.url.path),
            status_code=500,
            duration_ms=duration_ms,
            actor=request.headers.get("x-okr-actor"),
        )
        return response


__all__ = [
    "build_error_envelope",
    "install_observability_handlers",
]
