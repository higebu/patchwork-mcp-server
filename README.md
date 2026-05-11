# patchwork-mcp-server

A Model Context Protocol (MCP) server that exposes the
[Patchwork](https://patchwork.kernel.org) REST API to LLM-based coding
agents (Claude Code, Claude Desktop, Cursor, etc.).

It is a thin, **read-only** wrapper around `/api/1.2/` so you can ask the
agent things like:

- "What's the state of my latest `seg6:` series on netdev?"
- "Show me failing CI checks on patch 14553325."
- "List the cover-letter thread for series 1089407."
- "Find the patch with Message-Id `20260505-seg6-mobile-v2-0-...`."

Without this server, the same questions either require a working
`~/.pwclientrc` (which has trouble with CI checks and comment threads)
or hand-rolled `curl` against the REST API.

## Install

Requires Python 3.10+. Install with [uv](https://docs.astral.sh/uv/):

```bash
# From PyPI (preferred once published)
uv tool install patchwork-mcp-server

# From a local checkout
uv tool install .

# From a Git remote
uv tool install git+https://github.com/higebu/patchwork-mcp-server
```

The package installs a `patchwork-mcp-server` executable into `~/.local/bin/`. To
refresh an existing install after editing source locally:

```bash
uv tool install --reinstall .
```

## Configuration

| Variable                | Default                        | Purpose                            |
|-------------------------|--------------------------------|------------------------------------|
| `PATCHWORK_URL`         | `https://patchwork.kernel.org` | Base URL of the Patchwork instance |
| `PATCHWORK_API_VERSION` | `1.2`                          | REST API version segment           |

Read-only access to public Patchwork instances needs no credentials.

## Connect to Claude Code

After `uv tool install`, the executable is on your `PATH`, so registration
needs no path:

```bash
claude mcp add patchwork-mcp-server -- patchwork-mcp-server
```

For Claude Desktop, add it to `~/.config/claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "patchwork": {
      "command": "patchwork-mcp-server"
    }
  }
}
```

## Tools

| Tool             | Purpose                                                                    |
|------------------|----------------------------------------------------------------------------|
| `list_projects`  | List Patchwork projects on the instance.                                   |
| `find_by_msgid`  | Look up patches/covers by Message-Id (works across projects).              |
| `get_series`     | Series with every patch's state, delegate, archived flag, check summary.   |
| `get_patch`      | Single patch with submitter, tags, series links, check summary.            |
| `get_checks`     | CI checks for a patch (checkpatch, build_*, sashiko-*, contest, ...). Optional `fail_only`. |
| `get_comments`   | Comment thread on a cover letter or patch (time-ordered, body preview).    |
| `recent_series`  | Recent cover letters on a project, optional submitter filter, optional revision collapse. |
| `search_patches` | Substring search over patch names, with project/state/submitter filters.   |

## Example interaction

> What's the state of my SRv6 Mobile series on netdev?

Behind the scenes the agent calls:

1. `find_by_msgid("20260505-seg6-mobile-v2-0-9e8022bdfdb6@gmail.com")`
   to discover series id `1089407` on `netdevbpf`.
2. `get_series(1089407)` for the per-patch state table.
3. `get_checks(<lead_patch>, fail_only=True)` to triage CI.
4. `get_comments("cover", 14117478)` to read the thread.

## Development

```bash
cd patchwork-mcp-server
uv sync --group dev
just check          # ruff lint + format check + pytest
```

`just release patch` bumps the version, regenerates `CHANGELOG.md` via
`git-cliff`, and tags locally. Push the tag to trigger the PyPI release
workflow.

## License

MIT
