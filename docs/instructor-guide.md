---
title: Instructor guide
description: Facilitation, timing, checkpoints, demonstrations, and recovery guidance
author: tmathew1000
ms.date: 2026-10-17
ms.topic: reference
keywords:
  - instructor
  - facilitation
  - runbook
estimated_reading_time: 14
---

## Delivery model

The participant guide is self-contained. Instructor facilitation should improve
pacing and discussion but must not supply missing steps.

## Before the session

Complete the lab from a new subscription path and verify:

* Both supported regions
* Default model availability and quota requirements
* Codespace post-create setup
* `azd up` and `azd down --purge`
* Hosted-agent readiness
* MCP scale-from-zero behavior
* Direct upload of all six Foundry IQ files, repeat-run updates, and cited retrieval
* Azure AI Search regional support and current pricing
* Trace ingestion
* Evaluation suite completion
* Every checkpoint restore
* Saved trace and evaluation artifacts

Record current service advisories and model-capacity concerns.

### Prepare for participants bringing their own subscriptions

Distribute the repository and prerequisite checklist before the event. Each
student uploads the bundled documents into their own Search service with their
own tenant identity. Do not prepare a shared Blob account or distribute SAS tokens.

File knowledge sources use a preview API (`2026-08-01-preview`). Pilot the selected
region and Basic Search tier before delivery. Verify model quota, hosted-agent
support, permission to assign roles, and reachable Search and Foundry endpoints.
Direct files remove Blob ingestion setup, not these remaining dependencies.

Run `azd provision knowledge --no-state` twice in the pilot environment and
confirm the source still contains six files with the same file IDs. Inspect
retrieval citations for the
Tokyo neighborhood, transit, and activity documents. Use Module 2's comparison
prompt and `python scripts/smoke_test.py` for live integration evidence.

Allow students to provision before the event when possible. If they have an older
Blob-based environment, use the
[upgrade checklist](troubleshooting.md#upgrade-an-existing-blob-based-environment)
and retain old resources until the new retrieval path is verified.

## Suggested runbook

| Time | Instructor action | Participant milestone |
| ------ | ------------------- | ----------------------- |
| 0:00 | Introduce outcomes and start preflight | Subscription validated |
| 0:15 | Explain architecture while provisioning runs | `azd up` started |
| 0:40 | Demonstrate source-to-hosting relationship | Baseline invoked |
| 1:10 | Contrast capability types | Foundry IQ verified |
| 1:50 | Explain manager-led orchestration | Activities registered |
| 2:25 | Break | Multi-agent tests pass |
| 2:35 | Demonstrate trace hierarchy | Candidate deployed |
| 3:10 | Lead failure diagnosis | Failure explained from spans |
| 3:30 | Explain evaluation comparison | Baseline and candidate compared |
| 3:55 | Require cleanup | Resource deletion started |

## Talking points

Reinforce these distinctions:

* Agent Framework defines runtime agent behavior and orchestration.
* Foundry provides model access, hosting, observability, evaluation, and lifecycle.
* Logical-agent count does not equal deployment count.
* Tools perform actions; grounding contributes context.
* Foundry IQ manages reusable, multi-source knowledge and citations.
* Permission enforcement depends on source support and explicit configuration.
* Traces diagnose execution; evaluations measure behavior across cases.
* Automation removes setup work, not engineering decisions.

## Demonstration prompts

Focused routing:

```text
Convert 500 USD to JPY for my Tokyo trip.
```

Complete workflow:

```text
Plan four days in Tokyo from Lisbon. Keep the hotel under 200 EUR per night,
include a day trip, and show major prices in JPY.
```

Foundry IQ comparison:

```text
Recommend a Tokyo neighborhood under 200 EUR per night with evening dining,
convenient transportation, and a rainy-day activity. Cite the supporting
sources.
```

Controlled failure:

```text
Convert my Tokyo hotel budget of 200 CAD per night to JPY.
```

## Recovery policy

Use checkpoints when a participant has spent more than five minutes on source
drift. Use saved telemetry artifacts when the Azure service delay would prevent
the learning outcome.

Do not use checkpoints to hide a widespread repository defect. Pause and correct
the shared issue.

## Common misconceptions

### Each specialist must be deployed separately

The lab exposes one Agent Framework graph through one hosted-agent endpoint.

### MCP is another name for a function tool

A function tool is registered directly in application code. MCP standardizes
remote capability discovery and invocation.

### A good final answer proves the workflow is correct

The answer can look plausible despite incorrect routing, failed tools, or
ungrounded claims. Use traces and evaluations.

### Foundry IQ automatically provides live travel data

The workshop knowledge base contains curated destination guidance. Live prices,
availability, schedules, and wait times remain operational tool responsibilities.

### Evaluation is a final release gate

Evaluation is part of development. The lab uses a baseline and candidate to show
the iterative loop.

## Completion targets

A successful pilot should achieve:

* At least 80 percent of participants reach trace inspection
* At least 75 percent compare evaluation versions
* Checkpoint recovery takes less than five minutes
* The required path finishes within four hours

Collect module-level feedback and note where participants pause, misread, or
require help.
