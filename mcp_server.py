"""AssetManager MCP gateway.

Two run modes:
1. EMBEDDED (default in production): the Flask app hosts the MCP streamable
   HTTP endpoint at /mcp on port 8765, started and stopped by the
   Settings → MCP Enable/Disable toggle. No separate process to run.
2. STANDALONE (optional, for remote hosts): `python mcp_server.py` runs the
   gateway as its own process against a remote AssetManager, configured via
   ASSET_MANAGER_URL + ASSET_MANAGER_TOKEN (amcp_* token from Settings → MCP)
   or ASSET_MANAGER_USERNAME/PASSWORD.

Every tool call is authenticated by the amcp_* token sent by the MCP client
in the Authorization header; scope enforcement (read_only vs full) and role
permissions are applied by the app's own API layer.
"""
import argparse
import os
import time

import httpx
from mcp.server.fastmcp import Context, FastMCP

DEFAULT_URL = "http://127.0.0.1:5000"


class AssetManagerError(Exception):
    pass


class LocalClient:
    """In-process client: replays each call through the Flask app's WSGI
    stack with the caller's Authorization header, so authentication, scope
    and permission checks run exactly as they do for external API calls."""

    def __init__(self, app):
        from werkzeug.test import EnvironBuilder

        self._app = app
        self._builder = EnvironBuilder

    def get(self, path, params=None, token=None):
        from urllib.parse import urlencode

        query = ("?" + urlencode(params)) if params else ""
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        builder = self._builder(method="GET", path=path + query, headers=headers)
        environ = builder.get_environ()
        response = self._app.wsgi_app(environ, self._start_response)
        return self._parse(response)

    @staticmethod
    def _start_response(status, headers, exc_info=None):
        pass

    @staticmethod
    def _parse(response):
        import json

        if not response:
            raise AssetManagerError("Empty response from embedded API")
        body = b"".join(response)
        try:
            return json.loads(body.decode("utf-8"))
        except Exception:
            raise AssetManagerError(f"Non-JSON response: {body[:200]!r}")


class AssetManagerClient:
    """Standalone HTTP client over the AssetManager REST API."""

    def __init__(self, base_url, username=None, password=None, token=None, http=None):
        self.base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._access_token = token
        self._refresh_token = None
        self._expires_at = 0.0
        # http allows tests to inject a MockTransport (httpx).
        self._http = http or httpx

    def _headers(self):
        return {"Authorization": f"Bearer {self._access_token}"}

    def _ensure_token(self):
        if self._access_token and self._access_token.startswith("amcp_"):
            # App-issued MCP tokens are long-lived; no login/refresh needed.
            return
        if self._access_token and time.time() < self._expires_at - 30:
            return
        if self._refresh_token:
            try:
                self._refresh()
                return
            except AssetManagerError:
                pass
        if not self._username or not self._password:
            raise AssetManagerError(
                "AssetManager MCP is not authenticated. Set "
                "ASSET_MANAGER_USERNAME and ASSET_MANAGER_PASSWORD (or "
                "ASSET_MANAGER_TOKEN) and restart the server."
            )
        self._login()

    def _login(self):
        resp = self._http.post(
            f"{self.base_url}/api/v1/auth/login",
            json={"username": self._username, "password": self._password},
            timeout=30,
        )
        self._apply_token_response(resp)

    def _refresh(self):
        resp = self._http.post(
            f"{self.base_url}/api/v1/auth/refresh",
            json={"refresh_token": self._refresh_token},
            timeout=30,
        )
        self._apply_token_response(resp)

    def _apply_token_response(self, resp):
        if resp.status_code != 200:
            raise AssetManagerError(
                f"Authentication failed (HTTP {resp.status_code}): {resp.text[:300]}"
            )
        data = resp.json()
        self._access_token = data.get("access_token")
        self._refresh_token = data.get("refresh_token")
        expires_in = int(data.get("expires_in", 900))
        self._expires_at = time.time() + expires_in

    def get(self, path, params=None, token=None):
        self._ensure_token()
        headers = {"Authorization": f"Bearer {token}"} if token else self._headers()
        resp = self._http.get(
            f"{self.base_url}{path}", params=params, headers=headers, timeout=60
        )
        if resp.status_code == 401 and not token:
            # Token may have expired mid-flight; force a refresh once.
            self._access_token = None
            self._ensure_token()
            resp = self._http.get(
                f"{self.base_url}{path}",
                params=params,
                headers=self._headers(),
                timeout=60,
            )
        if resp.status_code >= 400:
            raise AssetManagerError(
                f"Request {path} failed (HTTP {resp.status_code}): {resp.text[:400]}"
            )
        return resp.json()


