# Open Source Strategy

This document captures what this project should learn from strong Agent repositories and how to move toward a high-star open-source project.

## Reference Projects

- Qwen-Agent: tool calling, memory, MCP/RAG direction, broad examples.
- LangGraph: durable state, human-in-the-loop, resumable workflows.
- VisionAgent: vision tasks as tools, grounding-first UX, generated visual evidence.
- VideoAgent: video memory first, reasoning second.
- OpenAI Agents SDK: tracing, guardrails, handoffs, clean developer experience.

## Current Strength

This repository is already stronger than a simple VLM demo because it has:

- vertical industrial safety scenario
- video upload and async worker
- VLM grounding with bbox evidence
- AgentRun and AgentStep observability
- video memory
- safety policy decision center
- Feishu alerting
- human review and resume
- remediation tickets
- post-remediation verification
- evaluation metrics
- lightweight MCP tools

## Gaps Against High-Star Agent Projects

| Area | Current state | Gap |
| --- | --- | --- |
| Agent planning | Fixed workflow | No dynamic planning or graph replay yet |
| Durable execution | Waiting states exist | No full state graph or retry policy |
| Video memory | Key-frame and risk memory | No semantic retrieval or object-level memory |
| Vision tools | VLM bbox grounding | No detector/OCR/segmentation tool router |
| Evaluation | Metrics panel | No public benchmark report with charts |
| Developer experience | Docker Compose and tests | Needs screenshots, demo GIF, CI badge, clearer examples |
| MCP | Server tools exist | Needs a client demo showing another Agent using the tools |

## High-Star Priorities

1. **First-screen clarity**
   - README should immediately explain the problem, workflow, and why it is not just a classifier.
   - Keep architecture diagram and quick start visible above deep docs.

2. **Visual proof**
   - Add screenshots for Safety Inspection, Agent Trace, Human Review, Ticket Verification, Evaluation.
   - Add one short GIF: upload video -> bbox evidence -> Feishu alert -> ticket.

3. **Reproducible demo**
   - Provide one command to seed an anonymized sample audit.
   - Provide one public sample video path and expected output.

4. **Benchmark credibility**
   - Run public samples and publish a small benchmark table:
     - processing success rate
     - bbox valid rate
     - high-risk alert count
     - average latency
     - false-positive examples

5. **Agent credibility**
   - Make state graph explicit in docs.
   - Show tool trace with input, output, latency, artifacts.
   - Add MCP client example.

6. **Contributor friendliness**
   - Keep CI green.
   - Tag good-first issues.
   - Keep docs current with API and screenshots.

## Next Milestone

The next release should be `v1.1-demo-polish`:

- README screenshots
- demo GIF
- sample seed command: done via `scripts/seed_demo_safety_agent.py`
- API client example: done via `examples/api_client_demo.py`
- CI badge after first GitHub Actions run
- benchmark report from 24 public samples
- MCP client demo that calls `services/safety-mcp-server`

## Current Demo Assets

- [Demo guide](demo.md)
- [Benchmark guide](benchmark.md)
- [API client example](../examples/api_client_demo.py)

## Messaging

Use this one-line pitch consistently:

> Multimodal Agent platform that turns industrial safety videos into grounded risk evidence, alerts, human review, remediation tickets, and verification workflows.

Chinese resume pitch:

> 基于视觉大模型构建工业安全巡检多模态 Agent，实现视频风险识别、bbox 证据框选、Agent 执行轨迹、飞书告警、人工复核、整改工单和复检闭环。
