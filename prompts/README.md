# Prompt Contracts

This directory contains the public prompt and output schema used by the
industrial safety VLM grounding tool.

| File | Purpose |
| --- | --- |
| [safety_inspection_skill.md](safety_inspection_skill.md) | Chinese VLM instruction for frame-level risk grounding. |
| [safety_findings.schema.json](safety_findings.schema.json) | JSON Schema for the expected VLM output. |

The worker and MCP server both load the shared prompt so the product workflow
and external Agent tools use the same recognition contract.

Validate the prompt contract with:

```bash
python scripts/dev.py prompt-check
```

