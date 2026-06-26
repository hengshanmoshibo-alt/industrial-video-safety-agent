# Five-Minute Demo Script

This script is designed for interviews, portfolio reviews, and open-source
walkthroughs. It keeps the story focused on Agent behavior, not only video
classification.

## 0:00 - Positioning

This is an industrial safety inspection Agent. The goal is to turn inspection
video into an auditable safety workflow:

```text
video -> video memory -> VLM grounding -> policy decision -> alert/review/ticket -> verification
```

The important difference from a simple classifier is that the system stores
intermediate Agent state, evidence, tool calls, policy decisions, and review
outcomes.

## 0:45 - Seed The Demo

```bash
python scripts/dev.py doctor
python scripts/dev.py up
python scripts/dev.py seed
```

Open `http://localhost:5173` and log in with `admin / Admin123!`.

## 1:30 - Safety Inspection Page

Show:

- total audits,
- completed audits,
- high-risk alerts,
- human review count,
- ticket status,
- the seeded walkway obstruction audit.

Explain that the seeded demo does not require a paid VLM key, while real upload
mode can use `qwen3-vl-plus` or another OpenAI-compatible vision model.

## 2:15 - Evidence And Video Memory

Open the audit detail and show:

- risk timeline,
- bbox evidence,
- video memory segments,
- Chinese risk explanation and remediation advice.

The key point is that the Agent does not only say "unsafe". It records what it
saw, where it saw it, the time range, confidence, and evidence artifact.

## 3:00 - Agent Trace

Show the Agent execution trace:

- receive task,
- load video,
- sample frames,
- inspect safety frame,
- validate bbox,
- merge risk events,
- build video memory,
- decide safety action,
- write report,
- send Feishu alert,
- recommend remediation ticket.

Explain that each step has status, latency, input summary, output summary, and
artifact references. This is the observability layer that makes the workflow
reviewable.

## 4:00 - Human Review And Remediation

Show how uncertain findings can wait for human review. Then create a remediation
ticket for a confirmed high-risk audit and explain the post-remediation evidence
upload flow.

The product deliberately keeps high-risk alerting automatic, but leaves final
ticket creation and uncertain findings under supervisor control.

## 4:45 - Extension Points

Show:

```bash
python scripts/dev.py mcp-tools
```

Explain that the project exposes `inspect_safety_frame`, `query_video_memory`,
and `send_feishu_alert` as MCP tools, so another Agent can call the platform
without importing backend code.

## Close

The project demonstrates:

- multimodal Agent workflow,
- VLM grounding with bbox evidence,
- persisted video memory,
- tool-level Agent trace,
- policy-driven safety action,
- human-in-the-loop review,
- alert and remediation loop,
- MCP extension.

