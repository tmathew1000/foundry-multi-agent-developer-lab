---
title: Module 6 - Review and clean up
description: Confirm the learning outcomes and remove all disposable Azure resources
author: tmathew1000
ms.date: 2026-10-18
ms.topic: tutorial
keywords:
  - cleanup
  - review
  - cost
estimated_reading_time: 8
---

## Outcome

You will connect the implementation to the platform features, verify the final
solution, and remove all disposable resources.

Estimated time: 15 minutes.

## Final architecture

```mermaid
flowchart TB
    U[Traveler] --> H[Foundry hosted agent]
    H --> C[Coordinator]
    C --> F[Flights]
    C --> HT[Hotels]
    C --> A[Activities]
    F --> FN[Function tools]
    HT --> MCP[MCP service]
    A --> MCP
    HT --> IQ[Foundry IQ]
    A --> IQ
    IQ --> B[Direct file knowledge]
    H -. telemetry .-> T[Tracing]
    H -. quality .-> E[Evaluation]
```

## Required: run final verification

```bash
python -m pytest
python scripts/verify_module.py all
python scripts/smoke_test.py
```

Do not continue to cleanup until you have recorded any results or screenshots
you want to retain.

`verify_module.py all` covers configuration/static checks for Modules 0-5.
Module 6 has no numbered script check and never deletes resources automatically.
The separate smoke test calls live MCP, Search, and the hosted agent; it can
incur model charges. Use trace and evaluation evidence for behavior beyond
service reachability.

## Required: explain the solution

Confirm that you can answer:

1. Why are four logical agents represented by one hosted endpoint?
2. When should an application use a function tool, MCP, or Foundry IQ?
3. What does `GroupChatBuilder` contribute?
4. What does `workflow.as_agent()` contribute?
5. How does trace evidence differ from final-response inspection?
6. Why compare evaluation versions instead of testing a few prompts manually?
7. Why should Foundry IQ access be assigned only to relevant specialists?

## Feature map

| Feature | Where you used it |
| --------- | ------------------- |
| Foundry project | Shared boundary for model, agent, traces, and evaluations |
| Model deployment | Inference for coordinator and specialists |
| Hosted agent | Managed execution of the containerized workflow |
| Agent Framework | Code-first agents and multi-agent orchestration |
| Function tool | Deterministic currency operation |
| MCP | Remote reusable travel operations |
| Foundry IQ | Managed destination knowledge with citations |
| Azure AI Search | Agentic retrieval and a managed index |
| File knowledge source | Directly uploaded, curated workshop documents |
| Managed identity | Authentication without API keys |
| Tracing | Runtime diagnosis |
| Evaluation | Baseline and candidate quality comparison |

## Required: remove resources

Capture the resource-group name before teardown:

```bash
RESOURCE_GROUP="$(azd env get-value AZURE_RESOURCE_GROUP)"
SUBSCRIPTION_ID="$(azd env get-value AZURE_SUBSCRIPTION_ID)"
```

Run:

```bash
azd down --purge
```

Confirm when prompted.

Verify the resource group no longer exists:

```bash
az group exists --name "$RESOURCE_GROUP" --subscription "$SUBSCRIPTION_ID"
```

The expected result is `false`. An authorization or authentication error does
not prove deletion. Inspect any extra resource groups or soft-deleted resources
reported by teardown, and confirm there are no remaining billable lab resources.
Cost Management data can take time to update.

If you upgraded from the Blob-based version, also review the old dedicated
knowledge storage account and any superseded Search source, generated indexer,
data source, skillset, or index. Incremental provisioning does not delete those
resources. See the [upgrade checklist](troubleshooting.md#upgrade-an-existing-blob-based-environment).
Pilot knowledge bases and sources in the lab Search service are removed when
that Search service is deleted. Do not delete resources used by another workload.

> [!CAUTION]
> Closing the Codespace does not remove Azure resources. Verify cleanup to stop
> ongoing charges.

## Retain the learning, not the environment

You can now apply the pattern to another scenario:

1. Define specialist boundaries around business responsibilities.
2. Assign each capability only where needed.
3. Select deterministic or dynamic orchestration deliberately.
4. Instrument the complete request path.
5. Create evaluation cases from real requirements and failures.
6. Improve one measured behavior at a time.

## Optional next steps

Explore these topics after the lab:

* Durable workflows and checkpointing
* SharePoint and OneLake knowledge sources
* Document-level permission synchronization
* Agent memory
* Continuous evaluation
* CI/CD and version promotion
* Private networking
* Safety and red-team evaluation
* Model comparison

## Lab complete

You have built, hosted, traced, evaluated, and improved a multi-agent solution
with Microsoft Foundry and Microsoft Agent Framework.
