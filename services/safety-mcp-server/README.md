# Safety MCP Server

Lightweight MCP tools for the industrial safety inspection Agent.

Tools:

- `inspect_safety_frame`: call an OpenAI-compatible vision model for one image.
- `query_video_memory`: query stored video memory through the platform API.
- `send_feishu_alert`: send a Feishu text alert with optional webhook signing.

Environment:

```bash
SAFETY_AGENT_API_BASE=http://localhost:8000/api
SAFETY_AGENT_TOKEN=
VISION_BASE_URL=
VISION_API_KEY=
VISION_MODEL=qwen3-vl-plus
FEISHU_WEBHOOK_URL=
FEISHU_WEBHOOK_SECRET=
```

Run:

```bash
python services/safety-mcp-server/server.py
```

Client examples:

- [examples/mcp_client_config.json](../../examples/mcp_client_config.json)
- [examples/mcp_stdio_client_demo.py](../../examples/mcp_stdio_client_demo.py)
- [docs/mcp-client-demo.md](../../docs/mcp-client-demo.md)