_client: AssetManagerClient | None = None
_embedded_app: object | None = None  # Flask app for embedded mode
_usage_logger = None  # set by the embedded app: fn(token, tool, args, ok, err, ms, ip)


def set_usage_logger(fn):
    global _usage_logger
    _usage_logger = fn


def _token_from_ctx(ctx: Context) -> str | None:
    """Extract the Authorization bearer token from the MCP request context."""
    try:
        request_ctx = ctx.request_context
        headers = request_ctx.request.headers
        auth = ""
        if headers is None:
            return None
        if hasattr(headers, "get"):
            # Starlette Headers / dict — .get is case-insensitive on Starlette.
            auth = headers.get("authorization") or headers.get("Authorization") or ""
        else:
            for key, value in headers:
                key_s = key.decode() if isinstance(key, bytes) else str(key)
                if key_s.lower() == "authorization":
                    auth = value.decode() if isinstance(value, bytes) else str(value)
        if auth.startswith("Bearer "):
            return auth.split(" ", 1)[1].strip()
    except Exception:
        pass
    return None


def get_client_for(token: str | None):
    """Right client for the current run mode. Embedded mode calls the app
    in-process with the caller's token; standalone mode uses the
    environment-configured HTTP client."""
    if _embedded_app is not None:
        return LocalClient(_embedded_app)
    global _client
    if _client is None:
        url = os.environ.get("ASSET_MANAGER_URL", DEFAULT_URL)
        env_token = os.environ.get("ASSET_MANAGER_TOKEN", "").strip() or None
        username = os.environ.get("ASSET_MANAGER_USERNAME", "").strip() or None
        password = os.environ.get("ASSET_MANAGER_PASSWORD", "") or None
        _client = AssetManagerClient(
            base_url=url, username=username, password=password, token=env_token
        )
    return _client


def _client_ip(ctx: Context):
    try:
        req = ctx.request_context.request
        headers = getattr(req, "headers", None)
        if headers is not None and hasattr(headers, "get"):
            xff = headers.get("x-forwarded-for")
            if xff:
                return str(xff).split(",")[0].strip()[:45]
        client = getattr(req, "client", None)
        if isinstance(client, (tuple, list)) and client:
            return str(client[0])[:45]
    except Exception:
        pass
    return None


def _record_usage(ctx: Context, tool_name, args, result, started):
    if _usage_logger is None:
        return
    error = None
    success = True
    if isinstance(result, dict) and result.get("error"):
        success, error = False, str(result["error"])
    elif (
        isinstance(result, list)
        and result
        and isinstance(result[0], dict)
        and result[0].get("error")
    ):
        success, error = False, str(result[0]["error"])
    duration_ms = int((time.monotonic() - started) * 1000)
    try:
        _usage_logger(
            _token_from_ctx(ctx),
            tool_name,
            (str(args)[:500] or None),
            success,
            error,
            duration_ms,
            _client_ip(ctx),
        )
    except Exception:
        pass


def _call(ctx: Context, tool_name, path, params=None):
    started = time.monotonic()
    try:
        token = _token_from_ctx(ctx)
        result = get_client_for(token).get(path, params=params, token=token)
    except Exception as exc:
        result = {"error": f"{exc}"}
    _record_usage(ctx, tool_name, params, result, started)
    return result


