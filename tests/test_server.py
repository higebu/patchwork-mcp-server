from __future__ import annotations

import respx
from httpx import Response

import patchwork_mcp_server.server as server
from patchwork_mcp_server.server import (
    find_by_msgid as find_by_msgid_fn,
)
from patchwork_mcp_server.server import (
    get_checks as get_checks_fn,
)
from patchwork_mcp_server.server import (
    get_comments as get_comments_fn,
)
from patchwork_mcp_server.server import (
    get_patch as get_patch_fn,
)
from patchwork_mcp_server.server import (
    get_series as get_series_fn,
)
from patchwork_mcp_server.server import (
    list_projects as list_projects_fn,
)
from patchwork_mcp_server.server import (
    recent_series as recent_series_fn,
)
from patchwork_mcp_server.server import (
    search_patches as search_patches_fn,
)


@respx.mock
def test_list_projects_returns_compact_shape():
    respx.get("https://patchwork.example/api/1.2/projects/").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 399,
                    "link_name": "netdevbpf",
                    "name": "Netdev + BPF",
                    "list_id": "bpf.vger.kernel.org",
                    "extra": "dropped",
                }
            ],
        )
    )
    result = list_projects_fn()
    assert result == [
        {
            "id": 399,
            "link_name": "netdevbpf",
            "name": "Netdev + BPF",
            "list_id": "bpf.vger.kernel.org",
        }
    ]


@respx.mock
def test_find_by_msgid_strips_brackets_and_aggregates():
    respx.get(
        "https://patchwork.example/api/1.2/patches/",
        params={"msgid": "abc@example"},
    ).mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 1,
                    "name": "[v2,1/2] foo",
                    "state": "new",
                    "project": {"link_name": "netdevbpf"},
                    "submitter": {"name": "Alice"},
                    "msgid": "<abc@example>",
                    "date": "2026-05-04T00:00:00",
                }
            ],
        )
    )
    respx.get(
        "https://patchwork.example/api/1.2/covers/",
        params={"msgid": "abc@example"},
    ).mock(return_value=Response(200, json=[]))

    out = find_by_msgid_fn("<abc@example>")
    assert out["patches"][0]["project"] == "netdevbpf"
    assert out["covers"] == []


@respx.mock
def test_get_series_aggregates_patch_states():
    respx.get("https://patchwork.example/api/1.2/series/77/").mock(
        return_value=Response(
            200,
            json={
                "id": 77,
                "name": "demo",
                "version": 2,
                "date": "2026-05-04T00:00:00",
                "received_total": 2,
                "total": 2,
                "project": {"link_name": "netdevbpf"},
                "submitter": {"name": "Alice"},
                "cover_letter": {"id": 700, "msgid": "<c@x>", "name": "[v2,0/2] demo"},
                "patches": [{"id": 11}, {"id": 12}],
            },
        )
    )
    for pid, state in [(11, "changes-requested"), (12, "changes-requested")]:
        respx.get(f"https://patchwork.example/api/1.2/patches/{pid}/").mock(
            return_value=Response(
                200,
                json={
                    "id": pid,
                    "name": f"patch {pid}",
                    "state": state,
                    "delegate": {"username": "netdev"},
                    "archived": False,
                    "msgid": f"<p{pid}@x>",
                    "check": "fail",
                },
            )
        )

    s = get_series_fn(77)
    assert s["received"] == "2/2"
    assert s["cover_letter"]["id"] == 700
    assert {p["state"] for p in s["patches"]} == {"changes-requested"}
    assert all(p["delegate"] == "netdev" for p in s["patches"])


@respx.mock
def test_get_patch_includes_series_and_summary():
    respx.get("https://patchwork.example/api/1.2/patches/42/").mock(
        return_value=Response(
            200,
            json={
                "id": 42,
                "name": "[v2,1/2] foo",
                "state": "new",
                "archived": False,
                "delegate": {"username": "netdev"},
                "submitter": {"name": "Alice", "email": "a@x"},
                "project": {"link_name": "netdevbpf"},
                "msgid": "<42@x>",
                "date": "2026-05-04T00:00:00",
                "tags": {"Reviewed-by": 1},
                "check": "warning",
                "series": [{"id": 77, "name": "demo", "version": 2}],
            },
        )
    )
    p = get_patch_fn(42)
    assert p["delegate"] == "netdev"
    assert p["series"] == [{"id": 77, "name": "demo", "version": 2}]
    assert p["check_summary"] == "warning"


@respx.mock
def test_get_checks_fail_only_filters_states():
    respx.get("https://patchwork.example/api/patches/42/checks/").mock(
        return_value=Response(
            200,
            json=[
                {"context": "checkpatch", "state": "success", "description": "ok"},
                {"context": "sashiko-gemini", "state": "fail", "description": "critical"},
                {"context": "series_format", "state": "warning", "description": "no tree"},
            ],
        )
    )
    all_checks = get_checks_fn(42)
    assert len(all_checks) == 3
    failing = get_checks_fn(42, fail_only=True)
    assert {c["context"] for c in failing} == {"sashiko-gemini", "series_format"}


@respx.mock
def test_get_comments_preview_truncation():
    respx.get("https://patchwork.example/api/covers/700/comments/").mock(
        return_value=Response(
            200,
            json=[
                {
                    "date": "2026-05-04T00:00:00",
                    "submitter": {"name": "Kuba", "email": "k@x"},
                    "msgid": "<reply@x>",
                    "content": "\n".join(f"line {i}" for i in range(50)),
                }
            ],
        )
    )
    out = get_comments_fn("cover", 700, preview_lines=10)
    assert len(out) == 1
    assert out[0]["truncated"] is True
    assert out[0]["preview"].count("\n") == 9


@respx.mock
def test_recent_series_collapse_keeps_highest_version():
    respx.get(
        "https://patchwork.example/api/1.2/covers/",
        params={"project": "netdevbpf"},
    ).mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 200,
                    "name": "[v2,0/2] foo",
                    "msgid": "<v2@x>",
                    "date": "2026-05-04T00:00:00",
                    "project": {"link_name": "netdevbpf"},
                    "submitter": {"name": "Alice"},
                    "series": [{"id": 22, "name": "foo", "version": 2}],
                },
                {
                    "id": 100,
                    "name": "[0/2] foo",
                    "msgid": "<v1@x>",
                    "date": "2026-05-03T00:00:00",
                    "project": {"link_name": "netdevbpf"},
                    "submitter": {"name": "Alice"},
                    "series": [{"id": 11, "name": "foo", "version": 1}],
                },
            ],
        )
    )
    out = recent_series_fn(project="netdevbpf", collapse_revisions=True)
    assert len(out) == 1
    assert out[0]["version"] == 2


@respx.mock
def test_search_patches_passes_filters():
    route = respx.get("https://patchwork.example/api/1.2/patches/").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 5,
                    "name": "[v2,1/2] seg6: add foo",
                    "state": "new",
                    "project": {"link_name": "netdevbpf"},
                    "submitter": {"name": "Alice"},
                    "msgid": "<5@x>",
                    "date": "2026-05-04T00:00:00",
                }
            ],
        )
    )
    out = search_patches_fn(query="seg6", project="netdevbpf", state="new")
    assert len(out) == 1
    qs = route.calls.last.request.url.query.decode()
    assert "q=seg6" in qs
    assert "project=netdevbpf" in qs
    assert "state=new" in qs


def test_client_singleton_resets_between_tests():
    assert server._client is None
