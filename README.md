# ⚡ FieldKit — Resilient Field Operations Platform

[![CI Pipeline](https://github.com/YOUR_USERNAME/fieldkit/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/fieldkit/actions)
[![Python Version](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

FieldKit is an event-driven edge platform built for field service crews and back-office ERP synchronization. Built with **FastAPI**, **PostgreSQL**, **Redis Streams**, and **offline-first PWA technologies**, it handles high-throughput inbound webhooks, provides cryptographic HMAC verification, performs reversible PII masking, coordinates offline field submissions, and ensures zero-loss ERP sync with automatic dead-letter queueing.

---

## 🏛️ System Architecture

```text
                                  ┌─────────────────────────────────────────┐
                                  │      Client / Mobile PWA (Field)        │
                                  │  • Camera Barcode / QR Scanner          │
                                  │  • Photo Capture & Local Compression    │
                                  │  • IndexedDB Offline Queue Auto-Flush   │
                                  └────────────────────┬────────────────────┘
                                                       │ HTTPS (client_uuid)
                                                       ▼
┌───────────────────────────┐         ┌─────────────────────────────────────┐
│  External Event Provider  │────────►│        FastAPI Ingestion Node       │
│  (X-Signature-256: HMAC)  │         │  1. Raw Byte HMAC-SHA256 Auth       │
└───────────────────────────┘         │  2. Redis SETNX Atomic Deduplication│
                                      │  3. Redis Stream Dispatch (XADD)    │
                                      └──────────────────┬──────────────────┘
                                                         │
                                                         ▼
                                      ┌─────────────────────────────────────┐
                                      │            Redis Stream             │
                                      │         key: events:stream          │
                                      └──────────────────┬──────────────────┘
                                                         │
                                                         ▼
                                      ┌─────────────────────────────────────┐
                                      │     Distributed Background Worker   │
                                      │  • Reversible PII Masking Engine    │
                                      │  • AI Intent Classification (LLM)   │
                                      │  • PostgreSQL Atomic Persistence    │
                                      │  • Outbound ERP Sync + Backoff/DLQ  │
                                      └──────────┬────────────────┬─────────┘
                                                 │                │
                        ┌────────────────────────┘                └────────────────────────┐
                        ▼                                                                  ▼
          ┌───────────────────────────┐                                      ┌───────────────────────────┐
          │     PostgreSQL Storage    │                                      │    Mock ERP REST Service  │
          │  • `events` (Masked)      │                                      │  • Bearer Token Auth      │
          │  • `pii_vault` (Encrypted)│                                      │  • Auto-DLQ Routing on    │
          │  • `dead_letter_events`   │                                      │    Terminal Retries       │
          │  • `ai_reviews` (Pending) │                                      └───────────────────────────┘
          └───────────────────────────┘
```

---

## 🔄 ERP Sync Boundary

**Stays in FieldKit (operational edge):**
Sub-second barcode/QR ingestion, raw photo uploads, offline client queuing, HMAC-verified webhook intake, PII masking vault, real-time field telemetry, and AI classification drafts awaiting human review. These require low-latency, edge-local persistence that would be too chatty or too sensitive to funnel live through an ERP.

**Belongs in the ERP (back-office system of record):**
Invoicing and general ledger entries, customer Master Service Agreements, inventory and spare parts valuation, crew payroll and scheduling, supplier procurement, and finalized job completion records. FieldKit forwards a `summary_payload` (masked, de-identified) to the ERP REST API only after local persistence and AI review are complete. The ERP never receives raw event bytes or reversible PII mappings.

---

## 🚀 One-Command Start

```bash
git clone https://github.com/lovey7768/fieldkit.git
cd fieldkit
docker compose up --build
```

| Service | Address | Description |
|---|---|---|
| Mobile Field PWA | http://localhost:8000 | Camera QR scanner + offline capture UI |
| API Docs (Swagger) | http://localhost:8000/docs | Interactive endpoint explorer |
| Pending AI Reviews | http://localhost:8000/api/reviews/pending | Human-in-the-loop review queue |
| Mock ERP | http://localhost:8080 | Standalone ERP simulator |

---

## 🧪 Run the Test Suite

```bash
docker compose exec api pytest tests/ -v
```

**14 tests across 5 files — all failure paths covered:**
- `test_intake.py` — Invalid HMAC → 401, duplicate dedup via Redis SETNX
- `test_pii.py` — Multi-country phone/email masking, recursive payload traversal
- `test_worker_resilience.py` — Healthy ERP flow, ERP-down → DLQ routing
- `test_offline_sync.py` — PWA serve, field scan ingestion, client UUID dedup
- `test_ai_integration.py` — Zero PII leakage to LLM, `PENDING_HUMAN_REVIEW` persistence

---

## 📚 Documentation

- **[DESIGN.md](DESIGN.md)** — Multi-tenant architecture, fleet business line adaptability, ERP boundaries, AI governance
- **[ANSWERS.md](ANSWERS.md)** — Engineering question responses (Parts D)

---

## 📄 License

MIT
