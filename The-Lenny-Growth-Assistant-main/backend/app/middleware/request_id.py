"""
Attaches a unique request ID to every incoming request (reusing an incoming
X-Request-Id header if present) and echoes it back in the response.
Ties together logs, structured error responses, and — once the agent/RAG
layers exist — retrieval and generation traces for a single request.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
