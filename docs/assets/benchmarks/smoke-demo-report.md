# Smoke Demo Benchmark Report

This report is generated from
[`smoke-demo-metrics.json`](smoke-demo-metrics.json). It validates workflow
integrity for the deterministic seeded demo. It is not a model-quality benchmark.

![Smoke benchmark chart](smoke-demo-chart.svg)

## Summary

| Field | Value |
| --- | --- |
| Benchmark type | `deterministic_smoke_demo` |
| Scope | `workflow_integrity` |
| Dataset | `seeded_demo_safety_agent` |
| Model | `seeded_or_qwen3-vl-plus` |

## Metrics

| Metric | Key | Value |
| --- | --- | --- |
| Total videos | `total_videos` | 1 |
| Processing success | `processing_success_rate` | 100% |
| BBox validity | `bbox_validity_rate` | 100% |
| High-risk alerts | `high_risk_alerts` | 1 |
| Feishu alert success | `feishu_alert_success_rate` | 100% |
| Human review required | `human_review_required` | 0 |
| Tickets by default | `remediation_tickets_created_by_default` | 0 |
| Verifications by default | `post_remediation_verifications_by_default` | 0 |

## Expected Artifacts

- `VideoAudit`
- `VideoAuditFinding`
- `VideoAuditEvidence`
- `VideoAuditReport`
- `VideoAuditAgentRun`
- `VideoAuditAgentStep`
- `VideoMemorySegment`
- `VideoAuditAlertEvent`
- `ticket_recommendation`

## Notes

- This file is a reproducible smoke benchmark contract, not a model-quality benchmark.
- Use scripts/evaluate_safety_agent.py with public samples for model-quality metrics.
