# ADR-0003: Separate VLM Perception From Safety Decisions

## Status

Accepted

## Context

A vision-language model can describe what appears in an image, but business
actions such as alerting, ticket creation, review requirements, and remediation
deadlines should be controlled by explicit product policy.

If the VLM directly decides every downstream action, the system becomes harder
to audit and tune.

## Decision

Use the VLM for perception:

- risk label,
- risk level,
- confidence,
- bbox,
- evidence description,
- remediation suggestion.

Use `SafetyPolicy` for action decisions:

- whether to send Feishu alert,
- whether human review is required,
- whether to recommend a ticket,
- due hours,
- whether verification is required.

## Consequences

Benefits:

- Safety operations can adjust policy without changing prompts.
- The UI can explain both "what the model saw" and "why the system acted".
- Uncertain results can be routed to human review instead of being treated as
  final violations.

Tradeoffs:

- Requires policy maintenance.
- The policy layer must be tested independently from VLM prompts.

## Follow-Up

Add a policy editor with audit history and environment-specific policy profiles.

