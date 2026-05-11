# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
## [0.1.0] - 2026-05-11

### Features
- initial read-only MCP server for Patchwork REST API
- tools: list_projects, find_by_msgid, get_series, get_patch, get_checks, get_comments, recent_series, search_patches

### CI
- ruff lint + pytest on push / pull_request
- tag-driven release workflow with PyPI trusted publishing and git-cliff release notes

