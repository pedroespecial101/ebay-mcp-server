# eBay Seller MCP Agent Instructions

## Start here

- Resolve project ID `ebay-mcp-server` through Agent Context MCP and read its
  ordered start context before project work.
- Read this repository's README and relevant files under `docs/`; the `docs/`
  symlink points to the canonical Agent Context documentation.
- If Agent Context MCP is unavailable, use `~/Projects/Agent-Context` and
  report its source status. Do not silently substitute stale copied docs.
- Listing Studio checkout: `../ebay-listing-studio`.

## Boundaries

- This MCP contains both read-only `research_*` tools and seller tools that can
  change live eBay data. Keep research credentials and seller OAuth credentials
  separate as documented.
- Never expose or copy secret values. Runtime credentials belong to Doppler
  project `ebay-mcp`, config `dev`; do not create a local `.env` for this
  development setup.
- The Listing Studio dependency and its guarded publication boundary remain
  distinct from the seller MCP's lower-level mutation tools.
- OCI is the current live development runtime. The seller container and
  Tailscale sidecar were observed running on 27 September 2026; the exact
  image build commit and seller business-tool acceptance remain unverified.
  Verify current host state and the Agent Context OCI record before runtime
  or deployment work.

## Safe validation

- Focused safe test: `.venv/bin/python -m pytest tests/test_credentials_and_defaults.py`.
- Do not run legacy inventory or offer integration tests as a generic smoke
  suite; they can create, publish, withdraw, or delete real account data.
- Doppler-backed MCP discovery/live smoke checks and seller mutations require a
  separately authorized task and current credential/runtime verification.

## Git handoff

- Before a new task, inspect this checkout's branch, working tree, upstream,
  unpushed commits, and other worktrees. Finish or explicitly park earlier work
  before starting an unrelated branch; preserve unknown changes.
- Use a focused `codex/` branch for changes. At a safe checkpoint, commit and
  push only this task's files. Report the branch, commit, PR, checks, and any
  unfinished work at handoff. Keep cross-repository commits and PRs separate.
- A Git merge does not deploy the OCI container or prove seller-tool
  acceptance. Follow the separate live-operation rules above.

## Deferred fulfillment work

`codex/wip-fulfillment-orders` is an intentionally unmerged read-only order
exploration. Do not deploy or merge it until its namespace, date-window
validation, data-minimisation contract, client access boundary, and seller
reauthorisation requirement have been reviewed.
