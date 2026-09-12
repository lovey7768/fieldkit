# FieldKit — Architectural Design Document (Part C)

## 1. Multi-Company Evolution (50+ Isolated Tenant Organizations)

To evolve FieldKit from a single-company tool into a multi-tenant platform supporting 50+ enterprise organizations, changes must be applied across three layers:

### Data Isolation: Schema-per-Tenant Model
- **Topology:** A shared PostgreSQL cluster where each company owns an isolated PostgreSQL schema (`tenant_acme.*`, `tenant_apex.*`), with a shared `public` schema for cross-tenant billing, global subscriptions, and metadata.
- **Trade-off Analysis:** While Row-Level Security (RLS) via a `tenant_id` foreign key is simpler, schema isolation eliminates cross-tenant data leaks from developer filtering oversights, makes tenant-level backup and point-in-time recovery straightforward, and simplifies regional regulatory compliance (e.g., GDPR data deletion).
- **Runtime Switching:** Fast connection poolers (PgBouncer) intercept incoming authenticated connections and execute `SET search_path TO tenant_x, public;` at checkout based on claims in the authenticated token.

### Authentication & Intake Routing
- **Tenant Auth:** Asymmetric RS256 JWTs issued by an identity provider (e.g., Keycloak). Tokens carry `tenant_id`, `roles` (`crew`, `dispatcher`, `auditor`), and cryptographic key IDs.
- **Webhook Isolation:** Endpoints transition to tenant-scoped paths: `POST /api/v1/tenants/{tenant_slug}/webhooks/events`. Each tenant registers its own cryptographic HMAC secret in Redis, validated prior to queuing.

### Deployment & Queue Topology
- **Tenant Stream Segregation:** To prevent high-volume tenants from starving lower-volume ones ("noisy neighbor" problem), Redis Streams transition from a global stream to per-tenant streams: `stream:tenant_acme`.
- **Worker Pools:** Background worker pools allocate consumers via fair round-robin scheduling across tenant streams.

---

## 2. Second Business Line Adaptability (Delivery Fleet Operations)

```text
┌───────────────────────────────────────────────────────────────┐
│              Reusable Core Engine (Zero Changes)              │
│  • Raw Byte HMAC-SHA256 Ingestion & Deduplication             │
│  • PII Tokenization Vault & Fernet Reversible Encryption      │
│  • Redis Stream Consumer Group Pipeline & DLQ Routing         │
│  • Offline-First PWA Shell (IndexedDB & Local State Queues)   │
│  • ERP Outbound Sync Resilience & Exponential Backoff         │
└───────────────────────────────┬───────────────────────────────┘
                                │
                  Domain Plugin Interface Layer
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
┌───────────────────────────────┐       ┌───────────────────────────────┐
│     Field Services Domain     │       │       Deliveries Domain       │
├───────────────────────────────┤       ├───────────────────────────────┤
│ • Asset Maintenance Registers │       │ • Multi-Stop Route Optimizer  │
│ • Long-Duration Work Orders   │       │ • Proof-of-Delivery (POD)     │
│ • Spare Parts Depletion Logs  │       │ • Live Telemetry & Fleet GPS  │
│ • Site Hazard Checklists      │       │ • Dynamic Recipient ETAs      │
└───────────────────────────────┘       └───────────────────────────────┘