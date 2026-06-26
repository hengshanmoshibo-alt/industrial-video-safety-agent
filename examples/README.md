# Examples

Small integration examples for the Industrial Video Safety Agent.

## API Client Demo

After starting the stack and seeding the demo:

```bash
python scripts/dev.py up
python scripts/dev.py seed
```

Run:

```bash
python scripts/dev.py api-demo
```

The script logs in, prints evaluation metrics, fetches the latest audit, and prints the Agent explanation plus video memory summary.

## MCP Stdio Client Demo

The repository also includes a minimal MCP client that talks to the safety MCP
server over the stdio JSON-RPC transport:

```bash
python examples/mcp_stdio_client_demo.py --audit-id 1 --token <jwt-token>
```

Use [mcp_client_config.json](mcp_client_config.json) as a starting point for
MCP-compatible desktop clients or Agent frameworks. See
[../docs/mcp-client-demo.md](../docs/mcp-client-demo.md) for the full setup.

## Why Examples Matter

The production UI is useful for demos, but examples make the project easier to embed into other Agents or automation workflows.
