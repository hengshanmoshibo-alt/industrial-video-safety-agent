# ADR-0004: Use MCP As An Extension Layer

## Status

Accepted

## Context

MCP is useful for exposing tools to external Agents, but the safety platform
still needs stable backend APIs, database persistence, tenant controls, and
business workflows. Replacing the core backend flow with MCP would make the
main product harder to operate and test.

## Decision

Keep the product runtime inside FastAPI services and workers. Provide a
lightweight MCP server as an extension layer exposing selected tools:

- `inspect_safety_frame`
- `query_video_memory`
- `send_feishu_alert`

The MCP server calls the same platform APIs or model providers used by the main
system, but it does not own the core workflow state.

## Consequences

Benefits:

- External Agents can reuse the safety capabilities.
- The main product remains stable and testable through HTTP APIs.
- MCP can evolve independently from the core service contracts.

Tradeoffs:

- MCP clients need their own authentication and environment configuration.
- Not every backend function is exposed as a tool.

## Follow-Up

Add a second-Agent demo where an external Agent queries video memory, asks for
extra evidence, and sends a review reminder.

