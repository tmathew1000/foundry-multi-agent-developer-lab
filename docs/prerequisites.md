---
title: Prerequisites and subscription checks
description: Required skills, Azure permissions, quotas, policies, and workstation setup for the lab
author: tmathew1000
ms.date: 2026-10-18
ms.topic: reference
keywords:
  - prerequisites
  - azure subscription
  - quota
  - permissions
estimated_reading_time: 8
---

## Participant knowledge

You should be comfortable with:

* Reading and editing Python
* Running commands in a terminal
* Basic Git and JSON concepts
* Basic generative AI concepts such as prompts, tokens, and tool calls

You do not need prior Microsoft Foundry or Microsoft Agent Framework experience.

## Accounts and tools

You need:

* A GitHub account with access to GitHub Codespaces
* An Azure account in the tenant that owns your subscription
* An Azure subscription in which you can create disposable resources
* A modern browser that can access GitHub, Azure, and Microsoft Foundry

The Codespace installs the required command-line tools and Python dependencies.
No local workstation setup is required.

## Required Azure permissions

Use one of these permission combinations at subscription or resource-group scope:

* Owner
* Contributor plus Role Based Access Control Administrator

Contributor alone is insufficient because provisioning assigns managed-identity
roles.

Run this command after signing in to confirm the active subscription:

```bash
az account show --output table
```

> [!CAUTION]
> Do not continue if the displayed subscription is not the subscription you
> intend to use. Lab resources incur cost.

## Subscription constraint checklist

Confirm each item before starting:

| Constraint | Required state |
| ------------ | ---------------- |
| Subscription | Enabled and not read-only |
| Spending | Sufficient credit or spending limit |
| Permissions | Owner, or Contributor plus RBAC Administrator |
| Region | Primary or documented secondary region allowed |
| Model access | Selected model available to the subscription |
| Model quota | Sufficient tokens-per-minute capacity |
| Search | Region supports agentic retrieval and Basic tier resources |
| Azure Policy | Resource types and public endpoints permitted |
| Role assignments | Participant can create role assignments |
| Providers | Registration is allowed |
| Network | Codespace can reach Azure and Foundry public endpoints |

## Resource providers

Provisioning may register or use:

* `Microsoft.CognitiveServices`
* `Microsoft.ManagedIdentity`
* `Microsoft.Insights`
* `Microsoft.OperationalInsights`
* `Microsoft.Storage`
* `Microsoft.Search`
* `Microsoft.ContainerRegistry`
* `Microsoft.App`

Provider registration can take several minutes in a new subscription.

## Regional model capacity

The default logical deployments are `travel-model` for chat and
`travel-embeddings` for Foundry IQ indexing. The models behind those names are
selected by the infrastructure configuration.

Availability in the Foundry catalog does not guarantee capacity in your
subscription. Preflight verifies local tooling, login, and subscription state.
It does not query live model quota, Search capacity, or hosted-agent regional
availability. Its quota and policy messages are caveats, not successful capacity
checks. Review these constraints with your administrator before allocating resources.

Candidate regions include `eastus2`, `northcentralus`, and `westus3`, subject to
current model, hosted-agent, and Search agentic-retrieval support. No candidate
guarantees capacity. Use the recovery steps in [Troubleshooting](troubleshooting.md)
if allocation fails. Do not substitute an untested model during the lab.

## Policies that commonly block the lab

The lab cannot deploy normally when policy:

* Denies public network access to required services
* Restricts Azure regions
* Denies managed identities
* Denies role assignments
* Requires tags not supplied by the template
* Restricts Container Apps or container registries
* Requires private endpoints

If your organization enforces these controls, use a sandbox subscription or the
fallback artifacts. The four-hour lab does not configure private networking.

### Direct file knowledge access from Codespaces

The knowledge bootstrap uploads six bundled Markdown files directly to your
Azure AI Search service using your signed-in identity. Students from different
tenants ingest their own copy into their own subscription. No organizer-hosted
Blob account, SAS token, cross-tenant storage grant, or anonymous access is needed.

File knowledge sources are a preview feature. The lab uses API
`2026-08-01-preview`, minimal text extraction, and Basic Search. Confirm support
in the selected region before the event. Search must be reachable from Codespaces;
the deployment identity needs Search Service Contributor for knowledge objects
and file operations, plus Search Index Data Reader for retrieval. Search's managed
identity needs Cognitive Services User on the Foundry account for embedding and
chat inference. The templates assign these roles.

Removing Blob ingestion avoids its network-policy and role-propagation
dependencies, not all Azure policy restrictions. Foundry, Search, and hosted-agent
network requirements remain. Private networking is outside the default lab;
use an approved sandbox or saved artifacts when public endpoints are denied.
Other platform resources may still use supporting storage.

See [file operation recovery](troubleshooting.md#direct-file-upload-fails) and the
[Microsoft file knowledge source documentation](https://learn.microsoft.com/azure/search/agentic-knowledge-source-how-to-file).

## Expected resources

The automated setup creates a disposable environment that includes:

* One resource group
* One Microsoft Foundry project
* One model deployment
* One embedding deployment
* One hosted TravelBuddy deployment
* One scale-to-zero MCP service
* Application Insights and Log Analytics
* Supporting storage, registry, and managed identities
* One Basic Azure AI Search service
* One Foundry IQ file knowledge source and knowledge base

## Cost assumption

Plan for five hours of resource lifetime:

* Expected cost: USD 5 to USD 10
* Current Azure AI Search and model pricing must be checked before delivery
* Possible Codespaces charge: depends on your GitHub plan and included quota

Cost varies with model selection, token volume, region, retries, and evaluation
runs.

## Stop conditions

Do not start the required Azure path when:

* The preflight reports no model quota
* Your role cannot create role assignments
* Azure Policy blocks a required resource
* Neither supported region has capacity
* Your subscription is disabled or has no available credit

Use the checkpoint and saved-artifact path instead. Do not spend lab time trying
to bypass organizational policy.
