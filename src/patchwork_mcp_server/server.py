from __future__ import annotations

import os
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from patchwork_mcp_server.client import PatchworkClient

mcp = FastMCP("patchwork-mcp")

_client: PatchworkClient | None = None


def _get_client() -> PatchworkClient:
    global _client
    if _client is None:
        _client = PatchworkClient(
            base_url=os.environ.get("PATCHWORK_URL", "https://patchwork.kernel.org"),
            api_version=os.environ.get("PATCHWORK_API_VERSION", "1.2"),
        )
    return _client


def _compact_patch(p: dict) -> dict:
    return {
        "id": p["id"],
        "name": p["name"],
        "state": p["state"],
        "project": p.get("project", {}).get("link_name"),
        "msgid": p["msgid"],
        "date": p["date"],
        "submitter": p.get("submitter", {}).get("name"),
    }


def _compact_cover(c: dict) -> dict:
    series = (c.get("series") or [{}])[0]
    return {
        "cover_id": c["id"],
        "name": c["name"],
        "series_id": series.get("id"),
        "series_name": series.get("name"),
        "version": series.get("version", 1),
        "project": c.get("project", {}).get("link_name"),
        "msgid": c["msgid"],
        "date": c["date"],
        "submitter": c.get("submitter", {}).get("name"),
    }


def _full_patch(p: dict) -> dict:
    return {
        "id": p["id"],
        "name": p["name"],
        "state": p["state"],
        "archived": p["archived"],
        "delegate": (p.get("delegate") or {}).get("username"),
        "submitter": p.get("submitter", {}).get("name"),
        "submitter_email": p.get("submitter", {}).get("email"),
        "project": p.get("project", {}).get("link_name"),
        "msgid": p["msgid"],
        "date": p["date"],
        "tags": p.get("tags") or {},
        "check_summary": p.get("check"),
        "series": [
            {"id": s["id"], "name": s["name"], "version": s.get("version")}
            for s in (p.get("series") or [])
        ],
        "list_archive_url": p.get("list_archive_url"),
        "web_url": p.get("web_url"),
    }


@mcp.tool()
def list_projects() -> list[dict]:
    """List Patchwork projects available on the configured instance.

    Returns id, link_name (used as ?project= filter), display name, and list_id.
    """
    return [
        {
            "id": p["id"],
            "link_name": p["link_name"],
            "name": p["name"],
            "list_id": p.get("list_id"),
        }
        for p in _get_client().projects()
    ]


@mcp.tool()
def find_by_msgid(
    msgid: Annotated[
        str,
        Field(description="Message-Id with or without angle brackets"),
    ],
) -> dict:
    """Look up patches and cover letters by Message-Id across all projects.

    A single Message-Id can appear under multiple projects (e.g. netdevbpf
    and linux-kselftest). Use this to discover the projects + series ids
    before drilling in.
    """
    msgid = msgid.strip().lstrip("<").rstrip(">")
    cli = _get_client()
    patches = cli.patches(msgid=msgid)
    covers = cli.covers(msgid=msgid)
    return {
        "patches": [_compact_patch(p) for p in patches],
        "covers": [_compact_cover(c) for c in covers],
    }


@mcp.tool()
def get_series(series_id: int) -> dict:
    """Get a series with every patch's state, delegate, and archived flag.

    Use this after find_by_msgid to see the whole patchset at once.
    """
    cli = _get_client()
    s = cli.series(series_id)
    patches = []
    for ref in s.get("patches", []):
        full = cli.patch(ref["id"])
        patches.append(
            {
                "id": full["id"],
                "name": full["name"],
                "state": full["state"],
                "delegate": (full.get("delegate") or {}).get("username"),
                "archived": full.get("archived"),
                "msgid": full["msgid"],
                "check": full.get("check"),
            }
        )
    cover = s.get("cover_letter") or {}
    return {
        "id": s["id"],
        "name": s["name"],
        "version": s.get("version"),
        "date": s.get("date"),
        "received": f"{s.get('received_total')}/{s.get('total')}",
        "project": (s.get("project") or {}).get("link_name"),
        "submitter": (s.get("submitter") or {}).get("name"),
        "cover_letter": (
            {"id": cover.get("id"), "msgid": cover.get("msgid"), "name": cover.get("name")}
            if cover
            else None
        ),
        "patches": patches,
    }


