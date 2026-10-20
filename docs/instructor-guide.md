---
title: Instructor guide
description: Facilitation, timing, checkpoints, demonstrations, and recovery guidance
author: tmathew1000
ms.date: 2026-10-19
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

* The selected region and an approved alternative with current service support
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

Require provisioning and the Module 0 readiness and smoke checks before the
four-hour event. Initial provisioning typically takes 25 to 35 minutes, plus
authentication, verification, and remediation. Provide a separate setup clinic;
a cold-start session needs additional time, not weaker completion gates.
If students have an older
Blob-based environment, use the
[upgrade checklist](troubleshooting.md#upgrade-an-existing-blob-based-environment)
and retain old resources until the new retrieval path is verified.

## Suggested runbook

| Time | Instructor action | Participant milestone |
| ------ | ------------------- | ----------------------- |
| Before class | Complete provisioning and smoke checks | Environment ready |
| 0:00 | Module 0: architecture and readiness | Setup confirmed |
| 0:15 | Module 1: source and local hosting | Baseline invoked by 0:45 |
| 0:45 | Module 2: tools and managed retrieval | Comparisons recorded by 1:25 |
| 1:25 | Module 3: manager-led orchestration | Workflow tests pass by 2:20 |
| 2:20 | Break | Resume at 2:30 |
| 2:30 | Module 4: deploy and diagnose traces | Evidence retained by 3:05 |
| 3:05 | Module 5: baseline and candidate | Comparison or fallback by 3:45 |
| 3:45 | Module 6: review and cleanup | Verify resource deletion |
| 4:00 | Close session | Follow up on unfinished deletion |

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

Unsupported-currency diagnostic:

```text
Convert my Tokyo hotel budget of 200 CAD per night to JPY.
```

## Facilitating Modules 4 and 5

Keep the published application and Module 1–3 checkpoints unchanged. Existing
currency-routing instructions are part of the baseline, not a failure to
reintroduce. Model-driven routing can still vary between runs.

In Module 4, collect the invocation IDs, version, time, and actual trace
evidence. Diagnose routing bypass separately from a tool's structured
`unsupported_currency` result and from final-answer fidelity. Correct handling
is a valid observation; do not ask students to rerun until a failure appears.
The saved trace is an illustrative correct-handling example, not a live trace.
Do not change instructions during diagnosis.

In Module 5, run the fixed 12-case suite before editing instructions. Capture
the exact baseline version, select a measured hypothesis, then deploy and
evaluate a distinct candidate on identical cases and settings. The comparison
helper checks recorded provenance, but manual trace review must establish
actual tool execution and conversation isolation. Missing evidence remains
unverified even if the response or an evaluator score looks good.

If the baseline handles currency correctly, choose another observed issue.
If no suitable issue appears or services are delayed, use Module 5's labeled
supplied scenario and historical fallback scores for analysis only. Do not
claim those scores measure the supplied narrative or the current suite.
Unchanged or worse candidate results are valid discussion material. Keep the
exercise to one focused instruction hypothesis and one candidate comparison;
record what still requires live verification.

When verification uses custom evaluation directories, carry `--results-dir`
through the runner, comparison, and Module 5/final verification commands. Use
`--fallback` explicitly for historical artifacts; never present them as live.
Do not restore Module 3 checkpoints over a student's Module 5 candidate.

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
* The pre-provisioned instructional path finishes within four hours
* Resource deletion is confirmed, even when teardown outlasts the session

Collect module-level feedback and note where participants pause, misread, or
require help.
