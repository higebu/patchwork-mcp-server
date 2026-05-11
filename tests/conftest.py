from __future__ import annotations

import pytest

import patchwork_mcp_server.server as server


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch):
    monkeypatch.setattr(server, "_client", None)
    monkeypatch.setenv("PATCHWORK_URL", "https://patchwork.example/")
    monkeypatch.setenv("PATCHWORK_API_VERSION", "1.2")
    yield
    server._client = None
