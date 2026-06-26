# ADR-0002: Build Video Memory Before Final Risk Reasoning

## Status

Accepted

## Context

Industrial safety videos are temporal evidence, not isolated images. A single
frame can be ambiguous: a person near equipment may be authorized, an object may
briefly cross a walkway, and a blurry frame may not be enough for a formal
violation.

Projects such as VideoAgent emphasize building structured memory first, then
reasoning over that memory. This makes the Agent more explainable than a single
black-box video label.

## Decision

Sample video frames and persist `VideoMemorySegment` records before final risk
decision. Each segment stores:

- time range,
- key frame artifact,
- visible objects,
- risk subject,
- bbox,
- evidence text,
- raw VLM output,
- review status.

Risk events are then merged from frame-level findings, and policy decisions are
made over the structured memory and findings.

## Consequences

Benefits:

- Reviewers can inspect why the Agent made a decision.
- The UI can show timeline memory, not only final screenshots.
- Later retrieval features can search memory segments by label, object, bbox, or
  review status.

Tradeoffs:

- More database records are created per video.
- Memory quality depends on frame sampling and VLM output quality.

## Follow-Up

Add semantic search over video memory and object-level temporal retrieval.

