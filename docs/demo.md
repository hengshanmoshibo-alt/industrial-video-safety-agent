# Demo Guide

This guide is optimized for reviewers who clone the repository and want to see the Agent workflow quickly.

## Three-Minute Seeded Demo

Start the safety-only stack:

```bash
python scripts/dev.py up
```

Seed one deterministic inspection:

```bash
python scripts/dev.py seed
```

Open the product:

```text
http://localhost:5173
admin / Admin123!
```

Expected result:

- Safety Inspection shows one completed high-risk audit.
- The detail drawer shows a single red bbox around a metal coil blocking a marked walkway.
- Agent Trace shows tool-level steps from video loading to ticket recommendation.
- Feishu Alert shows a seeded `sent` alert event. This does not call a real Feishu webhook.
- The remediation ticket has not been created by default, so you can click Create Ticket during a live demo.

To seed the same demo with a ticket already created:

```bash
python scripts/dev.py seed --with-ticket
```

## Real VLM Demo

Configure `.env`:

```env
VISION_ENABLED=true
VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
VISION_API_KEY=your_key_here
VISION_MODEL=qwen3-vl-plus
```

Then upload a public sample video from the Safety Inspection page. The worker will:

1. sample frames with FFmpeg,
2. call the VLM for Chinese risk grounding and bbox coordinates,
3. validate bbox quality,
4. build video memory,
5. apply the safety policy,
6. send Feishu alert if configured,
7. wait for supervisor ticket confirmation or human review.

## Screenshot Checklist

For a GitHub README or release page, capture these five screens:

- Safety Inspection list with high-risk audit.
- Detail drawer showing bbox evidence.
- Agent Trace timeline with tool latency.
- Human Review view with confirmed / false-positive / needs-more-evidence choices.
- Remediation Ticket page with post-remediation evidence upload.

## Demo Reset

The seed script is idempotent. Re-running it removes only the previous audit whose file name is `demo_walkway_violation.mp4` and recreates it. It does not delete uploaded user videos.
