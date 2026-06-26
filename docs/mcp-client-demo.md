# MCP Client Demo

The safety platform includes a lightweight MCP server so another Agent can call
the inspection capabilities as tools instead of using internal application APIs.

## Tools

| Tool | Purpose |
| --- | --- |
| `inspect_safety_frame` | Inspect one image with an OpenAI-compatible vision model and return risk findings with bbox data. |
| `query_video_memory` | Query stored video memory segments from the platform API. |
| `send_feishu_alert` | Send a signed Feishu alert from an Agent tool call. |

## Configure A Client

Use [examples/mcp_client_config.json](../examples/mcp_client_config.json) as a
template for Codex, Claude Desktop, Qwen-Agent, or another MCP-compatible client.

The required runtime values are:

| Variable | Required For |
| --- | --- |
| `SAFETY_AGENT_API_BASE` | Querying video memory. |
| `SAFETY_AGENT_TOKEN` | Authenticated platform API calls. |
| `VISION_BASE_URL`, `VISION_API_KEY`, `VISION_MODEL` | Direct frame inspection. |
| `FEISHU_WEBHOOK_URL`, `FEISHU_WEBHOOK_SECRET` | Alert delivery. |

## Run The Stdio Demo

Start the safety platform and seed one demo audit:

```bash
python scripts/dev.py up
python scripts/dev.py seed
```

Log in and copy the JWT token, or use the API client demo to inspect the latest
audit id:

```bash
python examples/api_client_demo.py
```

Then list MCP tools and query memory through the stdio protocol:

```bash
python examples/mcp_stdio_client_demo.py --audit-id 1 --token <jwt-token>
```

This validates the same tool boundary used by external Agent frameworks: the
MCP client initializes the server, lists tools, and calls `query_video_memory`
without importing backend application code.
