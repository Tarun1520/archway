"""
The front door: where a request comes from, and the security headers on every answer.

What this file does
    SecurityGuard is an ASGI middleware: it sees every HTTP request AND every WebSocket handshake before any route.

    1. Origin check. A browser sends an `Origin` header saying which site a request comes from. For anything that
       changes data (POST, PUT, PATCH, DELETE) and for WebSocket handshakes, a request whose Origin is not one of
       Archway's own sites is refused with 403.
         - This stops cross-site request forgery: another website cannot make your browser send a request to
           Archway with your sign-in cookie (the cookie's SameSite=Lax setting already blocks most of it; this is
           the second lock).
         - It stops cross-site WebSocket hijacking: another website cannot open the voice WebSocket as you.
       Requests without an Origin header (scripts, tests, the server's own health checks) are not browsers acting
       for a signed-in person, and pass to the normal sign-in checks.
    2. Security headers on every answer:
         X-Content-Type-Options: nosniff     the browser must not guess a different file type
         X-Frame-Options: DENY               and CSP frame-ancestors 'none': no other site may show Archway in a frame
                                             (blocks click-jacking and fake "framed" sign-in pages)
         Referrer-Policy: no-referrer        addresses are never passed on to other sites
         Cache-Control: no-store             answers about accounts and projects are never kept in a shared cache
         Cross-Origin-Opener-Policy / Resource-Policy: same-origin
         Strict-Transport-Security           on the HTTPS site only: browsers must always use HTTPS
       The API answers JSON, so its Content-Security-Policy allows nothing to run at all. The interactive API docs
       (/docs, only on a local machine) need their own scripts and are left without that policy.

Which origins are Archway's own
    ALLOWED_ORIGINS in the settings (the deployed site, e.g. https://archway.vercel.app). On a local machine
    (COOKIE_SECURE=false) any http://localhost:<port> or http://127.0.0.1:<port> is allowed as well, for the dev server.
"""

from urllib.parse import urlsplit

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


def origin_allowed(origin: str, allowed: list[str], local: bool) -> bool:
    origin = origin.strip().rstrip("/").lower()
    if origin in {item.strip().rstrip("/").lower() for item in allowed}:
        return True
    if local:
        parts = urlsplit(origin)
        return parts.scheme == "http" and parts.hostname in {"localhost", "127.0.0.1", "[::1]", "::1"}
    return False


class SecurityGuard:
    def __init__(self, app, *, allowed_origins: list[str], local: bool, https: bool):
        self.app = app
        self.allowed = allowed_origins
        self.local = local
        self.https = https

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        origin = headers.get("origin")
        checks_origin = scope["type"] == "websocket" or scope.get("method", "GET").upper() in UNSAFE_METHODS
        if checks_origin and origin is not None and not origin_allowed(origin, self.allowed, self.local):
            return await self._refuse(scope, receive, send)

        if scope["type"] == "websocket":
            return await self.app(scope, receive, send)

        path = scope.get("path", "")

        async def with_headers(message):
            if message["type"] == "http.response.start":
                extra = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"cross-origin-opener-policy", b"same-origin"),
                    (b"cross-origin-resource-policy", b"same-origin"),
                    (b"permissions-policy", b"camera=(), geolocation=(), payment=(), usb=()"),
                ]
                if not path.startswith(DOCS_PATHS):
                    extra.append((b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'"))
                if path.startswith("/api/"):
                    extra.append((b"cache-control", b"no-store"))
                if self.https:
                    extra.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains"))
                present = {name for name, _ in message.get("headers", [])}
                message = {**message, "headers": [*message.get("headers", []), *(h for h in extra if h[0] not in present)]}
            await send(message)

        return await self.app(scope, receive, with_headers)

    async def _refuse(self, scope, receive, send):
        if scope["type"] == "websocket":
            await receive()  # the handshake request
            await send({"type": "websocket.close", "code": 1008})  # 1008 = policy violation
            return
        body = b'{"detail":"This request did not come from Archway, so it was refused."}'
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})
