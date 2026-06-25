# Examples

Small integration examples for the Industrial Video Safety Agent.

## API Client Demo

After starting the stack and seeding the demo:

```bash
docker compose -p aicoding -f docker-compose.safety.yml up -d --build
docker compose -p aicoding -f docker-compose.safety.yml exec video-audit-service \
  python /app/scripts/seed_demo_safety_agent.py
```

Run:

```bash
python examples/api_client_demo.py
```

The script logs in, prints evaluation metrics, fetches the latest audit, and prints the Agent explanation plus video memory summary.

## Why Examples Matter

The production UI is useful for demos, but examples make the project easier to embed into other Agents or automation workflows.
