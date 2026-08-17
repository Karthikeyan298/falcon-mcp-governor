# MCP Governance & Agent Control Plane — MVP Design Draft

## 1. Purpose

This document captures the first draft design for an MCP Governance and Agent Control Plane MVP. The goal is to validate the product hypothesis quickly: an enterprise gateway that sits between AI clients/agents and MCP servers and enforces centralized policy for tool access, approvals, and audit.

The primary aim of the MVP is not to build a complete enterprise platform. It is to prove the value of the core mechanism:

- an AI client connects to a central gateway instead of directly to many MCP servers
- the gateway filters and authorizes tool access
- the gateway enforces allow/deny/approval decisions at runtime
- the system records what was attempted and what was allowed

This MVP should help answer the key question: does the use case resonate with real teams that want fine-grained control over AI agent tool access?

A key enterprise requirement for the MVP is that only signed tools can be used. In other words, the gateway should only allow MCP tools whose identity and metadata have been verified and trusted by policy before execution.

## 2. Problem Statement

Organizations increasingly allow AI agents to interact with enterprise systems such as Jira, GitHub, email, Kubernetes, cloud APIs, and internal tools. In the current model, agents often connect directly to MCP servers and operate with broad or implicit permissions.

That creates real risks:

- tools can be invoked without explicit authorization
- sensitive operations may occur without human approval
- tool arguments may allow unsafe or unexpected behavior
- auditing is weak or missing
- policy enforcement is scattered and hard to govern centrally

The product idea is to create a central governance layer: a policy engine and gateway that evaluates identity, tool provenance, environment, and parameter context before allowing an MCP operation.

In an enterprise setting, the system should also enforce that tool usage is restricted to trusted, signed tool manifests or signed tool metadata. This prevents untrusted or unsigned MCP tool definitions from being executed through the agent surface.

## 3. Product Thesis

Build an enterprise MCP Gateway + Governance Control Plane that enforces centrally managed policy-as-code for tool access, tool parameters, approval workflows, and audit.

The product is positioned as:

- not just a GUI for MCP server management
- not just a model gateway
- but an Agent Access Control / MCP Governance Platform

## 4. Target Users

### 4.1 Primary users

- platform/security team responsible for AI access policies
- enterprise admins managing tool exposure to agents
- operations or support teams running AI-assisted workflows
- engineering teams exposing internal tools through MCP

### 4.2 Secondary users

- developers using AI tools in IDEs and CLIs
- security/compliance stakeholders reviewing agent activity
- product owners enabling safe agent automation

## 5. MVP Goals

The MVP should prove the following minimum value:

1. A single gateway can sit between AI clients and downstream MCP servers.
2. Tool discovery can be filtered based on policy.
3. Only signed and trusted tools are permitted to execute.
4. Tool invocation can be denied or approved at runtime.
5. A basic approval flow can require human confirmation for sensitive operations.
6. Policy can be represented in a declarative format and managed centrally.
7. Requests and decisions can be logged for audit and investigation.

## 6. Non-Goals for MVP

The first version should intentionally avoid full enterprise scale features, including:

- full risk scoring and anomaly detection
- enterprise SIEM integrations
- deep RBAC hierarchy modeling
- full policy simulation engine
- multi-tenant admin UI polish
- advanced workflow automation beyond basic approval
- complete end-user self-service portal

These can be explored after the MVP proves the core use case.

## 7. MVP Scope

### 7.1 In scope

- MCP gateway server
- agent/client connection through the gateway
- upstream MCP server proxying
- tool discovery filtering
- allow/deny/approval policies
- basic policy store in YAML or JSON
- basic runtime policy evaluation
- signed tool trust enforcement
- audit log for requests and decisions
- minimal web UI for policy editing and audit viewing

### 7.2 Out of scope

- production-grade identity federation
- enterprise deployment hardening
- large-scale parallel routing
- multi-region enforcement
- advanced compliance workflows
- extensive experimentation and analytics

## 8. Proposed Architecture

### 8.1 High-level architecture

```text
AI Clients / Agents
  |        
  | MCP
  v
MCP Gateway
  - Authentication
  - Tool Registry
  - Policy Engine
  - Request Filtering
  - Parameter validation
  - Approval workflow
  - Audit logging
  - Routing
  v
Jira MCP / Email MCP / GitHub MCP / other upstream MCP servers
```

### 8.2 Control plane vs data plane

The MVP should separate the two concerns clearly:

- Control plane: policy management, roles, agents, tools, audit views, approvals
- Data plane: runtime gateway that enforces decisions in real time

This helps keep the system governance-friendly and operationally deployable.

## 9. Core Functional Requirements

### 9.1 Policy model

The gateway should enforce a simple policy-as-code model with rules similar to:

```yaml
agent:
  name: production-support
servers:
  jira:
    tools:
      search_issues:
        action: allow
      create_issue:
        action: allow
      update_issue:
        action: approval
      delete_issue:
        action: deny
  email:
    tools:
      send_email:
        action: approval
      delete_email:
        action: deny
```

The MVP should support at minimum:

- allow
- deny
- approval-required

### 9.2 Tool-level governance

The gateway must filter unauthorized tools during discovery and again when the tool is invoked.

Examples:

- Jira delete issue -> deny
- Email send to external recipient -> approval
- Kubernetes delete pod in prod -> block

### 9.3 Signed-tool governance

The gateway should enforce a signed-tool model for the MVP. Only tools that pass trust validation can be registered and invoked.

This can be represented in a simple model such as:

- `status: trusted | untrusted | revoked`
- `signature: valid | invalid`
- `publisher: approved-org`
- `tool_manifest_hash: <hash>`

