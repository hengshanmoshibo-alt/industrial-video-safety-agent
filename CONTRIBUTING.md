# Contributing

Thanks for helping improve Industrial Video Safety Agent.

## Development Setup

1. Copy environment template:

   ```bash
   cp .env.example .env
   ```

2. Start the safety-only stack:

   ```bash
   docker compose -f docker-compose.safety.yml up -d --build
   ```

3. Run checks before opening a pull request:

   ```bash
   pytest -q
   cd frontend
   npm run build
   ```

## Useful Areas

- Safety policies for new risk classes
- Better VLM prompts and JSON validation
- Evaluation scripts and public dataset adapters
- Evidence visualization and bbox quality checks
- Video memory retrieval
- MCP clients and tool integrations
- Frontend UX polish

## Pull Request Guidelines

- Keep changes scoped and explain the user-visible impact.
- Do not commit API keys, webhook URLs, private videos, datasets, model weights, or generated evidence files.
- Include tests when changing workflow logic, policy decisions, API contracts, or model output parsing.
- Update README or docs for new public behavior.

## Safety Guidelines

This repository is an inspection assistant, not a certified safety system. When adding prompts or policies, avoid language that presents model output as a final legal or safety conclusion. Human review must remain visible for high-risk and uncertain cases.
