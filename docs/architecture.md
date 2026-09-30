---
title: TravelBuddy architecture
description: Readable architecture diagrams for the Foundry and Agent Framework lab
author: tmathew1000
ms.date: 2026-09-30
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
    FP --> HA[TravelBuddy hosted agent]
    FP --> EV[Evaluation suite]
    HA --> MCP[Travel MCP service<br/>Azure Container Apps]
    HA --> GD[Destination grounding data]
    HA -. OpenTelemetry .-> AI[Application Insights]
    AI --> FP

    classDef learner fill:#dff6dd,stroke:#107c10,color:#000
    classDef managed fill:#e5f1fb,stroke:#0078d4,color:#000
    classDef azure fill:#fff4ce,stroke:#986f0b,color:#000
    class D learner
    class FP,MD,HA,EV managed
    class MCP,GD,AI azure
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
    A --> G[Grounding context]
```

The coordinator and specialists are four logical agents. Foundry hosts the
complete graph as one deployment.

## Capability ownership

| Agent | Responsibility | Capabilities |
| ------- | ---------------- | -------------- |
| Coordinator | Route and synthesize | Routing and termination |
| Flights | Flights, timing, weather, and currency | Python function tools |
| Hotels | Lodging areas, budgets, and trade-offs | MCP and grounding |
| Activities | Experiences and day-by-day plans | MCP and grounding |

The division is intentionally visible so you can reason about routing and inspect
each specialist in a trace.

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
    A --> GR[Grounding retrieval]
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
