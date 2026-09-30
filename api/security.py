import secrets
import tempfile
import threading
import time
from collections import defaultdict, deque

from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse


class APIGuard:
    """Authenticate and cap request bytes before multipart/JSON parsing (one worker)."""

    def __init__(self, app, settings):
        self.app = app
        self.settings = settings
        self.windows = defaultdict(deque)
        self.lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1"):
            return await self.app(scope, receive, send)
        headers = {key.lower(): value for key, value in scope["headers"]}
        owner = "local"
        if self.settings.api_keys:
            supplied = headers.get(b"x-api-key", b"")
            owner = next(
                (
                    name
                    for name, key in self.settings.api_keys.items()
                    if secrets.compare_digest(supplied, key.get_secret_value().encode())
                ),
                None,
            )
            if owner is None:
                return await JSONResponse({"detail": "API key tidak valid."}, status_code=401)(
                    scope, receive, send
                )
        else:
            # Anonymous mode is explicitly restricted to local clients.
            host = (scope.get("client") or ("", 0))[0]
            if host not in ("127.0.0.1", "::1", "localhost", "testclient"):
                return await JSONResponse(
                    {"detail": "Akses jarak jauh membutuhkan RAG_API_KEYS."}, status_code=403
                )(scope, receive, send)
        scope.setdefault("state", {})["owner"] = owner
        now = time.monotonic()
        with self.lock:
            window = self.windows[owner]
            while window and window[0] <= now - 60:
                window.popleft()
            limited = len(window) >= self.settings.requests_per_minute
            if not limited:
                window.append(now)
        if limited:
            return await JSONResponse(
                {"detail": "Terlalu banyak request. Coba lagi nanti."},
                status_code=429,
                headers={"Retry-After": "60"},
            )(scope, receive, send)
        limit = (
            self.settings.max_upload_mb * 1024 * 1024 + 64 * 1024
            if scope["path"] == "/api/v1/upload"
            else 128 * 1024
        )
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Content-Length tidak valid."}, status_code=400)(
                scope, receive, send
            )
        if declared > limit:
            return await JSONResponse({"detail": "Ukuran request terlalu besar."}, status_code=413)(
                scope, receive, send
            )
        # Bound disk and memory use even when Content-Length is absent/incorrect.
        with tempfile.SpooledTemporaryFile(max_size=64 * 1024) as body:
            size = 0
            while True:
                event = await receive()
                if event["type"] == "http.disconnect":
                    return
                chunk = event.get("body", b"")
                size += len(chunk)
                if size > limit:
                    return await JSONResponse(
                        {"detail": "Ukuran request terlalu besar."}, status_code=413
                    )(scope, receive, send)
                await run_in_threadpool(body.write, chunk)
                if not event.get("more_body", False):
                    break
            await run_in_threadpool(body.seek, 0)
            consumed = 0

            async def bounded_receive():
                nonlocal consumed
                # After request body delivery retain normal disconnect semantics.
                if consumed > size:
                    return await receive()
                chunk = await run_in_threadpool(body.read, 64 * 1024)
                consumed += len(chunk)
                more = consumed < size
                if not more:
                    consumed = size + 1
                return {"type": "http.request", "body": chunk, "more_body": more}

            await self.app(scope, bounded_receive, send)
