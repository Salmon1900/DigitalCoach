---
name: add-exercise-analyzer
description: Scaffold a new per-exercise form analyzer for the DigitalCoach CV pipeline (e.g. pull-up, push-up, plank, dip). Use when the user wants to add support for a new calisthenics movement or technique check.
---

# Add an exercise analyzer

Use this when adding support for a new calisthenics movement. Each exercise is an
isolated analyzer implementing the shared interface so the pipeline core never changes.

## Before writing code
1. Identify the movement and its **form criteria** in plain language (e.g. pull-up:
   full dead hang at bottom, chin over bar at top, minimal kipping/swing).
2. Map each criterion to **landmarks and a measurable signal** — joint angles, vertical
   displacement, symmetry, tempo. Name every threshold.
3. Confirm the output conforms to the `sample_analysis.json` contract (score + timestamped
   remarks + tips).
4. Defer pose/geometry questions to the `cv-pipeline-engineer` subagent.

## Steps
1. Create `app/cv/analyzers/<exercise>.py` implementing the common analyzer interface
   used by the other analyzers (read an existing one first for the exact signature).
2. Keep it in two layers:
   - **pure geometry/decision logic** (takes landmark time-series → remarks + score),
     unit-testable with no I/O;
   - thresholds as **named, configurable constants**, not magic numbers.
3. Register the analyzer in the exercise registry/dispatch so the pipeline can select it
   by exercise type — do not special-case it in pipeline core.
4. Add pytest cases (hand-craft landmark inputs with known expected angles) — hand off to
   `test-engineer`. Cover the normal rep plus edge cases: missing/low-confidence
   landmarks, partial range of motion, asymmetry.
5. Verify output validates against the `sample_analysis.json` shape.

## Guardrails
- No blocking work in async paths — analyzers are sync/pure and run in the worker pool.
- Don't duplicate frame-extraction or pose-detection; reuse the generic pipeline.
- This repo is in configuration/planning phase — only implement when explicitly asked.