@mcp.tool()
def get_patch(patch_id: int) -> dict:
    """Get a single patch with submitter, delegate, state, tags, and check summary."""
    return _full_patch(_get_client().patch(patch_id))


@mcp.tool()
def get_checks(
    patch_id: int,
    fail_only: Annotated[
        bool,
        Field(description="Return only checks in 'fail' or 'warning' state"),
    ] = False,
) -> list[dict]:
    """Get CI check results for a patch (checkpatch, build_*, sashiko-*, contest, ...).

    Pair with get_patch's check_summary to triage failing series quickly.
    """
    items = _get_client().checks(patch_id)
    if fail_only:
        items = [c for c in items if c.get("state") in ("fail", "warning")]
    return [
        {
            "context": c.get("context"),
            "state": c.get("state"),
            "description": c.get("description"),
            "target_url": c.get("target_url") or None,
            "date": c.get("date"),
        }
        for c in items
    ]


@mcp.tool()
def get_comments(
    kind: Annotated[Literal["cover", "patch"], Field(description="Comments target type")],
    id: Annotated[int, Field(description="Cover-letter id or patch id")],
    preview_lines: Annotated[
        int,
        Field(description="Lines of body to include per comment (use 0 for no body)"),
    ] = 30,
) -> list[dict]:
    """Get the comment thread on a cover letter or a patch, time-ordered."""
    items = _get_client().comments(kind, id)
    out = []
    for c in items:
        body = c.get("content") or ""
        if preview_lines > 0:
            lines = body.splitlines()
            preview = "\n".join(lines[:preview_lines])
            truncated = len(lines) > preview_lines
        else:
            preview = ""
            truncated = bool(body)
        out.append(
            {
                "date": c.get("date"),
                "submitter": (c.get("submitter") or {}).get("name"),
                "email": (c.get("submitter") or {}).get("email"),
                "msgid": c.get("msgid"),
                "preview": preview,
                "truncated": truncated,
            }
        )
    return out


@mcp.tool()
def recent_series(
    project: Annotated[
        str,
        Field(description="Project link_name (e.g. 'netdevbpf', 'linux-kselftest')"),
    ],
    submitter: Annotated[
        str | None,
        Field(description="Submitter name/email substring (resolved via /people/)"),
    ] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 20,
    collapse_revisions: Annotated[
        bool,
        Field(description="Keep only the highest version per series name"),
    ] = False,
) -> list[dict]:
    """List recent cover letters on a project, optionally filtered by submitter.

    With collapse_revisions=True, older revisions of the same series name
    are dropped so you only see the latest version of each topic.
    """
    cli = _get_client()
    params: dict = {"project": project}
    if submitter:
        people = cli.people(submitter)
        if not people:
            return []
        params["submitter"] = people[0]["id"]
    covers = cli.covers(**params)
    items = [_compact_cover(c) for c in covers]
    if collapse_revisions:
        seen: dict[str, dict] = {}
        for s in items:
            key = (s.get("series_name") or s["name"]).lower()
            prev = seen.get(key)
            if prev is None or (s.get("version") or 1) > (prev.get("version") or 1):
                seen[key] = s
        items = sorted(seen.values(), key=lambda x: x.get("date", ""), reverse=True)
    return items[:limit]


@mcp.tool()
def search_patches(
    query: Annotated[str, Field(description="Substring matched against patch name")],
    project: Annotated[
        str | None,
        Field(description="Project link_name to scope the search"),
    ] = None,
    state: Annotated[
        str | None,
        Field(description="State slug (e.g. 'new', 'changes-requested', 'accepted')"),
    ] = None,
    submitter: Annotated[str | None, Field(description="Submitter name/email substring")] = None,
    archived: Annotated[bool | None, Field(description="Filter by archived flag")] = None,
    limit: Annotated[int, Field(ge=1, le=100)] = 30,
) -> list[dict]:
    """Search patches by name substring with optional project/state/submitter filters."""
    cli = _get_client()
    params: dict = {"q": query}
    if project:
        params["project"] = project
    if state:
        params["state"] = state
    if archived is not None:
        params["archived"] = "true" if archived else "false"
    if submitter:
        people = cli.people(submitter)
        if not people:
            return []
        params["submitter"] = people[0]["id"]
    return [_compact_patch(p) for p in cli.patches(**params)[:limit]]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