A tool that is unsigned, revoked, or not present in the approved trust list should be rejected before runtime execution.

### 9.4 Parameter-level controls

A necessary MVP capability is policy based on tool arguments.

Examples:

- `email.send(recipient="employee@company.com")` -> allow
- `email.send(recipient="external@gmail.com")` -> approval
- `kubernetes.delete_pod(namespace="production")` -> deny

### 9.5 Approval workflow

For high-risk actions, the gateway should pause and request explicit approval before calling the downstream tool.

Flow:

1. agent invokes tool
2. gateway evaluates policy
3. tool is marked as approval-required
4. approval request is generated
5. user approves or rejects
6. downstream call is executed only if approved

### 9.6 Audit logging

Each request should log at least:

- timestamp
- user/agent identity
- MCP server
- tool name
- parameters/metadata
- decision
- policy id/version
- tool trust status
- signature validation result
- reason
- approval action if relevant

## 10. Minimal User Flow

### 10.1 Admin config flow

1. configure an MCP server upstream
2. register the server with the gateway
3. inspect discovered tools
4. assign a policy to each tool
5. save as YAML/JSON policy
6. deploy policy to gateway

### 10.2 End-user agent flow

1. agent connects to the gateway endpoint
2. gateway exposes only allowed tools
3. agent discovers available tools
4. agent attempts call
5. gateway checks policy and tool arguments
6. request is allowed, denied, or paused for approval
7. audit log records outcome

## 11. Recommended MVP Architecture Components

### 11.1 Gateway service

A lightweight Python/FastAPI service that:

- accepts MCP requests from clients
- proxies requests upstream
- evaluates tool permissions before execution
- records decisions and metadata
- handles approval requests

### 11.2 Policy engine

A small policy evaluator that takes:

- agent identity
- user identity
- tool name
- tool parameters
- environment
- target resource
- tool trust status
- signature validation state
- policy rules

and returns an authorization decision.

### 11.3 Policy store

A declarative store backed by:

- YAML files for local MVP
- optionally a simple JSON or SQLite layer

This keeps the MVP simple while preserving policy-as-code principles.

### 11.4 UI

A minimal admin interface for:

- viewing servers and discovered tools
- editing policy rules
- reviewing audit logs
- approving or rejecting requests

The UI should be a support layer, not the center of the product. Policy as code remains the real source of truth.

## 12. MVP Data Model

### 12.1 Entities

- User
- Agent
- Environment
- MCP Server
- Tool
- Policy Rule
- Approval Request
- Audit Event

### 12.2 Policy rule example

```json
{
  "agent": "production-support",
  "server": "jira",
  "tool": "delete_issue",
  "action": "deny",
  "reason": "destructive action not allowed"
}
```

### 12.3 Trust record example

```json
{
  "tool": "jira.delete_issue",
  "status": "trusted",
  "signature": "valid",
  "publisher": "company-platform",
  "manifest_hash": "sha256:abc123",
  "approved_by": "platform-admin"
}
```

### 12.4 Audit event example

```json
{
  "timestamp": "2026-08-14T10:12:00Z",
  "user": "alice",
  "agent": "production-support",
  "server": "email",
  "tool": "send_email",
  "parameters": {
    "recipient": "external@gmail.com"
  },
  "decision": "approval_required",
  "policy_version": "v1.2.3"
}
```

## 13. MVP Security Model

The MVP should assume a basic but explicit trust model:

- all requests pass through a central gateway
- downstream tools are not directly exposed to end users or agents
- tool access is enforced using policy evaluation
- approval gating is required for high-risk operations
- audit logs are immutable or append-only for the MVP

## 14. Prototype Plan

### Phase 1 — Validate the mechanism

Build a thin gateway that supports:

- one or two upstream MCP servers
- simple allow/deny/approval policies
- basic request filtering and forwarding
- discovery filtering for tools
- a minimal policy editor
- a basic audit log

### Phase 2 — Validate enterprise relevance

- add richer parameter checks
- add environment-specific rules
- support approval workflows in user UI
- demonstrate restricted tool sets for different agents

### Phase 3 — Expansion

- support more policy complexity
- add policy versioning and deployment workflow
- integrate with identity providers
- add more governance features and compliance views

## 15. Key Risks and Open Questions

- Do customers care more about tool restrictions or parameter restrictions?
- Is approval-required behavior enough for enterprise risk handling?
- Is the strongest wedge a governance platform, or a gateway-only product?
- Does the market prefer a GUI-first story or a policy-as-code-first story?
- How much of the value comes from the MCP gateway itself versus the policy engine?

These need to be validated through prototype usage and customer conversations.

## 16. MVP Success Criteria

The MVP is successful if it demonstrates all of the following:

- a client can connect through a single gateway instead of directly to multiple MCP servers
- tool discovery is filtered by policy
- dangerous or unauthorized tool invocations are prevented
- approval-required workflows can be enforced
- policy changes are centrally managed and auditable
- the workflow feels relevant to real enterprise AI tooling scenarios

## 17. Recommended Next Milestone

The next milestone should focus on implementing a thin MVP with:

1. a FastAPI-based gateway
2. one demo upstream MCP server
3. one second MCP server for a different tool category
4. YAML-based rules
5. allow/deny/approval behavior
6. audit logging
7. a minimal admin UI

This is the smallest implementation that can validate the use case and reveal whether the product concept is worth expanding.

## 18. Decision Summary

The product concept is promising because it addresses a real enterprise problem: AI agents need controlled access to tools and APIs, and organizations need a governance layer that is centralized, auditable, and policy-driven.

The MVP should prioritize proving the runtime enforcement mechanism and approval workflow, rather than building a broad platform prematurely.
