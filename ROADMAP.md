# Roadmap

The goal is to evolve this project from a strong vertical demo into a high-quality open-source Agent system.

## v1: Vertical Agent Application

- [x] Video upload and asynchronous processing
- [x] Qwen3-VL / OpenAI-compatible vision model integration
- [x] bbox evidence generation
- [x] AgentRun and AgentStep traces
- [x] VideoMemorySegment storage
- [x] SafetyPolicy decision center
- [x] Feishu alert integration
- [x] Human review and resume
- [x] Remediation tickets
- [x] Post-remediation verification
- [x] Evaluation panel
- [x] Lightweight MCP tools

## v2: High-Star Open Source Experience

- [ ] README screenshots and short demo GIF
- [ ] hosted sample video outputs with anonymized evidence
- [ ] GitHub Actions status badge
- [ ] one-command seed demo
- [ ] richer English and Chinese docs
- [ ] public benchmark report from open samples

## v3: Stronger Agent Architecture

- [ ] explicit state graph for Agent workflow
- [ ] durable resume from every state
- [ ] branch replay for failed tools
- [ ] tool-call retry policy and idempotency keys
- [ ] richer tracing view with artifacts and cost
- [ ] MCP client demo where another Agent calls this platform

## v4: Better Video Intelligence

- [ ] object-level video memory
- [ ] semantic search over memory segments
- [ ] temporal event retrieval
- [ ] bbox IoU evaluation when annotations exist
- [ ] OCR and sign detection tools
- [ ] optional segmentation evidence overlay

## v5: Production Hardening

- [ ] alert deduplication
- [ ] role-specific review queues
- [ ] audit export
- [ ] configurable retention policy
- [ ] observability dashboard
- [ ] deployment profiles for local, staging, and GPU worker

## Non-Goals

- Real-time CCTV streaming in the first open-source release
- Replacing certified safety systems
- Treating model output as a final violation conclusion without human review
