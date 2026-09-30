---
title: Troubleshooting
description: Symptom-based recovery guidance for setup, deployment, MCP, tracing, and evaluation
author: tmathew1000
ms.date: 2026-09-30
ms.topic: troubleshooting
keywords:
  - troubleshooting
  - quota
  - rbac
  - tracing
estimated_reading_time: 12
---

## Diagnostic order

Use this order before changing code:

1. Confirm the active subscription and tenant.
2. Confirm the latest command completed successfully.
3. Confirm required environment values are populated.
4. Confirm identity and role assignments.
5. Confirm resource and deployment status.
6. Confirm network reachability.
7. Inspect logs and traces.
8. Restore the current checkpoint only when source drift is the cause.

## Authentication fails

Symptoms:

* `DefaultAzureCredential` cannot obtain a token
* Azure CLI reports that login is required
* Foundry returns HTTP 401

Recovery:

```bash
az login --use-device-code
azd auth login --use-device-code
az account show --output table
```

Confirm that both tools use the intended tenant and subscription.

## Authorization fails

Symptoms:

* HTTP 403
* Role-assignment creation fails
* Hosted identity cannot access the project

Allow several minutes for a new role assignment to propagate. If the error
persists, verify that provisioning assigned the documented roles to the correct
managed identity.

Contributor alone cannot create role assignments.

## Model deployment fails

Symptoms:

* Insufficient quota
* SKU unavailable
* Model unavailable in region
* Capacity allocation failure

Run preflight again and use the documented secondary region. If neither region
has tested capacity, use the fallback artifacts. Do not select an arbitrary
model because tool and structured-output behavior may differ.

## `azd up` partially succeeds

Inspect the failed deployment:

```bash
azd show
RESOURCE_GROUP="$(azd env get-value AZURE_RESOURCE_GROUP)"
az deployment group list --resource-group "$RESOURCE_GROUP" --output table
```

Fix the reported cause, then rerun `azd up`. The templates are intended to be
idempotent.

Do not create replacement resources manually unless the lab explicitly directs
you to do so.

## Hosted agent is not ready

Deployment success does not always mean the container has started.

Check:

* Image build and push succeeded
* Required environment variables are populated
* The hosted version reports ready
* Startup logs contain no import or authentication errors

Do not repeatedly redeploy an unchanged image. Diagnose the startup failure.

## MCP calls fail

Check:

* The endpoint uses HTTPS
* The Container App is running or can scale from zero
* The agent configuration uses the remote endpoint, not `localhost`
* Tool names and input schemas match
* The hosted identity can invoke the endpoint

The first request can be slower after scale-to-zero.

## Grounding returns no context

Check:

* Data provisioning completed
* The expected destination exists in the source data
* The context provider is attached to the intended specialist
* Identity has data-plane access
* The retrieval query and top-k value are reasonable

Do not replace a failed grounding call with ungrounded model knowledge.

## Traces do not appear

Trace ingestion can be delayed.

Check:

* Application Insights connection is configured
* OpenTelemetry setup runs before agent construction
* Sampling does not exclude the request
* The time filter includes the invocation
* The selected Foundry project is correct

Use the response ID to correlate the request. If the delay exceeds the module
timebox, use the saved trace artifact and return later.

## Evaluations remain queued

Keep the required dataset small and avoid starting duplicate runs. Use the saved
results after the documented wait threshold, then return to the live result if
it completes.

## Restore a checkpoint

Preview the restore:

```bash
python scripts/restore_checkpoint.py 3 --dry-run
```

Apply it:

```bash
python scripts/restore_checkpoint.py 3
```

The command must report every replaced file. Review the changes before
continuing.

## Cleanup fails

Retry:

```bash
azd down --purge
```

Then inspect the resource group for policy locks or resources still deleting.
Do not assume that closing a Codespace stopped Azure charges.
