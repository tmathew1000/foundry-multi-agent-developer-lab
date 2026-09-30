---
title: Prerequisites and subscription checks
description: Required skills, Azure permissions, quotas, policies, and workstation setup for the lab
author: tmathew1000
ms.date: 2026-09-30
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
* `Microsoft.ContainerRegistry`
* `Microsoft.App`

Provider registration can take several minutes in a new subscription.

## Regional model capacity

The default logical deployment name is `travel-model`. The model behind that
name is selected by the infrastructure configuration.

Availability in the Foundry catalog does not guarantee capacity in your
subscription. The preflight checks:

* Region support
* Model quota
* Required inference capabilities
* Hosted-agent compatibility

If the primary region lacks capacity, use the documented secondary region. Do
not select an untested model during the lab.

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

## Expected resources

The automated setup creates a disposable environment that includes:

* One resource group
* One Microsoft Foundry project
* One model deployment
* One hosted TravelBuddy deployment
* One scale-to-zero MCP service
* Application Insights and Log Analytics
* Supporting storage, registry, and managed identities

## Cost assumption

Plan for five hours of resource lifetime:

* Expected cost: USD 3 to USD 5
* Conservative allowance: USD 7
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
