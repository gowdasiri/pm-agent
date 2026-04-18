# Product Memory MCP Server

This repository starts the Product Memory Layer as a local Model Context Protocol (MCP) server.

## What exists today

- A stdio MCP server implemented without third-party runtime dependencies
- A persistent JSON-backed store for feature memory records
- An HTTP MCP endpoint for remote URL-based clients
- Jira and Confluence integration hooks for live sync from Atlassian Cloud
- Feature memory views, rendered memory pages, and graph outputs

## Run locally

```bash
python3 -m product_memory_mcp.server
```

Or after installation:

```bash
pip install -e .
product-memory-mcp
```

To run the remote URL version locally:

```bash
python3 -m product_memory_mcp.http_server
```

Then post MCP JSON-RPC requests to:

```text
http://localhost:8000/mcp
```

Health endpoint:

```text
http://localhost:8000/health
```

## Required Environment Variables

For Atlassian sync:

```bash
export ATLASSIAN_BASE_URL="https://your-company.atlassian.net"
export ATLASSIAN_EMAIL="you@company.com"
export ATLASSIAN_API_TOKEN="your-api-token"
```

Optional local storage override:

```bash
export PRODUCT_MEMORY_STORE_PATH=/absolute/path/to/store.json
```

## Hosting

This repo includes:

- `Dockerfile`
- `render.yaml`

The fastest deploy path is Render:

1. Create a new Render Web Service from this repo.
2. Let Render use `render.yaml`.
3. Set:
   - `ATLASSIAN_BASE_URL`
   - `ATLASSIAN_EMAIL`
   - `ATLASSIAN_API_TOKEN`
4. Deploy.
5. Use the MCP URL:
   - `https://<your-render-service>.onrender.com/mcp`

## MCP Capabilities

Tools include:

- `health_check`
- `get_atlassian_integration_status`
- `upsert_feature`
- `get_feature`
- `record_artifact`
- `add_evidence`
- `add_decision`
- `add_dependency`
- `list_feature_decisions`
- `get_feature_memory`
- `get_feature_graph`
- `ingest_jira_issue_event`
- `ingest_confluence_page_event`
- `sync_jira_issue`
- `sync_confluence_page`

Resources include:

- `memory://features`
- `memory://feature/<feature_id>`
- `memory://feature/<feature_id>/page`
- `memory://feature/<feature_id>/graph`
- `memory://feature/<feature_id>/graph-text`
