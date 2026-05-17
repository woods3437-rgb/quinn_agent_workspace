from __future__ import annotations

import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class InternalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = os.getenv("CTO_OS_ADMIN_TOKEN")
        if not token or request.url.path == "/health":
            return await call_next(request)

        auth = request.headers.get("authorization", "")
        bearer = auth.removeprefix("Bearer ").strip() if auth.startswith("Bearer ") else ""
        header_token = request.headers.get("x-cto-os-token", "")
        if bearer != token and header_token != token:
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)
