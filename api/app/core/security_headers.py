from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """OWASP-recommended response headers. This is a JSON/SSE API with no
    server-rendered HTML, so the CSP can be maximally strict -- there's
    nothing here that should ever load a script, style, or frame."""

    def __init__(self, app: object, *, hsts: bool) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._hsts = hsts

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if self._hsts:
            # Only sent when actually served over HTTPS (production) -- HSTS
            # over plain HTTP in local dev would get cached by the browser
            # and break the next http:// request to the same host.
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
