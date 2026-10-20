---
title: Troubleshooting
description: Symptom-based recovery for setup, Foundry IQ, MCP, tracing, and evaluation
author: tmathew1000
ms.date: 2026-10-19
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

Preflight does not allocate capacity or query live regional quotas. Check model,
hosted-agent, and Search support before choosing another approved region.
Candidate regions include `eastus2`, `northcentralus`, and `westus3`; availability
can change. Search can report `InsufficientResourcesAvailable` even in a supported
region. Use fallback artifacts when allocation remains unavailable. Do not select
an arbitrary model because tool and structured-output behavior may differ.

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

## Region change fails with InvalidDeploymentLocation

Subscription-level deployment records retain their original location even after
their resource group has been deleted. Before retrying in a different region:

1. Confirm the subscription and identify the exact deployment named in the error.
2. Inspect that record and verify it belongs to this lab.
3. If existing lab resources need removal, review and run `azd down --purge`
   before changing regions. This deletes resources and requires confirmation.
4. Delete only the stale lab deployment record, not unrelated deployment history.

```bash
az account show --output table
az deployment sub list --query "[].{name:name,location:location}" --output table
az deployment sub show --name "<deployment-name-from-error>"
az deployment sub delete --name "<verified-stale-lab-deployment-name>"
azd env set AZURE_LOCATION "<approved-supported-region>"
azd up
```

Deleting a deployment record does not delete its resources. Do not use this as
a replacement for resource cleanup.

## Local capabilities differ from the hosted agent

Run local commands from the repository root. Import deployment outputs with
`azd env get-values > .env`, then restart `python main.py`. The local application
derives `/mcp` from `SERVICE_MCP_SERVER_URI` unless `TRAVEL_BUDDY_MCP_URL` is
explicitly set. Remove a stale terminal override before testing a changed value.

For Foundry IQ, keep the hosted `azure.yaml` setting and the active `azd`
environment aligned. Module 2 uses
`azd env set TRAVEL_BUDDY_GROUNDING_PROVIDER foundry_iq` before exporting `.env`.
A value added only to `.env` is lost on the next export. The provider defaults
to `local`; provisioned Search resources alone do not enable it. Local restarts
do not update hosted code or configuration; redeployment is required.

The smoke test checks service connectivity independently. Inspect the actual
invocation trace to prove an agent used MCP or Foundry IQ.

## Evaluation verification cannot find results

Use the same `--results-dir` for baseline, candidate, comparison, and
`verify_module.py 5` (or `all`). The verifier prints the selected paths and fails
when either result is missing. It never automatically substitutes historical
artifacts. For offline analysis, explicitly select `--fallback` instead, and
record that the comparison is illustrative, not a live deployment measurement.

## Hosted agent is not ready

Deployment success does not always mean the container has started.

Check:

* Image build and push succeeded
* Required environment variables are populated
* The hosted version reports ready
* Startup logs contain no import or authentication errors

Do not repeatedly redeploy an unchanged image. Diagnose the startup failure.

For HTTP 424 `session_not_ready`, inspect the failing session:

```bash
azd ai agent show travel-buddy --output json
azd ai agent sessions list --agent-name travel-buddy --output table
azd ai agent monitor travel-buddy --session-id "<session-id>" --tail 100
azd ai agent monitor travel-buddy --session-id "<session-id>" \
  --type system --tail 100
```

Use the session ID from the failed invoke or the sessions list. An active agent
version does not guarantee that a session's application reached `/readiness`.
Inspect import, configuration, dependency, and authentication errors before
changing health endpoints or timeouts.

If logs show `ModuleNotFoundError: No module named 'travel_buddy'`, confirm that
`requirements.txt` installs `.` rather than `-e .`. Remote code builds must install
a regular package: an editable install can reference a temporary build directory
that is not present in the runtime image. Editable installs remain appropriate
for local development.

After fixing the logged cause:

```bash
azd deploy travel-buddy
python scripts/smoke_test.py
```

The smoke test requires an actual completed response with nonempty answer text.
It also calls MCP and Search independently; it does not prove every specialist
used every integration in that particular response. Inspect traces for that
evidence.

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

## Foundry IQ bootstrap fails

Check:

* The Search region supports agentic retrieval.
* The Search service is Basic tier or higher.
* Both `travel-model` and `travel-embeddings` deployed successfully.
* The file knowledge source uses `2026-08-01-preview` and minimal extraction.
* The Search managed identity has Cognitive Services User on the Foundry account.
* The deployment identity has Search Service Contributor.
* Role assignments have finished propagating.

