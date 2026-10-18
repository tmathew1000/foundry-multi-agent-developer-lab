---
title: TravelBuddy architecture
description: Readable architecture diagrams for the Foundry and Agent Framework lab
author: tmathew1000
ms.date: 2026-10-17
ms.topic: concept
keywords:
  - architecture
  - multi-agent
  - tracing
  - evaluation
estimated_reading_time: 6
---

## Learning journey

```mermaid
flowchart LR
    P[Provision] --> B[Build]
    B --> O[Orchestrate]
    O --> T[Trace]
    T --> E[Evaluate]
    E --> I[Improve]
```

You will complete one development lifecycle rather than a collection of
unrelated demonstrations.

## Deployed architecture

```mermaid
flowchart TB
    D[Developer in Codespaces]
    D --> FP[Microsoft Foundry project]
    FP --> MD[travel-model deployment]
    FP --> ED[travel-embeddings deployment]
    FP --> HA[TravelBuddy hosted agent]
    FP --> EV[Evaluation suite]
    HA --> MCP[Travel MCP service<br/>Azure Container Apps]
    HA --> IQ[Foundry IQ knowledge base]
    IQ --> SRCH[Azure AI Search]
    D -->|Direct file upload| GD[File knowledge source]
    GD -->|Extract, chunk, embed, index| SRCH
    HA -. OpenTelemetry .-> AI[Application Insights]
    AI --> FP

    classDef learner fill:#dff6dd,stroke:#107c10,color:#000
    classDef managed fill:#e5f1fb,stroke:#0078d4,color:#000
    classDef azure fill:#fff4ce,stroke:#986f0b,color:#000
    class D learner
    class FP,MD,ED,HA,EV managed
    class MCP,IQ,SRCH,GD,AI azure
```

Green identifies the participant environment. Blue identifies Foundry-managed
resources. Gold identifies supporting Azure resources.

## Multi-agent workflow

```mermaid
flowchart TB
    R[Travel request] --> C[Coordinator<br/>group-chat manager]
    C -->|flight need| F[Flights specialist]
    C -->|lodging need| H[Hotels specialist]
    C -->|destination need| A[Activities specialist]
    F --> C
    H --> C
    A --> C
    C --> P[Consolidated itinerary]

    F --> FN[Python function tools]
    H --> MCP[MCP travel tools]
    A --> MCP
    H --> G[Foundry IQ]
    A --> G
```

The coordinator and specialists are four logical agents. Foundry hosts the
complete graph as one deployment.

## Capability ownership

| Agent | Responsibility | Capabilities |
| ------- | ---------------- | -------------- |
| Coordinator | Route and synthesize | Routing and termination |
| Flights | Flights, timing, weather, and currency | Python function tools |
| Hotels | Lodging areas, budgets, and trade-offs | MCP and Foundry IQ |
| Activities | Experiences and day-by-day plans | MCP and Foundry IQ |

The division is intentionally visible so you can reason about routing and inspect
each specialist in a trace.

## Knowledge and tenancy

All required resources remain in the participant's Azure subscription and
Microsoft Entra tenant. The synthesized Foundry resources can use a dedicated
Foundry resource group. Search, Container Apps, registry, monitoring,
and supporting identities use the primary `azd` resource group.

The Search service has a managed identity that can invoke the Foundry chat and
embedding deployments. The hosted TravelBuddy identity receives query-only
access to Search. The deployment identity creates knowledge objects and uploads
the workshop documents directly to Search using Microsoft Entra authentication.

The `travel-destinations-files` file knowledge source uses the
`2026-08-01-preview` API and minimal text extraction. Search manages the generated
index and processes each upload synchronously. There is no external Blob account,
cross-tenant storage grant, or indexer pipeline for this source. Repeat runs
update existing file IDs; they do not remove obsolete files automatically.

The local provider remains available as a deterministic baseline and recovery
path. Selecting `foundry_iq` replaces retrieval, not the Hotels or Activities
specialist boundaries.

## Trace hierarchy

```mermaid
flowchart TB
    I[Hosted invocation] --> W[Agent Framework workflow]
    W --> C[Coordinator decision]
    C --> F[Flights specialist]
    F --> FC[Function call]
    C --> H[Hotels specialist]
    H --> MC[MCP call]
    C --> A[Activities specialist]
    A --> GR[Foundry IQ retrieval]
    GR --> QP[Query planning]
    GR --> CI[Citations]
    A --> MA[MCP call]
    C --> S[Final synthesis]
```

The span hierarchy mirrors the code and makes routing, tool selection, failures,
latency, and token use observable.

## Evaluation loop

```mermaid
flowchart LR
    B[Baseline version] --> D[Evaluation dataset]
    D --> R1[Baseline run]
    R1 --> X[Inspect failures]
    X --> C[Change one instruction]
    C --> V[Candidate version]
    V --> R2[Candidate run]
    R2 --> CMP[Compare results]
```

The lab ends with a measured improvement. It does not rely on subjective prompt
testing alone.