def build_fastmcp(embedded_app=None) -> FastMCP:
    global _embedded_app
    _embedded_app = embedded_app
    mcp = FastMCP("assetmanager")

    @mcp.tool()
    def search_assets(ctx: Context, query: str) -> dict:
        """Search every asset type at once by asset tag, vendor, model, or assignee."""
        return _call(ctx, "search_assets", "/api/v1/search", params={"q": query})

    @mcp.tool()
    def list_asset_types(ctx: Context) -> list:
        """List all asset types (built-in and custom) with key, label and icon."""
        try:
            return _call(ctx, "list_asset_types", "/api/v1/asset-types")
        except Exception as exc:
            return [{"error": f"{exc}"}]

    @mcp.tool()
    def list_assets(
        ctx: Context, asset_type: str, status: str = "all", q: str = "",
        page: int = 1, per_page: int = 25,
    ) -> dict:
        """List assets of a given type. Filters: status (In Stock, Assigned,
        Broken, Write Off, all), free-text q."""
        params = {"status": status, "q": q, "page": page, "per_page": per_page}
        started = time.monotonic()
        token = _token_from_ctx(ctx)
        client = get_client_for(token)
        try:
            custom = None
            for entry in client.get("/api/v1/asset-types", token=token):
                if entry.get("key") == asset_type:
                    custom = bool(entry.get("custom"))
            if custom is None:
                result = {"error": f"Unknown asset type: {asset_type}"}
            else:
                path = (
                    f"/api/v1/custom/{asset_type}/assets"
                    if custom
                    else f"/api/v1/assets/{asset_type}"
                )
                result = client.get(path, params=params, token=token)
        except Exception as exc:
            result = {"error": f"{exc}"}
        _record_usage(ctx, "list_assets", params, result, started)
        return result

    @mcp.tool()
    def get_asset(ctx: Context, asset_type: str, asset_id: int) -> dict:
        """Get a single asset by its type key and numeric id."""
        started = time.monotonic()
        token = _token_from_ctx(ctx)
        client = get_client_for(token)
        try:
            custom = None
            for entry in client.get("/api/v1/asset-types", token=token):
                if entry.get("key") == asset_type:
                    custom = bool(entry.get("custom"))
            if custom is None:
                result = {"error": f"Unknown asset type: {asset_type}"}
            else:
                path = (
                    f"/api/v1/custom/{asset_type}/assets/{asset_id}"
                    if custom
                    else f"/api/v1/assets/{asset_type}/{asset_id}"
                )
                result = client.get(path, token=token)
        except Exception as exc:
            result = {"error": f"{exc}"}
        _record_usage(ctx, "get_asset", {"asset_type": asset_type, "asset_id": asset_id}, result, started)
        return result

    @mcp.tool()
    def dashboard_summary(ctx: Context) -> dict:
        """Current inventory KPIs: total assets, assigned, available, broken,
        and per-category counts."""
        return _call(ctx, "dashboard_summary", "/api/v1/dashboard-summary")

    @mcp.tool()
    def list_users(ctx: Context) -> list:
        """List all usernames (local and LDAP)."""
        return _call(ctx, "list_users", "/api/v1/users")

    @mcp.tool()
    def list_departments(ctx: Context) -> list:
        """List all department names."""
        return _call(ctx, "list_departments", "/api/v1/departments")

    @mcp.tool()
    def list_roles(ctx: Context) -> list:
        """List roles with their capabilities and per-asset-type permissions."""
        return _call(ctx, "list_roles", "/api/v1/roles")

    @mcp.tool()
    def list_groups(ctx: Context) -> list:
        """List user groups with their assigned role and member user ids."""
        return _call(ctx, "list_groups", "/api/v1/groups")

    @mcp.tool()
    def list_audit_log(ctx: Context, page: int = 1, per_page: int = 50) -> dict:
        """Recent audit-log entries (creates, updates, deletes, logins) with
        actor, IP address, entity and details."""
        return _call(ctx, "list_audit_log", "/api/v1/audit-log", params={"page": page, "per_page": per_page})

    return mcp


def main():
    parser = argparse.ArgumentParser(description="AssetManager MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http"],
        default="stdio",
        help="MCP transport (default: stdio)",
    )
    parser.add_argument("--port", type=int, default=8765, help="HTTP port (default 8765)")
    args = parser.parse_args()

    mcp = build_fastmcp(embedded_app=None)
    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
