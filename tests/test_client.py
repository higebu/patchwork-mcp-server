from __future__ import annotations

import pytest
import respx
from httpx import Response

from patchwork_mcp_server.client import PatchworkClient, PatchworkError


@respx.mock
def test_projects_call_targets_versioned_endpoint():
    respx.get("https://patchwork.example/api/1.2/projects/").mock(
        return_value=Response(200, json=[{"id": 399, "link_name": "netdevbpf", "name": "Netdev"}])
    )
    with PatchworkClient("https://patchwork.example") as cli:
        projects = cli.projects()
    assert projects[0]["link_name"] == "netdevbpf"


@respx.mock
def test_checks_uses_unversioned_path():
    # Patchwork serves /api/patches/<id>/checks/ outside the /api/<ver>/ tree.
    respx.get("https://patchwork.example/api/patches/42/checks/").mock(
        return_value=Response(200, json=[{"context": "checkpatch", "state": "success"}])
    )
    with PatchworkClient("https://patchwork.example") as cli:
        checks = cli.checks(42)
    assert checks[0]["context"] == "checkpatch"


@respx.mock
def test_comments_validate_kind():
    with PatchworkClient("https://patchwork.example") as cli, pytest.raises(ValueError):
        cli.comments("bogus", 1)


@respx.mock
def test_4xx_raises_patchwork_error():
    respx.get("https://patchwork.example/api/1.2/patches/99/").mock(
        return_value=Response(404, text="Not found")
    )
    with (
        PatchworkClient("https://patchwork.example") as cli,
        pytest.raises(PatchworkError) as exc,
    ):
        cli.patch(99)
    assert exc.value.status == 404


@respx.mock
def test_auth_header_when_token_provided():
    route = respx.get("https://patchwork.example/api/1.2/projects/").mock(
        return_value=Response(200, json=[])
    )
    with PatchworkClient("https://patchwork.example", token="tok123") as cli:
        cli.projects()
    assert route.calls.last.request.headers["Authorization"] == "Token tok123"


@respx.mock
def test_params_strip_none():
    route = respx.get("https://patchwork.example/api/1.2/patches/").mock(
        return_value=Response(200, json=[])
    )
    with PatchworkClient("https://patchwork.example") as cli:
        cli.patches(project="netdevbpf", state=None, q="seg6")
    qs = route.calls.last.request.url.query.decode()
    assert "project=netdevbpf" in qs
    assert "q=seg6" in qs
    assert "state" not in qs
