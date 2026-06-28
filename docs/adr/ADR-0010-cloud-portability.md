# ADR-0010: Cloud-portable core (no AWS SDK in domain)

- Status: accepted
- Date: 2026-06-28
- Deciders: Cloud Architect, CTO, Senior Backend Engineer
- Related: ADR-0001

## Context

The charter says "AWS Ready," not "AWS locked." If the core imports `boto3` to
read a secret, fetch an object, or publish a metric, then running on GCP/Azure
or on-prem (or even locally in Docker) requires forking the core. That
violates the hexagonal principle (ADR-0001) and reduces portability.

## Options considered

**A. Sprinkle `boto3` wherever convenient.** Fast, but creates hard AWS
coupling and un-testable domain code.

**B. Cloud operations behind ports; AWS is one adapter (chosen).**
Secrets, object storage, and metrics are accessed through interfaces
(`SecretsPort`, `ObjectStorePort`, `MetricsPort`). In production an AWS
adapter satisfies them; locally, in-memory/filesystem/fakes satisfy them.

**C. A cloud-agnostic framework (e.g., a PaaS SDK).** Trades one vendor
lock-in for another. Rejected.

## Decision

The domain and services import **no cloud SDK**. Cloud capability is exposed
through ports; concrete cloud adapters live in `infra/`-adjacent adapter
modules and are selected by configuration. Production targets AWS (RDS,
ElastiCache, S3, Secrets Manager, CloudWatch) but the core is portable.

## Consequences

**Positive**
- Local dev and CI run with no AWS credentials (fakes/filesystem).
- Multi-cloud or on-prem is feasible without rewriting the core.
- Domain tests stay fast and hermetic.

**Negative**
- A little extra plumbing for secret/object/metric access.

**Neutral**
- AWS-specific IaC (Terraform) lives in `infra/` and is a Phase 18 concern.
