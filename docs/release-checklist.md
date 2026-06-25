# Release Checklist

Use this checklist before tagging a public demo release.

## Required Evidence

- CI is green on `main`.
- README demo GIF renders.
- `docker compose -f docker-compose.safety.yml config --quiet` passes.
- `pytest -q` passes.
- `frontend` production build passes.
- A deterministic seeded demo can be created from a clean database.
- At least one VLM-backed sample includes Chinese findings, bbox evidence, Agent steps, Feishu alert status, and ticket recommendation.

## Suggested Release Assets

- Demo GIF or short MP4.
- Smoke benchmark JSON.
- Public dataset evaluation JSON when available.
- Screenshots for dashboard, bbox evidence, risk timeline, Agent trace, remediation ticket, and evaluation panel.
- Model/provider configuration with secrets redacted.

## Release Notes Template

```markdown
## Industrial Video Safety Agent vX.Y.Z

### Highlights
- Multimodal video inspection with bbox grounding.
- Observable AgentRun and AgentStep trace.
- Video memory timeline.
- Safety policy decisions with Feishu alert and human review.
- Remediation ticket and post-remediation verification loop.
- MCP tools for external Agent integration.

### Validation
- CI: passing
- Backend tests: passing
- Frontend build: passing
- Compose config: passing
- Smoke benchmark: attached

### Known Limits
- The system is an inspection assistant, not a certified safety device.
- Public benchmark quality depends on the selected VLM/provider and dataset labels.
```
