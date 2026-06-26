# ADR-0001: Lightweight Persisted Agent Workflow

## Status

Accepted

## Context

The project needs to demonstrate Agent behavior in a way that is understandable
and reliable for a portfolio demo. Frameworks such as LangGraph provide durable
execution and human-in-the-loop patterns, but adding a full graph runtime early
would increase dependency and operational complexity.

The existing platform already has FastAPI services, PostgreSQL, Redis, and a
video worker. The first priority is to make the workflow observable and
recoverable enough for real demos.

## Decision

Implement a lightweight persisted Agent workflow using application models:

- `VideoAuditAgentRun`
- `VideoAuditAgentStep`
- `VideoMemorySegment`
- `VideoAuditReview`
- `VideoAuditAlertEvent`
- `TicketVerification`

Each tool call writes an `AgentStep` with status, latency, input summary, output
summary, artifact references, and error state. The `AgentRun` stores current
stage, paused reason, status, and final decision.

## Consequences

Benefits:

- Easy to inspect in the UI and database.
- No heavy framework dependency for the core demo.
- The workflow remains compatible with future LangGraph-style migration.
- Tests can validate business contracts without running a graph runtime.

Tradeoffs:

- Branching and replay are implemented manually.
- Advanced graph features such as checkpoint stores and graph visualization are
  not provided by a framework yet.

## Follow-Up

Add an explicit state graph representation once the core workflow stabilizes.

