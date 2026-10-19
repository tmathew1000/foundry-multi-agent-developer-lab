---
title: Module 4 - Deploy and diagnose with tracing
description: Deploy the multi-agent version and inspect its distributed execution trace
author: tmathew1000
ms.date: 2026-10-19
ms.topic: tutorial
keywords:
  - deployment
  - tracing
  - opentelemetry
estimated_reading_time: 18
---

## Outcome

You will deploy the completed workflow, follow its distributed trace, and use
evidence to diagnose a controlled tool failure.

Estimated time: 35 minutes.

## Architecture change

```mermaid
flowchart TB
    I[Hosted invocation] --> W[Agent Framework workflow]
    W --> C[Coordinator]
    C --> S[Specialist]
    S --> T[Tool or Foundry IQ]
    I -. trace context .-> O[Foundry observability]
    W -. spans .-> O
    C -. spans .-> O
    S -. spans .-> O
    T -. spans .-> O
```

Trace context connects the hosted request to Agent Framework, model, tool, MCP,
Foundry IQ retrieval, and citation activity.

## Required: deploy the candidate

Run the complete local verification before deployment:

```bash
python -m pytest
python scripts/verify_module.py 3
```

Deploy:

```bash
azd deploy
```

Wait until the hosted-agent status reports ready. A deployment that was accepted
but is still starting is not ready for invocation.

## Required: connect Application Insights to Foundry

The lab provisions an Application Insights resource and configures the hosted
application to export telemetry through `APPLICATIONINSIGHTS_CONNECTION_STRING`.
The Foundry project also needs a connection to that resource so you can view
traces in the portal. Creating the resource and configuring telemetry export do
not, by themselves, establish this portal connection.

Find `AZURE_APPLICATION_INSIGHTS_NAME` in the `.env` file imported earlier in the
lab. The resource name follows the pattern `appi-mcp-<resource token>`. Despite
the `mcp` name, the hosted TravelBuddy application also exports telemetry to
this resource. Use this existing resource rather than creating a second one.

In the new Microsoft Foundry portal:

1. Open the same project that hosts your deployed TravelBuddy agent.
2. In the left navigation, select **Agents**, then select **Traces** at the top.
3. Select **Connect**.
4. Choose the subscription and resource group containing the lab's Application
   Insights resource, then select the resource matching
   `AZURE_APPLICATION_INSIGHTS_NAME`.
5. Select **Connect** and wait for the success confirmation.

If the **Connect** button is not visible, use **Manage → Project details →
Connected resources → Add connection → Application Insights**, then select the
same existing resource. If the project already has a connection, confirm that
it points to the resource used by the application.

You need permission to add the project connection and query the selected
Application Insights resource. If access is denied, ask your administrator for
the appropriate access. Querying telemetry requires **Log Analytics Reader**.
If the underlying Log Analytics tables are protected, you may also need
**Privileged Monitoring Data Reader**.

Connecting the existing resource does not require redeploying the agent.
Generate a new invocation after connecting, as described below, and allow a few
minutes for telemetry ingestion.

See [Set up tracing in Microsoft Foundry](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup)
for the portal connection procedure and access requirements.

## Required: generate a trace

Invoke the deployed agent with:

```text
Plan four days in Tokyo from Lisbon. Keep the hotel under 200 EUR per night,
include a day trip, and show major prices in JPY.
```

Save the response ID printed by the invocation helper.

## Required: inspect the trace

In Microsoft Foundry:

1. Open the project.
2. Open **Agents → Traces**.
3. Filter to the TravelBuddy agent and recent time range.
4. Open the trace matching the saved response ID.

If the invocation is not listed immediately, wait a few minutes and refresh.
Confirm that the time range includes the invocation and that the project is
connected to the Application Insights resource selected above.

Find:

* Hosted invocation
* Agent Framework workflow
* Coordinator decisions
* Selected specialists
* Model calls
* Function and MCP calls
* Foundry IQ knowledge retrieval
* Query-planning or source-retrieval activity
* Retrieved references and citations
* Final synthesis

Record:

* Which specialist ran first
* Which operation had the highest latency
* Whether an unnecessary specialist ran
* Whether Foundry IQ ran only for destination knowledge
* Which sources supported the destination recommendation
* Token usage for the complete request

## Required: diagnose the controlled failure

Invoke:

```text
Convert my Tokyo hotel budget of 200 CAD per night to JPY.
```

The starter currency tool intentionally supports a limited set of currencies.
Use the trace to answer:

1. Did routing select the expected specialist?
2. Did the model form valid tool arguments?
3. Did the tool execute?
4. What result or error did the tool return?
5. Did the final response represent the limitation accurately?

The correct diagnosis is based on the tool span, not on the wording of the final
answer alone.

## Why this matters

Agent responses hide execution details. Distributed tracing separates routing,
model reasoning, external dependencies, and application code so you can improve
the correct layer.

## Verify your work

```bash
python scripts/verify_module.py 4
```

Expected result:

```text
PASS Module 4: tracing configuration is present
```

The script verifies instrumentation configuration. You must inspect the live
trace to complete the learning outcome.

## Fallback artifact

If trace ingestion is delayed, open `artifacts/traces/controlled-failure.json`.
Follow the same diagnostic questions and return to the live trace if it appears.

## Optional challenge

Compare specialist span durations and propose one capability assignment that
would reduce latency without reducing answer quality.

## Completion check

Continue when:

* The candidate version is deployed
* The Foundry project is connected to the lab's Application Insights resource
* You have followed one complete trace
* You have diagnosed the unsupported-currency failure

Next: [Module 5 - Evaluate and improve](05-evaluate-improve.md).
