# Benchmark And Evaluation

This project exposes two evaluation layers:

- **Smoke evaluation**: prove the full Agent workflow can create audit, evidence, memory, alert, report, and ticket recommendation.
- **Dataset evaluation**: run public industrial safety videos through the API or local model.

## Local Smoke Benchmark

Use the deterministic seeded demo:

```bash
python scripts/dev.py up
python scripts/dev.py seed
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

A committed smoke benchmark contract is available at
[docs/assets/benchmarks/smoke-demo-metrics.json](assets/benchmarks/smoke-demo-metrics.json).

Generate the human-readable report and chart:

```bash
python scripts/dev.py benchmark-report
```

Artifacts:

- [smoke-demo-report.md](assets/benchmarks/smoke-demo-report.md)
- [smoke-demo-chart.svg](assets/benchmarks/smoke-demo-chart.svg)

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

The repository now includes a smoke benchmark report and chart for workflow
integrity. The next credibility milestone is a public dataset benchmark artifact
with fixed sample ids, model configuration, and false-positive / false-negative
examples.
