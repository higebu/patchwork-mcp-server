from __future__ import annotations

from typing import Any

import httpx


class PatchworkError(RuntimeError):
    def __init__(self, status: int, url: str, body: str):
        super().__init__(f"Patchwork API {status} for {url}: {body[:200]}")
        self.status = status
        self.url = url
        self.body = body


class PatchworkClient:
    """Thin synchronous wrapper around the Patchwork REST API.

    Defaults to https://patchwork.kernel.org with API v1.2. The comments
    endpoint lives outside the versioned tree (/api/<kind>s/<id>/comments/)
    so callers can pass an absolute URL or use :meth:`comments`.
    """

    def __init__(
        self,
        base_url: str = "https://patchwork.kernel.org",
        token: str | None = None,
        api_version: str = "1.2",
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_version = api_version
        self.api_root = f"{self.base_url}/api/{api_version}"
        headers = {
            "User-Agent": "patchwork-mcp",
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Token {token}"
        self._client = httpx.Client(timeout=timeout, headers=headers, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PatchworkClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def request(self, path_or_url: str, **params: Any) -> Any:
        if path_or_url.startswith(("http://", "https://")):
            url = path_or_url
        elif path_or_url.startswith("/api/"):
            url = f"{self.base_url}{path_or_url}"
        else:
            url = f"{self.api_root}{path_or_url}"
        clean = {k: v for k, v in params.items() if v is not None}
        resp = self._client.get(url, params=clean)
        if resp.status_code >= 400:
            raise PatchworkError(resp.status_code, str(resp.request.url), resp.text)
        return resp.json()

    def projects(self) -> list[dict]:
        return self.request("/projects/")

    def project(self, link_name_or_id: str | int) -> dict:
        return self.request(f"/projects/{link_name_or_id}/")

    def patches(self, **params: Any) -> list[dict]:
        return self.request("/patches/", **params)

    def patch(self, patch_id: int) -> dict:
        return self.request(f"/patches/{patch_id}/")

    def covers(self, **params: Any) -> list[dict]:
        return self.request("/covers/", **params)

    def cover(self, cover_id: int) -> dict:
        return self.request(f"/covers/{cover_id}/")

    def series(self, series_id: int) -> dict:
        return self.request(f"/series/{series_id}/")

    def checks(self, patch_id: int) -> list[dict]:
        return self.request(f"/api/patches/{patch_id}/checks/")

    def comments(self, kind: str, item_id: int) -> list[dict]:
        if kind not in ("patch", "cover"):
            raise ValueError("kind must be 'patch' or 'cover'")
        resource = "patches" if kind == "patch" else "covers"
        return self.request(f"/api/{resource}/{item_id}/comments/")

    def people(self, q: str) -> list[dict]:
        return self.request("/people/", q=q)
