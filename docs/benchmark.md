# Benchmark And Evaluation

This project exposes two evaluation layers:

- **Smoke evaluation**: prove the full Agent workflow can create audit, evidence, memory, alert, report, and ticket recommendation.
- **Dataset evaluation**: run public industrial safety videos through the API or local model.

## Local Smoke Benchmark

Use the deterministic seeded demo:

```bash
docker compose -p aicoding -f docker-compose.safety.yml up -d --build
docker compose -p aicoding -f docker-compose.safety.yml exec video-audit-service \
  python /app/scripts/seed_demo_safety_agent.py
```

Then open the Evaluation Panel or call:

```bash
curl http://localhost:8000/api/video-audits/metrics/evaluation \
  -H "Authorization: Bearer <token>"
```

Expected smoke properties:

| Metric | Expected |
| --- | --- |
| Processing success | 1 seeded completed audit |
| Bbox validity | 1 high-risk finding with bbox |
| Alert event | 1 seeded Feishu alert record |
| Human review | 0 by default |
| Remediation ticket | 0 by default, created during demo |
| Verification | 0 until post-remediation evidence is uploaded |

The smoke benchmark is not a model-quality benchmark. It verifies product and Agent workflow integrity.

## Public Dataset Benchmark

Download public safety videos:

```bash
python scripts/download_safety_dataset.py
```

Run API evaluation:

```bash
python scripts/evaluate_safety_agent.py --mode api --max-samples 24
```

The evaluation script reports:

- binary unsafe accuracy,
- 8-class accuracy,
- unsafe precision and recall,
- high/critical recall,
- end-to-end success rate,
- average processing time,
- confusion matrix,
- per-sample outputs.

## What To Publish In Releases

For credible open-source releases, attach:

- hardware and model configuration,
- dataset subset and exact command,
- model/provider version,
- full JSON evaluation output,
- false-positive examples,
- false-negative examples,
- average latency and timeout settings.

## Current High-Star Gap

The repository has the Agent workflow and metrics plumbing, but it still needs a public benchmark artifact generated from a fixed dataset subset and shown as charts in the README. That is the next credibility milestone.