Rerun `azd provision knowledge --no-state` after correcting the reported issue.
The post-provision hook updates the same deterministic knowledge source and
knowledge base. The `--no-state` flag prevents `azd` from skipping the unchanged
layer and its hook.

## Direct file upload fails

The bootstrap creates the file source, then uploads and indexes each document
directly in Search. There is no separate ingestion status poll or Blob network
check. Each operation can take up to 180 seconds; the client allows 240 seconds.

Check the HTTP error and confirm:

* The API version is `2026-08-01-preview`, not an older preview.
* Search file knowledge sources are available in your selected region.
* The Codespace can reach the Search endpoint under effective network rules.
* Your identity has Search Service Contributor and role propagation has completed.
* The Search identity can call `travel-embeddings` on the Foundry account.
* The six Markdown documents exist in `data/foundry-iq/`.

Rerun `azd provision knowledge --no-state` after correcting the cause.
The hook lists existing files,
follows pagination, and updates matching names by file ID. Uploading the same
filename with POST alone creates duplicates; the hook does not do that on reruns.
An upload with an uncertain response is not automatically retried. Rerunning
provisioning reconciles any file the service successfully persisted.

The default environment is Codespaces. If you run `azd` from Windows instead,
its `sh` hook requires a working Bash shell. A WSL startup error occurs before
the Python bootstrap runs. Use Codespaces or put an installed Git Bash directory
on the current terminal's PATH, then rerun the command above.

If the hook reports duplicate names, inspect the source's file list in Search
using the file API, retain the intended version, and delete only confirmed
duplicates by file ID. Removing or renaming a local document does not delete the
old remote file. Review optional source changes explicitly.

Do not change tenant-wide policies to bypass a restriction. Use an approved
sandbox or saved artifacts when Search public endpoints cannot be approved.

## Upgrade an existing Blob-based environment

New environments use direct files by default. For an existing environment:

1. Save your student exercise edits and update your checkout to the direct-file
   version of the repository.
2. Run `azd provision knowledge --no-state`. The updated knowledge template no
   longer provisions a
   dedicated Blob account or Blob roles. Its post-provision hook creates
   `travel-destinations-files`, uploads the six files, and repoints the existing
   `travel-destinations` knowledge base only after file processing succeeds.
3. Run `azd env get-values > .env` to refresh local values. Restore
   `TRAVEL_BUDDY_GROUNDING_PROVIDER=foundry_iq` if you are at Module 2 or later.
   Old `FOUNDRY_IQ_STORAGE_*` and `FOUNDRY_IQ_KNOWLEDGE_CONTAINER` values are unused.
4. Preserve the grounding-provider change in `azure.yaml`, then run
   `azd deploy travel-buddy` to deploy the new runtime and file source name.
   Restart any local host.
5. Run `python scripts/smoke_test.py` and Module 2's comparison prompt. Confirm
   cited retrieval before removing anything from the previous ingestion path.
6. Inventory the old `travel-destinations-blob` source, its generated Search
   resources, and the old dedicated knowledge storage account. Incremental ARM
   deployments retain resources omitted from a template. Remove only verified,
   unused lab resources through your approved cleanup process, or keep them until
   Module 6 teardown. Do not delete platform storage or shared resources.

Do not change the kind of the old source in place. The new source name separates
the migration from the previous Blob source. The old runtime uses `azureBlob`
retrieval parameters, so updating infrastructure without redeploying the runtime
is not a complete upgrade.

## Foundry IQ retrieval fails

An HTTP 401 indicates authentication failed. An HTTP 403 usually indicates that
the caller lacks Search Index Data Reader or that a new role assignment has not
propagated. An empty result can indicate incomplete indexing or a query outside
the workshop documents.

Do not silently switch to local grounding. Set
`TRAVEL_BUDDY_GROUNDING_PROVIDER=local` explicitly when following the documented
recovery path.

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

Capture the resource group and subscription before teardown. After deletion,
`az group exists --name "$RESOURCE_GROUP"` must return `false` in that same
subscription. Review any additional resource groups and soft-deleted resources
reported by `azd down`; a failed authentication or authorization request is not
evidence of successful deletion. Check Cost Management for remaining lab
resources, allowing for billing-data delay.
