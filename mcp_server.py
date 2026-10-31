"""AssetManager MCP server — expose the AssetManager read-only REST API as
Model Context Protocol tools so LLM clients (Claude Desktop, Codex, Hermes,
Cursor, ...) can query assets, users, departments, roles, groups and the
audit log.

Configuration (environment variables):
    ASSET_MANAGER_URL        Base URL of the AssetManager instance
                             (default http://127.0.0.1:5000)
    ASSET_MANAGER_USERNAME   Local or LDAP username
    ASSET_MANAGER_PASSWORD   Password for that username
    ASSET_MANAGER_TOKEN      Optional: skip login and use this JWT access
                             token directly (takes precedence)

Transports:
    stdio (default)          python mcp_server.py
                             (Claude Desktop / Codex style local MCP config)
    streamable HTTP          python mcp_server.py --transport streamable-http --port 8765
                             then connect clients to http://<host>:8765/mcp

All tools are read-only: they map to GET endpoints of the REST API.
"""
import argparse
import os
import time

import httpx
from mcp.server.fastmcp import FastMCP

DEFAULT_URL = "http://127.0.0.1:5000"

mcp = FastMCP("assetmanager")


class AssetManagerError(Exception):
    pass


class AssetManagerClient:
    """Thin, authenticated HTTP client over the AssetManager REST API."""

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

    def get(self, path, params=None):
        self._ensure_token()
        resp = self._http.get(
            f"{self.base_url}{path}", params=params, headers=self._headers(), timeout=60
        )
        if resp.status_code == 401:
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


def get_client() -> AssetManagerClient:
    global _client
    if _client is None:
        url = os.environ.get("ASSET_MANAGER_URL", DEFAULT_URL)
        token = os.environ.get("ASSET_MANAGER_TOKEN", "").strip() or None
        username = os.environ.get("ASSET_MANAGER_USERNAME", "").strip() or None
        password = os.environ.get("ASSET_MANAGER_PASSWORD", "") or None
        _client = AssetManagerClient(
            base_url=url, username=username, password=password, token=token
        )
    return _client


def _tool_error(exc: Exception) -> str:
    return f"Error: {exc}"


@mcp.tool()
def search_assets(query: str) -> dict:
    """Search every asset type at once by asset tag, vendor, model, or assignee.
    Returns up to 15 matching assets with their type, tag and detail URL."""
    try:
        return get_client().get("/api/v1/search", params={"q": query})
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": _tool_error(exc)}


@mcp.tool()
def list_asset_types() -> list:
    """List all asset types (built-in and custom) with key, label and icon."""
    try:
        return get_client().get("/api/v1/asset-types")
    except Exception as exc:  # pragma: no cover - defensive
        return [{"error": _tool_error(exc)}]


def _is_custom_type(client, asset_type):
    for entry in client.get("/api/v1/asset-types"):
        if entry.get("key") == asset_type:
            return bool(entry.get("custom"))
    return None


@mcp.tool()
def list_assets(
    asset_type: str, status: str = "all", q: str = "", page: int = 1, per_page: int = 25
) -> dict:
    """List assets of a given type (use list_asset_types for valid keys).
    Filters: status (In Stock, Assigned, Broken, Write Off, all), free-text q."""
    try:
        params = {"status": status, "q": q, "page": page, "per_page": per_page}
        client = get_client()
        custom = _is_custom_type(client, asset_type)
        if custom is None:
            return {"error": f"Unknown asset type: {asset_type}"}
        path = f"/api/v1/custom/{asset_type}/assets" if custom else f"/api/v1/assets/{asset_type}"
        return client.get(path, params=params)
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": _tool_error(exc)}


@mcp.tool()
def get_asset(asset_type: str, asset_id: int) -> dict:
    """Get a single asset by its type key and numeric id."""
    try:
        client = get_client()
        custom = _is_custom_type(client, asset_type)
        if custom is None:
            return {"error": f"Unknown asset type: {asset_type}"}
        path = (
            f"/api/v1/custom/{asset_type}/assets/{asset_id}"
            if custom
            else f"/api/v1/assets/{asset_type}/{asset_id}"
        )
        return client.get(path)
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": _tool_error(exc)}


@mcp.tool()
def dashboard_summary() -> dict:
    """Current inventory KPIs: total assets, assigned, available, broken, and
    per-category counts."""
    try:
        return get_client().get("/api/v1/dashboard-summary")
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": _tool_error(exc)}


@mcp.tool()
def list_users() -> list:
    """List all usernames (local and LDAP)."""
    try:
        return get_client().get("/api/v1/users")
    except Exception as exc:  # pragma: no cover - defensive
        return [{"error": _tool_error(exc)}]


@mcp.tool()
def list_departments() -> list:
    """List all department names."""
    try:
        return get_client().get("/api/v1/departments")
    except Exception as exc:  # pragma: no cover - defensive
        return [{"error": _tool_error(exc)}]


@mcp.tool()
def list_roles() -> list:
    """List roles with their capabilities and per-asset-type permissions."""
    try:
        return get_client().get("/api/v1/roles")
    except Exception as exc:  # pragma: no cover - defensive
        return [{"error": _tool_error(exc)}]


@mcp.tool()
def list_groups() -> list:
    """List user groups with their assigned role and member user ids."""
    try:
        return get_client().get("/api/v1/groups")
    except Exception as exc:  # pragma: no cover - defensive
        return [{"error": _tool_error(exc)}]


@mcp.tool()
def list_audit_log(page: int = 1, per_page: int = 50) -> dict:
    """Recent audit-log entries (creates, updates, deletes, logins) with
    actor, IP address, entity and details."""
    try:
        return get_client().get(
            "/api/v1/audit-log", params={"page": page, "per_page": per_page}
        )
    except Exception as exc:  # pragma: no cover - defensive
        return {"error": _tool_error(exc)}


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

    if args.transport == "streamable-http":
        mcp.run(transport="streamable-http", host="0.0.0.0", port=args.port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
