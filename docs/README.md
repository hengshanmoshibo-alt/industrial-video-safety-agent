# Documentation

Start here if you are reviewing, running, or extending the Industrial Video
Safety Agent.

## Run And Demo

| Document | Purpose |
| --- | --- |
| [Demo Guide](demo.md) | Three-minute seeded demo and real VLM demo checklist. |
| [Developer Commands](developer-commands.md) | One-command local development and verification flow. |
| [Demo Script](demo-script.md) | Five-minute presentation script for interviews and project reviews. |
| [Deployment](deployment.md) | Deployment notes and environment variables. |

## Architecture And APIs

| Document | Purpose |
| --- | --- |
| [Architecture](architecture.md) | Service layout and request flow. |
| [Agent State Graph](agent-state-graph.md) | Machine-readable workflow spec and state diagram. |
| [Video Safety Agent](video-safety-agent.md) | Product and technical design for the video Agent. |
| [API](api.md) | Main API surface. |
| [MCP Client Demo](mcp-client-demo.md) | External Agent integration through MCP tools. |

## Evaluation And Governance

| Document | Purpose |
| --- | --- |
| [Benchmark](benchmark.md) | Smoke benchmark and public dataset evaluation guidance. |
| [Data Sources](data-sources.md) | Public dataset references. |
| [Model Governance](model-governance.md) | Model configuration and governance notes. |
| [Knowledge Governance](knowledge-governance.md) | Governance patterns inherited from the original platform. |
| [Release Checklist](release-checklist.md) | Public release readiness checklist. |

## Design Decisions

| ADR | Decision |
| --- | --- |
| [ADR-0001](adr/0001-lightweight-agent-workflow.md) | Use a lightweight persisted Agent workflow instead of a framework dependency. |
| [ADR-0002](adr/0002-video-memory-first.md) | Build video memory before final risk reasoning. |
| [ADR-0003](adr/0003-policy-decision-center.md) | Separate VLM perception from business safety decisions. |
| [ADR-0004](adr/0004-mcp-as-extension.md) | Expose MCP as an extension layer, not the core runtime. |
